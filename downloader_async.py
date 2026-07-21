"""
Async / concurrent downloader — OPT-IN prototype (`python main.py --stage1-download --concurrent`).

Difference from the sequential downloader.py: the 9 subpages of each college are
fetched concurrently within a single browser context, bounded by a semaphore
(config.SUBPAGE_CONCURRENCY). Colleges are still processed one at a time, so the
maximum number of simultaneous requests hitting collegedunia per laptop is exactly
SUBPAGE_CONCURRENCY.

It reuses the sequential path's URL/pending selection, block-detection, resource
blocking and config knobs, so an A/B comparison against downloader.py isolates the
effect of concurrency alone.

IMPORTANT: concurrency raises the risk of CloudFront 403 / rate-limit (429) blocks —
6 laptops each firing SUBPAGE_CONCURRENCY requests multiply on one host. Validate on
a small sample and watch the logs for `Blocked/error` before trusting a full run.
"""
import asyncio
import os
import random
from typing import Dict

from playwright.async_api import async_playwright, Page, BrowserContext

from config import (
    HTML_DIR, HEADLESS, NAVIGATION_TIMEOUT, DELAY_BETWEEN_REQUESTS,
    SUBPAGE_MAPPING, BLOCK_RESOURCE_TYPES, HYDRATION_WAIT_MS,
    MAX_SCROLL_STEPS, SCROLL_STEP_WAIT_MS, SUBPAGE_CONCURRENCY,
)
from logger import logger
from downloader import parse_college_url, compute_pending_urls, is_valid_url_for_subpage, is_block_page


async def handle_popups(page: Page):
    """Closes/removes registration/login/newsletter popups if present (async)."""
    try:
        await page.evaluate("""() => {
            const selectors = [
                '#modal-root', '.modal', '.modal-backdrop',
                '[class*="modal"]', '[class*="backdrop"]', '[class*="popup"]'
            ];
            selectors.forEach(sel => {
                try {
                    document.querySelectorAll(sel).forEach(el => {
                        if (el.id === 'modal-root') { el.innerHTML = ''; }
                        else { el.remove(); }
                    });
                } catch(e) {}
            });
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        }""")
    except Exception:
        pass

    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass

    popup_selectors = [
        "button.close", "span.close", ".modal-close", ".close-btn",
        "[class*='close']", "[id*='close']", "button:has-text('Close')", "span:has-text('✕')"
    ]
    for selector in popup_selectors:
        try:
            loc = page.locator(selector)
            if await loc.is_visible():
                await loc.click(timeout=1000)
                logger.info(f"Closed popup with selector: {selector}")
                await page.wait_for_timeout(500)
        except Exception:
            continue


async def scroll_and_expand_page(page: Page, college_info: Dict[str, str], page_type: str):
    """Async port of the sequential scroll + expand logic (with early-exit)."""
    logger.info("Scrolling and expanding page content...")

    viewport_height = page.viewport_size["height"] if page.viewport_size else 800
    last_height = await page.evaluate("document.body.scrollHeight")
    stable_steps = 0

    for _ in range(MAX_SCROLL_STEPS):
        await page.evaluate(f"window.scrollBy(0, {viewport_height})")
        await page.wait_for_timeout(SCROLL_STEP_WAIT_MS)

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            stable_steps += 1
            if stable_steps >= 2:
                break
        else:
            stable_steps = 0
            await handle_popups(page)
        last_height = new_height

    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(500)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1000)

    expand_selectors = [
        "button:has-text('View More')", "span:has-text('View More')", "a:has-text('View More')",
        "button:has-text('Read More')", "span:has-text('Read More')",
        "button:has-text('Show More')", "span:has-text('Show More')",
    ]

    clicked_any = True
    clicks_count = 0
    max_clicks = 15
    while clicked_any and clicks_count < max_clicks:
        clicked_any = False
        await handle_popups(page)
        for selector in expand_selectors:
            try:
                locators = await page.locator(selector).all()
                for loc in locators:
                    if await loc.is_visible():
                        text = (await loc.text_content() or "").lower()
                        if any(w in text for w in ("apply", "brochure", "login", "register")):
                            continue
                        await loc.scroll_into_view_if_needed(timeout=1000)
                        await loc.click(timeout=1000)
                        logger.info(f"Clicked expand button: {text.strip()}")
                        await page.wait_for_timeout(1500)
                        if not is_valid_url_for_subpage(page.url, college_info, page_type):
                            logger.warning(f"Clicking '{text.strip()}' navigated to invalid URL {page.url}. Going back...")
                            await page.go_back()
                            await page.wait_for_timeout(1500)
                            continue
                        clicked_any = True
                        clicks_count += 1
                        if clicks_count >= max_clicks:
                            break
            except Exception:
                continue
            if clicked_any:
                break

    if page_type == "courses":
        try:
            locators = await page.locator(".course-info").all()
            logger.info(f"Found {len(locators)} course info/toggle sections to check.")
            for loc in locators:
                try:
                    if await loc.is_visible():
                        text = await loc.evaluate("node => node.textContent")
                        if "courses" in text.lower():
                            await loc.scroll_into_view_if_needed(timeout=2000)
                            await handle_popups(page)
                            try:
                                await loc.click(timeout=2000)
                            except Exception:
                                await loc.evaluate("node => node.click()")
                            logger.info("Expanded a collapsed course section.")
                            await page.wait_for_timeout(1000)
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error expanding course sections: {e}")


async def download_subpage(context: BrowserContext, sem: asyncio.Semaphore,
                           college_info: Dict[str, str], page_type: str, subpage_url: str) -> bool:
    """Downloads a single subpage under the concurrency semaphore. Mirrors the
    sync guards exactly: rejects HTTP >= 400 and block/error bodies without saving."""
    out_dir = os.path.join(HTML_DIR, page_type)
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{college_info['id']}_{college_info['slug']}.html"
    filepath = os.path.join(out_dir, filename)

    if os.path.exists(filepath):
        logger.info(f"Skipping already downloaded subpage: {page_type} -> {filename}")
        return True

    # Hold the semaphore for the whole operation so the number of in-flight
    # requests (and the post-request delay) is capped at SUBPAGE_CONCURRENCY.
    async with sem:
        logger.info(f"Downloading {page_type} from {subpage_url}")
        page = await context.new_page()
        page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
        try:
            response = await page.goto(subpage_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
            # See downloader.download_subpage for the rationale: a 404 is a
            # missing page, NOT a block, and must not be reported as one.
            if response is not None and response.status >= 400:
                status = response.status
                if status in (404, 410):
                    if page_type == "info":
                        logger.warning(
                            f"HTTP {status} NOT FOUND for base page {subpage_url} — college "
                            f"appears removed since discovery; skipping (no data captured)."
                        )
                    else:
                        logger.info(
                            f"HTTP {status}: subpage '{page_type}' does not exist for this "
                            f"college — skipping (normal, not an error): {subpage_url}"
                        )
                else:
                    logger.error(
                        f"Blocked/error HTTP {status} for {subpage_url} — not saving "
                        f"(page stays pending). Likely a geo-block or rate-limit."
                    )
                return False

            await page.wait_for_timeout(HYDRATION_WAIT_MS)
            await handle_popups(page)

            if page_type in ["courses", "reviews", "faculty", "placements", "scholarships"]:
                await scroll_and_expand_page(page, college_info, page_type)
            else:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

            content = await page.content()
            if is_block_page(content):
                logger.error(
                    f"Block/error page detected for {subpage_url} ({len(content)} bytes) — "
                    f"not saving (page stays pending)."
                )
                return False

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Successfully saved {filepath} ({len(content)} bytes)")

            delay = random.uniform(DELAY_BETWEEN_REQUESTS, DELAY_BETWEEN_REQUESTS + 2.0)
            logger.info(f"Sleeping for {delay:.2f}s...")
            await asyncio.sleep(delay)
            return True
        except Exception as e:
            logger.error(f"Failed to download subpage {subpage_url}: {e}")
            return False
        finally:
            await page.close()


async def download_college(context: BrowserContext, sem: asyncio.Semaphore, info: Dict[str, str]):
    """Fetch all subpages of one college concurrently (bounded by `sem`)."""
    tasks = [
        download_subpage(context, sem, info, page_type, info["base_url"] + suffix)
        for page_type, suffix in SUBPAGE_MAPPING.items()
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _run(limit: int):
    pending = compute_pending_urls(limit)
    if not pending:
        return

    logger.info(f"Downloading {len(pending)} new college(s) this batch "
                f"(concurrent, SUBPAGE_CONCURRENCY={SUBPAGE_CONCURRENCY}).")

    sem = asyncio.Semaphore(SUBPAGE_CONCURRENCY)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        await context.add_cookies([])

        if BLOCK_RESOURCE_TYPES:
            async def _route(route):
                if route.request.resource_type in BLOCK_RESOURCE_TYPES:
                    await route.abort()
                else:
                    await route.continue_()
            await context.route("**/*", _route)

        for idx, url in enumerate(pending, 1):
            info = parse_college_url(url)
            if not info:
                logger.warning(f"Could not parse college URL: {url}")
                continue
            logger.info(f"--- Downloading College {idx}/{len(pending)}: {info['slug']} (ID: {info['id']}) ---")
            await download_college(context, sem, info)

        await browser.close()
    logger.info("Downloader task complete (concurrent).")


def run_downloader_concurrent(limit: int = 0):
    """Sync entrypoint mirroring downloader.run_downloader() so main.py can call
    either path with the same signature."""
    asyncio.run(_run(limit))


if __name__ == "__main__":
    run_downloader_concurrent(limit=1)

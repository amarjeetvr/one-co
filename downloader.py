import csv
import os
import random
import re
import time
from typing import List, Dict
from playwright.sync_api import sync_playwright, Page, BrowserContext
from config import COLLEGE_URLS_CSV, HTML_DIR, HEADLESS, TIMEOUT, NAVIGATION_TIMEOUT, DELAY_BETWEEN_REQUESTS, SUBPAGE_MAPPING
from logger import logger

def parse_college_url(url: str) -> Dict[str, str]:
    """
    Extracts the college_id, type (colleges/university), and slug from a Collegedunia URL.
    Example: https://collegedunia.com/university/25455-iit-delhi-indian-institute-of-technology-iitd-new-delhi
    id: 25455
    slug: iit-delhi-indian-institute-of-technology-iitd-new-delhi
    """
    match = re.search(r"/(colleges?|university)/(\d+)-([^/?#]+)", url)
    if match:
        return {
            "type": match.group(1),
            "id": match.group(2),
            "slug": match.group(3)
        }
    return {}

def handle_popups(page: Page):
    """Closes any unwanted registration/login/newsletter popups if visible."""
    # Remove modal overlays directly from DOM
    try:
        page.evaluate("""() => {
            const selectors = [
                '#modal-root', '.modal', '.modal-backdrop', 
                '[class*="modal"]', '[class*="backdrop"]', '[class*="popup"]'
            ];
            selectors.forEach(sel => {
                try {
                    document.querySelectorAll(sel).forEach(el => {
                        if (el.id === 'modal-root') {
                            el.innerHTML = '';
                        } else {
                            el.remove();
                        }
                    });
                } catch(e) {}
            });
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        }""")
    except Exception:
        pass

    popup_selectors = [
        "button.close", "span.close", ".modal-close", ".close-btn", 
        "[class*='close']", "[id*='close']", "button:has-text('Close')", "span:has-text('✕')"
    ]
    # Press Escape to close most dialogs
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
        
    for selector in popup_selectors:
        try:
            loc = page.locator(selector)
            if loc.is_visible():
                loc.click(timeout=1000)
                logger.info(f"Closed popup with selector: {selector}")
                page.wait_for_timeout(500)
        except Exception:
            continue

def is_valid_url_for_subpage(url: str, college_info: Dict[str, str], page_type: str) -> bool:
    """Helper to check if a URL belongs to the targeted college subpage."""
    if college_info['id'] not in url:
        return False
    suffix = SUBPAGE_MAPPING.get(page_type, "")
    if suffix and suffix.lower() not in url.lower():
        return False
    if page_type == "info":
        for other_type, other_suffix in SUBPAGE_MAPPING.items():
            if other_type != "info" and other_suffix and other_suffix.lower() in url.lower():
                return False
    return True

def scroll_and_expand_page(page: Page, college_info: Dict[str, str], page_type: str):
    """
    Scrolls down the page gradually to trigger lazy loaders and 
    clicks visible 'View More' / 'Read More' expanders.
    """
    logger.info("Scrolling and expanding page content...")
    
    # 1. Gradual scrolling to trigger lazy loads
    viewport_height = page.viewport_size["height"] if page.viewport_size else 800
    last_height = page.evaluate("document.body.scrollHeight")
    
    for i in range(10):  # limit scroll steps
        page.evaluate(f"window.scrollBy(0, {viewport_height})")
        page.wait_for_timeout(800)
        handle_popups(page)
        
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            # Try scrolling a bit more or break
            pass
        last_height = new_height
    
    # Scroll back to top and then bottom to ensure full render
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)

    # 2. Click expand buttons
    # We should search for expand buttons, e.g. "View More", "Read More", "Show More"
    # But avoid "Apply Now", "Download Brochure", etc., which prompt login.
    expand_selectors = [
        "button:has-text('View More')", 
        "span:has-text('View More')", 
        "a:has-text('View More')",
        "button:has-text('Read More')", 
        "span:has-text('Read More')",
        "button:has-text('Show More')",
        "span:has-text('Show More')"
    ]
    
    # Let's loop and click them
    clicked_any = True
    clicks_count = 0
    max_clicks = 15  # Avoid infinite click loops
    
    while clicked_any and clicks_count < max_clicks:
        clicked_any = False
        handle_popups(page)
        
        for selector in expand_selectors:
            try:
                # Find visible elements matching the selector
                locators = page.locator(selector).all()
                for loc in locators:
                    if loc.is_visible():
                        # Verify it is not a register/apply form trigger
                        text = loc.text_content().lower()
                        if "apply" in text or "brochure" in text or "login" in text or "register" in text:
                            continue
                        
                        # Store current URL to detect navigation
                        current_url = page.url
                        
                        # Click the button
                        loc.scroll_into_view_if_needed(timeout=1000)
                        loc.click(timeout=1000)
                        logger.info(f"Clicked expand button: {text.strip()}")
                        page.wait_for_timeout(1500)
                        
                        # If URL changed to an invalid subpage, go back immediately
                        if not is_valid_url_for_subpage(page.url, college_info, page_type):
                            logger.warning(f"Clicking '{text.strip()}' navigated to invalid URL {page.url}. Going back...")
                            page.go_back()
                            page.wait_for_timeout(1500)
                            continue
                        
                        clicked_any = True
                        clicks_count += 1
                        if clicks_count >= max_clicks:
                            break
            except Exception as e:
                continue
            if clicked_any:
                break

    # 3. If we are on the courses page, find and expand all collapsed courses lists
    if page_type == "courses":
        try:
            locators = page.locator(".course-info").all()
            logger.info(f"Found {len(locators)} course info/toggle sections to check.")
            for loc in locators:
                try:
                    if loc.is_visible():
                        text = loc.evaluate("node => node.textContent")
                        if "courses" in text.lower():
                            loc.scroll_into_view_if_needed(timeout=2000)
                            handle_popups(page)
                            try:
                                loc.click(timeout=2000)
                            except Exception:
                                loc.evaluate("node => node.click()")
                            logger.info("Expanded a collapsed course section.")
                            page.wait_for_timeout(1000)
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error expanding course sections: {e}")

def download_subpage(context: BrowserContext, college_info: Dict[str, str], page_type: str, subpage_url: str) -> bool:
    """Downloads a single subpage and saves it to html/<page_type>/<college_id>_<slug>.html."""
    out_dir = os.path.join(HTML_DIR, page_type)
    os.makedirs(out_dir, exist_ok=True)
    
    filename = f"{college_info['id']}_{college_info['slug']}.html"
    filepath = os.path.join(out_dir, filename)
    
    if os.path.exists(filepath):
        logger.info(f"Skipping already downloaded subpage: {page_type} -> {filename}")
        return True
        
    logger.info(f"Downloading {page_type} from {subpage_url}")
    page = context.new_page()
    
    # Set default navigation timeout
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
    
    try:
        # Navigate
        page.goto(subpage_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
        
        # Wait a bit for JS hydration
        page.wait_for_timeout(2000)
        
        # Close initial modals if any
        handle_popups(page)
        
        # Scroll and expand sections (especially for courses/fees page)
        if page_type in ["courses", "reviews", "faculty", "placements", "scholarships"]:
            scroll_and_expand_page(page, college_info, page_type)
        else:
            # General scroll to trigger simple dynamic content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            
        # Get outer HTML
        content = page.content()
        
        # Save HTML
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info(f"Successfully saved {filepath} ({len(content)} bytes)")
        
        # Rotational delay
        delay = random.uniform(DELAY_BETWEEN_REQUESTS, DELAY_BETWEEN_REQUESTS + 2.0)
        logger.info(f"Sleeping for {delay:.2f}s...")
        time.sleep(delay)
        return True
        
    except Exception as e:
        logger.error(f"Failed to download subpage {subpage_url}: {e}")
        return False
    finally:
        page.close()

def run_downloader(limit: int = 0):
    """
    Main function to read college URLs from CSV and download all subpages.
    limit: if > 0, only download pages for the first `limit` colleges.
    """
    if not os.path.exists(COLLEGE_URLS_CSV):
        logger.error(f"College URLs CSV not found at {COLLEGE_URLS_CSV}. Run discovery.py first.")
        return
        
    urls = []
    with open(COLLEGE_URLS_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if row:
                urls.append(row[0])
                
    if limit > 0:
        urls = urls[:limit]
        
    logger.info(f"Preparing to download pages for {len(urls)} colleges.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        # Accept cookies globally if needed or setup mock location
        context.add_cookies([])
        
        for idx, url in enumerate(urls, 1):
            info = parse_college_url(url)
            if not info:
                logger.warning(f"Could not parse college URL: {url}")
                continue
                
            logger.info(f"--- Processing College {idx}/{len(urls)}: {info['slug']} (ID: {info['id']}) ---")
            
            for page_type, path_suffix in SUBPAGE_MAPPING.items():
                # Form subpage URL
                subpage_url = url + path_suffix
                download_subpage(context, info, page_type, subpage_url)
                
        browser.close()
    logger.info("Downloader task complete.")

if __name__ == "__main__":
    run_downloader(limit=1)

import csv
import os
import re
import time
from playwright.sync_api import sync_playwright
from config import COLLEGE_URLS_CSV, HEADLESS, TIMEOUT
from logger import logger

def clean_url(url: str) -> str:
    """Ensure URL is absolute and strip query parameters/hash."""
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://collegedunia.com" + url
    
    # Strip query parameters
    url = url.split("?")[0].split("#")[0]
    return url.strip()

def is_college_url(url: str) -> bool:
    """Check if the URL points to a college or university profile."""
    return bool(re.search(r"/(colleges?|university)/\d+", url))

def discover_college_urls(listing_url: str = "https://collegedunia.com/india-colleges", max_colleges: int = 50):
    """
    Crawls the listing page, scrolls to load dynamic content,
    extracts college profile URLs and any snippet data (avg package, rank)
    visible on the card, and saves them to CSV.
    """
    logger.info(f"Starting URL discovery from: {listing_url}")
    discovered_urls = set()
    card_meta: dict = {}  # url -> {avg_package, rank} from listing cards

    # Load existing URLs to avoid losing them
    if os.path.exists(COLLEGE_URLS_CSV):
        try:
            with open(COLLEGE_URLS_CSV, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row:
                        discovered_urls.add(row[0])
            logger.info(f"Loaded {len(discovered_urls)} existing URLs from {COLLEGE_URLS_CSV}")
        except Exception as e:
            logger.warning(f"Error loading existing URLs: {e}")

    with sync_playwright() as p:
        logger.info("Launching browser for discovery...")
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            logger.info(f"Navigating to {listing_url}...")
            page.goto(listing_url, timeout=TIMEOUT)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            scroll_count = 0
            max_scrolls = 20

            while len(discovered_urls) < max_colleges and scroll_count < max_scrolls:
                from bs4 import BeautifulSoup
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                # Extract college card links + any visible avg_package / rank snippets
                for a_tag in soup.find_all("a", href=True):
                    href = clean_url(a_tag["href"])
                    if not is_college_url(href) or href in discovered_urls:
                        continue

                    discovered_urls.add(href)
                    logger.info(f"Discovered: {href}")

                    # Try to read card-level package / rank from surrounding card element
                    card = a_tag.find_parent(["div", "li", "article"])
                    if card:
                        card_text = card.get_text(" ", strip=True)
                        pkg_m = re.search(
                            r"(?:Avg\.?|Average)\s*(?:Package|Salary|CTC)[^\d]{0,20}([0-9][0-9\.]*\s*(?:LPA|Lakh|Lakhs|Cr))",
                            card_text, re.I
                        )
                        rank_m = re.search(
                            r"(?:NIRF|Rank(?:ed)?)\s*[:#]?\s*(\d+)",
                            card_text, re.I
                        )
                        card_meta[href] = {
                            "listing_avg_package": pkg_m.group(1).strip() if pkg_m else "",
                            "listing_rank": f"#{rank_m.group(1)}" if rank_m else ""
                        }

                    if len(discovered_urls) >= max_colleges:
                        break

                logger.info(f"Scroll #{scroll_count}: total URLs={len(discovered_urls)}")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                scroll_count += 1

        except Exception as e:
            logger.error(f"Error during URL discovery: {e}")
        finally:
            browser.close()

    # Save to CSV — include listing-page metadata columns
    os.makedirs(os.path.dirname(COLLEGE_URLS_CSV), exist_ok=True)
    try:
        with open(COLLEGE_URLS_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "listing_avg_package", "listing_rank"])
            for url in sorted(discovered_urls):
                meta = card_meta.get(url, {})
                writer.writerow([url, meta.get("listing_avg_package", ""), meta.get("listing_rank", "")])
        logger.info(f"Saved {len(discovered_urls)} URLs to {COLLEGE_URLS_CSV}")
    except Exception as e:
        logger.error(f"Failed to write URLs to CSV: {e}")

if __name__ == "__main__":
    discover_college_urls(max_colleges=10)

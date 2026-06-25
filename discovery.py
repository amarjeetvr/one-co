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
    # Matches /university/<id>-<slug> or /college/<id>-<slug> or /colleges/<id>-<slug>
    pattern = r"/colleges?/\d+-[a-zA-Z0-9-]+" or r"/university/\d+-[a-zA-Z0-9-]+"
    # Also support general matching for collegedunia university/college URLs
    return bool(re.search(r"/(colleges|college|university)/\d+", url))

def discover_college_urls(listing_url: str = "https://collegedunia.com/india-colleges", max_colleges: int = 50):
    """
    Crawls the listing page, scrolls to load dynamic content, 
    extracts college profile URLs, and saves them to csv.
    """
    logger.info(f"Starting URL discovery from: {listing_url}")
    discovered_urls = set()
    
    # Load existing URLs if CSV exists to avoid losing them
    if os.path.exists(COLLEGE_URLS_CSV):
        try:
            with open(COLLEGE_URLS_CSV, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    if row:
                        discovered_urls.add(row[0])
            logger.info(f"Loaded {len(discovered_urls)} existing URLs from {COLLEGE_URLS_CSV}")
        except Exception as e:
            logger.warning(f"Error loading existing URLs: {e}")

    # Add default test URL (IIT Delhi) if not present, to ensure it is always included for verification
    test_url = "https://collegedunia.com/university/25455-iit-delhi-indian-institute-of-technology-iitd-new-delhi"
    discovered_urls.add(test_url)
    
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
            
            scroll_count = 0
            max_scrolls = 20  # Limit scrolls to prevent infinite loops
            
            while len(discovered_urls) < max_colleges and scroll_count < max_scrolls:
                # Extract links on current viewport
                links = page.locator("a").all()
                new_found = 0
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        if href:
                            abs_url = clean_url(href)
                            if is_college_url(abs_url) and abs_url not in discovered_urls:
                                discovered_urls.add(abs_url)
                                logger.info(f"Discovered college URL: {abs_url}")
                                new_found += 1
                                if len(discovered_urls) >= max_colleges:
                                    break
                    except Exception:
                        continue
                
                logger.info(f"Scroll #{scroll_count}: found {new_found} new URLs. Total in set: {len(discovered_urls)}")
                
                # Scroll down
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)  # Wait for dynamic elements to load
                scroll_count += 1
                
        except Exception as e:
            logger.error(f"Error during URL discovery: {e}")
        finally:
            browser.close()
            
    # Save to CSV
    os.makedirs(os.path.dirname(COLLEGE_URLS_CSV), exist_ok=True)
    try:
        with open(COLLEGE_URLS_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url"])
            for url in sorted(discovered_urls):
                writer.writerow([url])
        logger.info(f"Saved {len(discovered_urls)} URLs to {COLLEGE_URLS_CSV}")
    except Exception as e:
        logger.error(f"Failed to write URLs to CSV: {e}")

if __name__ == "__main__":
    discover_college_urls(max_colleges=10)

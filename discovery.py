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


def _extract_listing_placement_metrics(card_text: str) -> dict:
    """Extract average/highest package and placement percentage from listing-card text."""
    result = {
        "listing_avg_package": "",
        "listing_highest_package": "",
        "listing_placement_percentage": "",
    }

    text = re.sub(r"\s+", " ", card_text or "").strip()
    if not text:
        return result

    amount = r"(?:₹\s*)?([0-9][0-9,]*(?:\.[0-9]+)?(?:\s*(?:LPA|Lakh|Lakhs|Cr|Crore|CPA))?)"

    avg_patterns = [
        rf"{amount}\s*(?:Average|Avg\.?)(?:\s+Package|\s+Salary|\s+CTC)?",
        rf"(?:Average|Avg\.?)(?:\s+Package|\s+Salary|\s+CTC)[^0-9]{{0,25}}{amount}",
    ]
    high_patterns = [
        rf"{amount}\s*(?:Highest|Top)(?:\s+Package|\s+Salary|\s+CTC)?",
        rf"(?:Highest|Top)(?:\s+Package|\s+Salary|\s+CTC)[^0-9]{{0,25}}{amount}",
    ]
    pct_patterns = [
        r"(\d{1,3}(?:\.\d+)?\s*%)\s*(?:placements?|placed)",
        r"(?:placements?|placed)[^0-9]{0,20}(\d{1,3}(?:\.\d+)?\s*%)",
    ]

    for pattern in avg_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            result["listing_avg_package"] = m.group(1).strip()
            break

    for pattern in high_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            result["listing_highest_package"] = m.group(1).strip()
            break

    for pattern in pct_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            result["listing_placement_percentage"] = m.group(1).strip()
            break

    return result


def extract_cd_rank(card) -> str:
    """Extract the visible CD Rank shown on a listing card."""
    card_text = card.get_text(" ", strip=True)

    # The listing card usually begins with the CD Rank token, e.g. "#1 IIT Delhi ...".
    start_match = re.search(r"^#\s*(\d{1,3})\b", card_text)
    if start_match:
        return f"#{int(start_match.group(1))}"

    # Fallback: inspect individual text nodes and keep the first leading #N token.
    for text_node in card.stripped_strings:
        node_match = re.match(r"^#\s*(\d{1,3})\b", text_node)
        if node_match:
            return f"#{int(node_match.group(1))}"

    return ""

def discover_college_urls(listing_url: str = "https://collegedunia.com/india-colleges", max_colleges: int = 50):
    """
    Crawls the listing page, scrolls to load dynamic content,
    extracts college profile URLs and any snippet data (avg package, rank)
    visible on the card, and saves them to CSV.
    """
    logger.info(f"Starting URL discovery from: {listing_url}")
    discovered_list = []  # preserve order to infer CD Rank by position
    discovered_set = set()
    card_meta: dict = {}  # url -> {avg_package, rank} from listing cards

    # Load existing URLs to avoid losing them (preserve order if file exists)
    if os.path.exists(COLLEGE_URLS_CSV):
        try:
            with open(COLLEGE_URLS_CSV, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row:
                        discovered_list.append(row[0])
                        discovered_set.add(row[0])
            logger.info(f"Loaded {len(discovered_list)} existing URLs from {COLLEGE_URLS_CSV}")
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
            # Dynamic max scrolls to support larger limits (e.g. 500 colleges)
            max_scrolls = max(200, max_colleges * 2)

            while len(discovered_list) < max_colleges and scroll_count < max_scrolls:
                from bs4 import BeautifulSoup
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                # Extract college card containers and read visible listing metrics.
                card_containers = soup.find_all("tr", class_=re.compile(r"table-row", re.I))
                if not card_containers:
                    card_containers = soup.find_all(["div", "li", "article"], class_=re.compile(r"listing|card|college|result|row|item", re.I))
                for card in card_containers:
                    # prefer the first anchor inside the card that looks like a college link
                    a_tag = card.find("a", href=True)
                    if not a_tag:
                        continue
                    href = clean_url(a_tag["href"])
                    if not is_college_url(href) or href in discovered_set:
                        continue

                    # record in ordered list + membership set
                    discovered_list.append(href)
                    discovered_set.add(href)
                    logger.info(f"Discovered: {href}")

                    card_text = card.get_text(" ", strip=True)
                    placement_metrics = _extract_listing_placement_metrics(card_text)

                    # Primary: look for explicit ranking mentions (NIRF / Rank within text)
                    rank_m = re.search(
                        r"(?:NIRF(?:\s*Ranking)?|Rank(?:ed)?)\s*(?:[:#]?\s*)?(\d{1,3})(?:st|nd|rd|th)?\b",
                        card_text, re.I
                    )

                    # Fallback: scan visible text nodes for the leading CD Rank token.
                    cd_rank = extract_cd_rank(card) if not rank_m else ""

                    listing_rank_val = ""
                    if rank_m:
                        listing_rank_val = f"#{rank_m.group(1)}"
                    elif cd_rank:
                        listing_rank_val = cd_rank

                    # If we didn't find a rank token, use the card position as CD Rank.
                    if not listing_rank_val:
                        listing_rank_val = f"#{len(discovered_list)}"

                    card_meta[href] = {
                        "listing_avg_package": placement_metrics.get("listing_avg_package", ""),
                        "listing_highest_package": placement_metrics.get("listing_highest_package", ""),
                        "listing_placement_percentage": placement_metrics.get("listing_placement_percentage", ""),
                        "listing_rank": listing_rank_val
                    }

                    if len(discovered_list) >= max_colleges:
                        break

                # Secondary pass: some ranks appear outside the immediate card container
                # (e.g., left-column CD Rank). Find standalone '#N' tokens and try to
                # associate them with nearby college links if we missed them.
                for txt in soup.find_all(string=re.compile(r"#\s*\d{1,3}\b")):
                    try:
                        num_m = re.search(r"#\s*(\d{1,3})\b", txt)
                        if not num_m:
                            continue
                        num = num_m.group(1)
                        parent = txt.parent
                        # look for anchors in the same row/ancestor scope
                        associated = None
                        for anc in [parent] + list(parent.parents)[:4]:
                            anchors = anc.find_all("a", href=True)
                            for a in anchors:
                                href = clean_url(a.get("href", ""))
                                if is_college_url(href):
                                    associated = href
                                    break
                            if associated:
                                break

                        if associated and associated not in discovered_set:
                            if len(discovered_list) >= max_colleges:
                                break
                            discovered_list.append(associated)
                            discovered_set.add(associated)
                        if associated:
                            meta = card_meta.get(associated, {})
                            if not meta.get("listing_rank"):
                                meta["listing_rank"] = f"#{num}"
                                card_meta[associated] = meta
                    except Exception:
                        continue
                if len(discovered_list) >= max_colleges:
                    break

                logger.info(f"Scroll #{scroll_count}: total URLs={len(discovered_list)}")
                # Bypass popup modals to prevent scroll block
                try:
                    page.evaluate("""() => {
                        const modalRoot = document.getElementById('modal-root');
                        if (modalRoot) modalRoot.remove();
                        const modals = document.querySelectorAll('.modal, .modal-backdrop, [class*="modal"], [class*="Popup"]');
                        modals.forEach(m => m.remove());
                        document.body.style.overflow = 'auto';
                        document.documentElement.style.overflow = 'auto';
                    }""")
                except Exception:
                    pass
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                scroll_count += 1

        except Exception as e:
            logger.error(f"Error during URL discovery: {e}")
        finally:
            try:
                browser.close()
            except Exception as close_error:
                logger.warning(f"Browser close failed during discovery cleanup: {close_error}")

    # Save to CSV — include listing-page metadata columns
    os.makedirs(os.path.dirname(COLLEGE_URLS_CSV), exist_ok=True)
    try:
        with open(COLLEGE_URLS_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "url",
                "listing_avg_package",
                "listing_highest_package",
                "listing_placement_percentage",
                "listing_rank",
            ])
            for url in discovered_list:
                meta = card_meta.get(url, {})
                writer.writerow([
                    url,
                    meta.get("listing_avg_package", ""),
                    meta.get("listing_highest_package", ""),
                    meta.get("listing_placement_percentage", ""),
                    meta.get("listing_rank", ""),
                ])
        logger.info(f"Saved {len(discovered_list)} URLs to {COLLEGE_URLS_CSV}")
    except Exception as e:
        logger.error(f"Failed to write URLs to CSV: {e}")

if __name__ == "__main__":
    discover_college_urls(max_colleges=10)

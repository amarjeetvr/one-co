import argparse
import csv
import os
import re
from typing import List, Dict, Tuple, Any
from config import HTML_DIR, SUBPAGE_MAPPING, COLLEGE_URLS_CSV
from logger import logger
from discovery import discover_college_urls
from downloader import run_downloader
import college_parser as parser


def discover_downloaded_colleges() -> List[Tuple[str, str]]:
    """Scans all folders under html/ to find unique (college_id, slug) combinations."""
    colleges = set()
    if not os.path.exists(HTML_DIR):
        return []
    for page_type in SUBPAGE_MAPPING.keys():
        type_dir = os.path.join(HTML_DIR, page_type)
        if os.path.exists(type_dir):
            for filename in os.listdir(type_dir):
                if filename.endswith(".html"):
                    match = re.match(r"^(\d+)_(.+)\.html$", filename)
                    if match:
                        colleges.add((match.group(1), match.group(2)))
    return sorted(list(colleges))


def load_listing_metadata() -> Dict[str, Dict]:
    """Reads listing placement/rank columns written by discovery."""
    meta = {}
    if not os.path.exists(COLLEGE_URLS_CSV):
        return meta

    def _row_get(row: Dict[str, str], key: str) -> str:
        if key in row:
            return row.get(key, "")
        if key == "url" and "\ufeffurl" in row:
            return row.get("\ufeffurl", "")
        for existing_key in row.keys():
            normalized = existing_key.replace('"', "").replace("\ufeff", "").strip().lower()
            if normalized == key:
                return row.get(existing_key, "")
        return ""

    with open(COLLEGE_URLS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = _row_get(row, "url").strip()
            if url:
                meta[url] = {
                    "listing_avg_package": _row_get(row, "listing_avg_package").strip(),
                    "listing_highest_package": _row_get(row, "listing_highest_package").strip(),
                    "listing_placement_percentage": _row_get(row, "listing_placement_percentage").strip(),
                    "listing_rank": _row_get(row, "listing_rank").strip(),
                }
    return meta


def run_parsing_and_export():
    """Reads all downloaded HTML files, parses them offline, and exports to JSON and Excel."""
    import exporter

    logger.info("Starting Stage 2: Offline parsing and export...")

    downloaded = discover_downloaded_colleges()
    if not downloaded:
        logger.warning(f"No downloaded HTML files found under {HTML_DIR}. Run stage 1 first.")
        return

    logger.info(f"Found {len(downloaded)} college(s) to parse.")
    listing_meta = load_listing_metadata()

    all_colleges = []
    all_courses = []
    all_admissions = []
    all_placements = []
    all_rankings = []
    all_faculty = []
    all_scholarships = []
    all_hostels = []
    all_reviews = []

    for college_id, slug in downloaded:
        logger.info(f"Parsing college: {slug} (ID: {college_id})")

        info_file = os.path.join(HTML_DIR, "info", f"{college_id}_{slug}.html")
        college_url = f"https://collegedunia.com/university/{college_id}-{slug}"

        # 1. Parse Info — merge listing-page metadata if available
        info_html = ""
        info_data = {}
        if os.path.exists(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    info_html = f.read()
                info_data = parser.parse_college_info(info_html, college_id, college_url)

                # Always prefer the listing page's Collegedunia rank for the college summary
                card = listing_meta.get(college_url, {})
                if card.get("listing_rank"):
                    info_data["ranking"] = f"CD Rank {card['listing_rank']}"

                all_colleges.append(info_data)
            except Exception as e:
                logger.error(f"Error parsing info for {slug}: {e}")
        else:
            logger.warning(f"Info HTML file missing for {slug}: {info_file}")

        # 2. Parse Courses
        courses_file = os.path.join(HTML_DIR, "courses", f"{college_id}_{slug}.html")
        if os.path.exists(courses_file):
            try:
                with open(courses_file, "r", encoding="utf-8") as f:
                    html = f.read()
                all_courses.extend(parser.parse_courses(html, college_id, college_url))
            except Exception as e:
                logger.error(f"Error parsing courses for {slug}: {e}")

        # 3. Parse Admissions
        admissions_file = os.path.join(HTML_DIR, "admissions", f"{college_id}_{slug}.html")
        if os.path.exists(admissions_file):
            try:
                with open(admissions_file, "r", encoding="utf-8") as f:
                    html = f.read()
                all_admissions.append(parser.parse_admissions(html, college_id))
            except Exception as e:
                logger.error(f"Error parsing admissions for {slug}: {e}")

        # 4. Parse Placements & Rankings
        placements_file = os.path.join(HTML_DIR, "placements", f"{college_id}_{slug}.html")
        if os.path.exists(placements_file):
            try:
                with open(placements_file, "r", encoding="utf-8") as f:
                    placement_html = f.read()

                placement_data = parser.parse_placements(placement_html, college_id)

                # Fall back to listing-card metrics ONLY if parsed subpage metrics are "Not Specified"
                card = listing_meta.get(college_url, {})
                if card:
                    if placement_data.get("average_package") in (None, "", "Not Specified"):
                        listing_avg = card.get("listing_avg_package")
                        if listing_avg and listing_avg.strip():
                            placement_data["average_package"] = listing_avg.strip()
                        else:
                            placement_data["average_package"] = "Not Specified"

                    if placement_data.get("highest_package") in (None, "", "Not Specified"):
                        listing_highest = card.get("listing_highest_package")
                        if listing_highest and listing_highest.strip():
                            placement_data["highest_package"] = listing_highest.strip()
                        else:
                            placement_data["highest_package"] = "Not Specified"

                    if placement_data.get("placement_percentage") in (None, "", "Not Specified"):
                        listing_pct = card.get("listing_placement_percentage")
                        if listing_pct and listing_pct.strip():
                            placement_data["placement_percentage"] = listing_pct.strip()
                        else:
                            placement_data["placement_percentage"] = "Not Specified"

                all_placements.append(placement_data)

                # Rankings: search both placement page + info page
                all_rankings.extend(
                    parser.parse_rankings(placement_html, college_id, extra_html=info_html)
                )
                # Always use discovery's listing_rank as the authoritative CD Rank.
                # Parsed Collegedunia ranks can capture other rank snippets (e.g. #1/500)
                # that are not the listing CD Rank we want to store.
                card = listing_meta.get(college_url, {})
                listing_rank = card.get("listing_rank")
                if listing_rank:
                    # Drop existing Collegedunia entries for this college, then append CD Rank.
                    all_rankings = [
                        r for r in all_rankings
                        if not (r.get("college_id") == college_id and r.get("ranking_body") == "Collegedunia")
                    ]
                    all_rankings.append({
                        "college_id": college_id,
                        "ranking_body": "Collegedunia",
                        "rank": f"CD Rank {listing_rank}",
                        "ranking_year": None
                    })
            except Exception as e:
                logger.error(f"Error parsing placements for {slug}: {e}")

        # 5. Parse Faculty
        faculty_file = os.path.join(HTML_DIR, "faculty", f"{college_id}_{slug}.html")
        if os.path.exists(faculty_file):
            try:
                with open(faculty_file, "r", encoding="utf-8") as f:
                    html = f.read()
                all_faculty.extend(parser.parse_faculty(html, college_id))
            except Exception as e:
                logger.error(f"Error parsing faculty for {slug}: {e}")

        # 6. Parse Scholarships
        scholarships_file = os.path.join(HTML_DIR, "scholarships", f"{college_id}_{slug}.html")
        if os.path.exists(scholarships_file):
            try:
                with open(scholarships_file, "r", encoding="utf-8") as f:
                    html = f.read()
                all_scholarships.extend(parser.parse_scholarships(html, college_id))
            except Exception as e:
                logger.error(f"Error parsing scholarships for {slug}: {e}")

        # 7. Parse Hostel
        hostel_file = os.path.join(HTML_DIR, "hostel", f"{college_id}_{slug}.html")
        if os.path.exists(hostel_file):
            try:
                with open(hostel_file, "r", encoding="utf-8") as f:
                    html = f.read()
                all_hostels.append(parser.parse_hostel(html, college_id))
            except Exception as e:
                logger.error(f"Error parsing hostel for {slug}: {e}")

        # 8. Parse Reviews
        reviews_file = os.path.join(HTML_DIR, "reviews", f"{college_id}_{slug}.html")
        if os.path.exists(reviews_file):
            try:
                with open(reviews_file, "r", encoding="utf-8") as f:
                    html = f.read()
                all_reviews.extend(parser.parse_reviews(html, college_id))
            except Exception as e:
                logger.error(f"Error parsing reviews for {slug}: {e}")

    # Only keep Collegedunia ranking records for export
    all_rankings = [r for r in all_rankings if r.get("ranking_body") == "Collegedunia"]

    exporter.export_all_to_excel(
        colleges=all_colleges,
        courses=all_courses,
        admissions=all_admissions,
        placements=all_placements,
        rankings=all_rankings,
        faculty=all_faculty,
        scholarships=all_scholarships,
        hostels=all_hostels,
        reviews=all_reviews
    )
    logger.info("Offline parsing and export complete.")


def main():
    parser = argparse.ArgumentParser(description="Collegedunia Enterprise Scraper & Parser Pipeline")
    parser.add_argument("--stage1-discover", action="store_true", help="Run only Stage 1 college URL discovery")
    parser.add_argument("--stage1-download", action="store_true", help="Run only Stage 1 page downloading")
    parser.add_argument("--stage2-parse", action="store_true", help="Run only Stage 2 HTML offline parsing & export")
    parser.add_argument("--all", action="store_true", default=True, help="Run full end-to-end pipeline (default)")
    parser.add_argument("--limit", type=int, default=500, help="Limit number of colleges to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for incremental discovery and download")

    args = parser.parse_args()

    if args.stage1_discover:
        discover_college_urls(max_colleges=args.limit)
    elif args.stage1_download:
        run_downloader(limit=args.limit)
    elif args.stage2_parse:
        run_parsing_and_export()
    else:
        logger.info("Starting Full End-to-End Scraper Pipeline...")
        total_limit = args.limit
        batch_size = args.batch_size

        if batch_size <= 0:
            batch_size = 100

        current_limit = min(batch_size, total_limit)
        while current_limit <= total_limit:
            logger.info(f"\n========================================\n"
                        f"STARTING BATCH: {current_limit} Colleges (Max: {total_limit})\n"
                        f"========================================")
            
            logger.info(f"Stage 1: Discovering up to {current_limit} URLs...")
            discover_college_urls(max_colleges=current_limit)
            
            logger.info(f"Stage 2: Downloading subpages up to {current_limit} colleges...")
            run_downloader(limit=current_limit)
            
            logger.info(f"Stage 3: Parsing and exporting data...")
            run_parsing_and_export()
            
            if current_limit >= total_limit:
                break
            current_limit = min(current_limit + batch_size, total_limit)

        logger.info("Pipeline Execution Finished.")


if __name__ == "__main__":
    main()

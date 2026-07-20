import argparse
import csv
import os
import re
from typing import List, Dict, Tuple, Any
from config import HTML_DIR, SUBPAGE_MAPPING, COLLEGE_URLS_CSV
from logger import logger
from discovery import discover_college_urls
from downloader import run_downloader
from downloader_async import run_downloader_concurrent
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


def _load_existing_json() -> Dict[str, List]:
    """Load all existing JSON data files into memory, keyed by dataset name."""
    import json
    from config import JSON_DIR
    datasets = ["colleges", "courses", "admissions", "placements", "rankings",
                "faculty", "scholarships", "hostel", "reviews"]
    result = {}
    for name in datasets:
        path = os.path.join(JSON_DIR, f"{name}.json")
        try:
            result[name] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
        except Exception:
            result[name] = []
    return result


def run_parsing_and_export():
    """Parses only NEW colleges (not already in JSON) and merges into existing data."""
    import exporter

    logger.info("Starting Stage 2: Offline parsing and export...")

    downloaded = discover_downloaded_colleges()
    if not downloaded:
        logger.warning(f"No downloaded HTML files found under {HTML_DIR}. Run stage 1 first.")
        return

    # Load existing JSON — skip colleges already parsed
    existing = _load_existing_json()
    already_parsed_ids = {c["college_id"] for c in existing["colleges"]}
    new_colleges = [(cid, slug) for cid, slug in downloaded if cid not in already_parsed_ids]

    logger.info(f"Total downloaded: {len(downloaded)} | Already parsed: {len(already_parsed_ids)} | New to parse: {len(new_colleges)}")

    if not new_colleges:
        logger.info("Nothing new to parse. All downloaded colleges are already in JSON.")
        from config import EXPORTS_EXCEL
        if not os.path.exists(EXPORTS_EXCEL) or any(existing.values()):
            if any(existing.values()):
                logger.info("Compiling/re-compiling Excel workbook from existing JSON data...")
                exporter.export_all_to_excel(
                    colleges=existing["colleges"],
                    courses=existing["courses"],
                    admissions=existing["admissions"],
                    placements=existing["placements"],
                    rankings=existing["rankings"],
                    faculty=existing["faculty"],
                    scholarships=existing["scholarships"],
                    hostels=existing["hostel"],
                    reviews=existing["reviews"]
                )
            else:
                logger.warning("No parsed data found in JSON to compile.")
        return

    listing_meta = load_listing_metadata()

    new_data: Dict[str, List] = {
        "colleges": [], "courses": [], "admissions": [], "placements": [],
        "rankings": [], "faculty": [], "scholarships": [], "hostel": [], "reviews": []
    }

    for college_id, slug in new_colleges:
        logger.info(f"Parsing NEW college: {slug} (ID: {college_id})")

        info_file = os.path.join(HTML_DIR, "info", f"{college_id}_{slug}.html")

        # Resolve correct base URL (/university/ or /college/)
        college_url = f"https://collegedunia.com/university/{college_id}-{slug}"
        for candidate in [
            f"https://collegedunia.com/university/{college_id}-{slug}",
            f"https://collegedunia.com/college/{college_id}-{slug}",
        ]:
            if candidate in listing_meta:
                college_url = candidate
                break

        info_html = ""
        if os.path.exists(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    info_html = f.read()
                info_data = parser.parse_college_info(info_html, college_id, college_url)
                card = listing_meta.get(college_url, {})
                if card.get("listing_rank"):
                    info_data["ranking"] = f"CD Rank {card['listing_rank']}"
                new_data["colleges"].append(info_data)
            except Exception as e:
                logger.error(f"Error parsing info for {slug}: {e}")
        else:
            logger.warning(f"Info HTML missing for {slug}")

        for subpage, key, parse_fn, is_list in [
            ("courses",      "courses",      lambda h: parser.parse_courses(h, college_id, college_url),      True),
            ("admissions",   "admissions",   lambda h: parser.parse_admissions(h, college_id),               False),
            ("faculty",      "faculty",      lambda h: parser.parse_faculty(h, college_id),                  True),
            ("scholarships", "scholarships", lambda h: parser.parse_scholarships(h, college_id),             True),
            ("hostel",       "hostel",       lambda h: parser.parse_hostel(h, college_id),                   False),
            ("reviews",      "reviews",      lambda h: parser.parse_reviews(h, college_id),                  True),
        ]:
            fpath = os.path.join(HTML_DIR, subpage, f"{college_id}_{slug}.html")
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        h = f.read()
                    result = parse_fn(h)
                    if is_list:
                        new_data[key].extend(result)
                    else:
                        new_data[key].append(result)
                except Exception as e:
                    logger.error(f"Error parsing {subpage} for {slug}: {e}")

        # Placements + Rankings together
        placements_file = os.path.join(HTML_DIR, "placements", f"{college_id}_{slug}.html")
        if os.path.exists(placements_file):
            try:
                with open(placements_file, "r", encoding="utf-8") as f:
                    placement_html = f.read()
                placement_data = parser.parse_placements(placement_html, college_id)
                card = listing_meta.get(college_url, {})
                if card:
                    for field, listing_key in [("average_package", "listing_avg_package"),
                                               ("highest_package", "listing_highest_package"),
                                               ("placement_percentage", "listing_placement_percentage")]:
                        if placement_data.get(field) in (None, "", "Not Specified"):
                            v = card.get(listing_key, "").strip()
                            placement_data[field] = v or "Not Specified"
                new_data["placements"].append(placement_data)
                new_data["rankings"].extend(
                    parser.parse_rankings(placement_html, college_id, extra_html=info_html)
                )
            except Exception as e:
                logger.error(f"Error parsing placements for {slug}: {e}")

    # Deduplicate new rankings
    existing_rank_keys = {
        (r["college_id"], r["ranking_body"], r["ranking_year"])
        for r in existing["rankings"]
    }
    deduped_new_rankings = []
    for r in new_data["rankings"]:
        key = (r.get("college_id"), r.get("ranking_body"), r.get("ranking_year"))
        if key not in existing_rank_keys:
            existing_rank_keys.add(key)
            deduped_new_rankings.append(r)
    new_data["rankings"] = deduped_new_rankings

    # Merge new data into existing
    merged = {
        "colleges":      existing["colleges"]      + new_data["colleges"],
        "courses":       existing["courses"]       + new_data["courses"],
        "admissions":    existing["admissions"]    + new_data["admissions"],
        "placements":    existing["placements"]    + new_data["placements"],
        "rankings":      existing["rankings"]      + new_data["rankings"],
        "faculty":       existing["faculty"]       + new_data["faculty"],
        "scholarships":  existing["scholarships"]  + new_data["scholarships"],
        "hostel":        existing["hostel"]        + new_data["hostel"],
        "reviews":       existing["reviews"]       + new_data["reviews"],
    }

    logger.info(f"Merged totals — colleges: {len(merged['colleges'])}, courses: {len(merged['courses'])}, rankings: {len(merged['rankings'])}")

    exporter.export_all_to_excel(
        colleges=merged["colleges"],
        courses=merged["courses"],
        admissions=merged["admissions"],
        placements=merged["placements"],
        rankings=merged["rankings"],
        faculty=merged["faculty"],
        scholarships=merged["scholarships"],
        hostels=merged["hostel"],
        reviews=merged["reviews"]
    )
    logger.info("Offline parsing and export complete.")



def _split_urls(n_parts: int):
    """Split college_urls.csv into N equal part files under urls/parts/."""
    if not os.path.exists(COLLEGE_URLS_CSV):
        logger.error(f"CSV not found: {COLLEGE_URLS_CSV}")
        return
    with open(COLLEGE_URLS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    total = len(rows)
    chunk = (total + n_parts - 1) // n_parts  # ceiling division
    parts_dir = os.path.join(os.path.dirname(COLLEGE_URLS_CSV), "parts")
    os.makedirs(parts_dir, exist_ok=True)

    for i in range(n_parts):
        part_rows = rows[i * chunk: (i + 1) * chunk]
        if not part_rows:
            break
        out_path = os.path.join(parts_dir, f"college_urls_part{i + 1}.csv")
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(part_rows)
        logger.info(f"Part {i + 1}: {len(part_rows)} URLs → {out_path}")

    logger.info(f"Split complete: {total} URLs → {n_parts} parts in {parts_dir}")


def main():
    parser = argparse.ArgumentParser(description="Collegedunia Enterprise Scraper & Parser Pipeline")
    parser.add_argument("--stage1-discover", action="store_true", help="Run only Stage 1 college URL discovery")
    parser.add_argument("--stage1-download", action="store_true", help="Run only Stage 1 page downloading")
    parser.add_argument("--stage2-parse", action="store_true", help="Run only Stage 2 HTML offline parsing & export")
    parser.add_argument("--all", action="store_true", default=True, help="Run full end-to-end pipeline (default)")
    parser.add_argument("--limit", type=int, default=1000, help="Limit number of colleges to process")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for incremental discovery and download")
    parser.add_argument("--discover-only", type=int, metavar="N", help="Only discover N URLs and stop (no download/parse)")
    parser.add_argument("--split", type=int, metavar="PARTS", help="Split college_urls.csv into N equal part files under urls/parts/")
    parser.add_argument("--concurrent", action="store_true", help="Use the concurrent/async downloader (fetches a college's subpages in parallel, bounded by config.SUBPAGE_CONCURRENCY). Opt-in — validate on a sample first.")

    args = parser.parse_args()

    # Pick the download implementation once; both share the same signature.
    downloader_fn = run_downloader_concurrent if args.concurrent else run_downloader
    if args.concurrent:
        logger.info("Using CONCURRENT downloader (subpages fetched in parallel).")

    if args.discover_only:
        discover_college_urls(max_colleges=args.discover_only)
    elif args.split:
        _split_urls(args.split)
    elif args.stage1_discover:
        discover_college_urls(max_colleges=args.limit)
    elif args.stage1_download:
        downloader_fn(limit=args.limit)
    elif args.stage2_parse:
        run_parsing_and_export()
    else:
        logger.info("Starting Full End-to-End Scraper Pipeline...")
        total_limit = args.limit
        batch_size = args.batch_size

        if batch_size <= 0:
            batch_size = 300

        # Discover all URLs up front (resumes from last listing page)
        logger.info(f"Stage 1: Discovering up to {total_limit} URLs...")
        discover_college_urls(max_colleges=total_limit)

        # Download in batches of `batch_size` new colleges at a time.
        # NOTE: parsing/export is deliberately deferred until ALL downloads
        # finish. run_parsing_and_export() reloads every JSON file and rewrites
        # the entire Excel workbook, so calling it per-batch is O(N^2) over a
        # run (65 batches would re-export a growing workbook 65 times). Parsing
        # is fast and offline — do it once at the end from the HTML on disk.
        current_batch = 1
        downloaded_any = False
        while True:
            logger.info(f"\n========================================\n"
                        f"BATCH {current_batch}: downloading up to {batch_size} new colleges\n"
                        f"========================================")

            before = len(discover_downloaded_colleges())
            downloader_fn(limit=batch_size)
            after = len(discover_downloaded_colleges())
            new_count = after - before

            if new_count > 0:
                logger.info(f"Downloaded {new_count} new colleges this batch.")
                downloaded_any = True
            else:
                logger.info("No new colleges downloaded. All pending colleges done or CSV exhausted.")
                break

            current_batch += 1

        from config import EXPORTS_EXCEL
        if downloaded_any or not os.path.exists(EXPORTS_EXCEL):
            logger.info("Parsing + exporting once...")
            run_parsing_and_export()

        logger.info("Pipeline Execution Finished.")


if __name__ == "__main__":
    main()

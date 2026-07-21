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

    existing_rank_keys = {
        (r["college_id"], r["ranking_body"], r["ranking_year"])
        for r in existing["rankings"]
    }

    for college_id, slug in new_colleges:
        logger.info(f"Parsing NEW college: {slug} (ID: {college_id})")

        info_file = os.path.join(HTML_DIR, "info", f"{college_id}_{slug}.html")

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
                for r in parser.parse_rankings(placement_html, college_id, extra_html=info_html):
                    key = (r.get("college_id"), r.get("ranking_body"), r.get("ranking_year"))
                    if key not in existing_rank_keys:
                        existing_rank_keys.add(key)
                        new_data["rankings"].append(r)
            except Exception as e:
                logger.error(f"Error parsing placements for {slug}: {e}")

        # Save JSON incrementally after each college (fast)
        exporter.save_to_json(existing["colleges"] + new_data["colleges"], "colleges.json")
        exporter.save_to_json(existing["courses"] + new_data["courses"], "courses.json")
        exporter.save_to_json(existing["admissions"] + new_data["admissions"], "admissions.json")
        exporter.save_to_json(existing["placements"] + new_data["placements"], "placements.json")
        exporter.save_to_json(existing["rankings"] + new_data["rankings"], "rankings.json")
        exporter.save_to_json(existing["faculty"] + new_data["faculty"], "faculty.json")
        exporter.save_to_json(existing["scholarships"] + new_data["scholarships"], "scholarships.json")
        exporter.save_to_json(existing["hostel"] + new_data["hostel"], "hostel.json")
        exporter.save_to_json(existing["reviews"] + new_data["reviews"], "reviews.json")
        # Write individual college Excel only (1 college, fast)
        exporter.export_college_wise_excel(
            new_data["colleges"][-1:],
            new_data["courses"], new_data["admissions"], new_data["placements"],
            new_data["rankings"], new_data["faculty"], new_data["scholarships"],
            new_data["hostel"], new_data["reviews"]
        )
        logger.info(f"Saved college {college_id} ({slug}). Total in JSON: {len(existing['colleges']) + len(new_data['colleges'])}")

    # Write all_colleges.xlsx once after all new colleges are parsed
    if new_data["colleges"]:
        merged = {
            k: existing[k] + new_data[k] for k in existing
        }
        exporter.export_all_to_excel(
            colleges=merged["colleges"], courses=merged["courses"],
            admissions=merged["admissions"], placements=merged["placements"],
            rankings=merged["rankings"], faculty=merged["faculty"],
            scholarships=merged["scholarships"], hostels=merged["hostel"],
            reviews=merged["reviews"], new_colleges_only=[]
        )
        logger.info(f"all_colleges.xlsx updated. Total colleges: {len(merged['colleges'])}")

    logger.info("Offline parsing and export complete.")



def _count_info_files() -> int:
    """Returns number of colleges with a saved info HTML file."""
    info_dir = os.path.join(HTML_DIR, "info")
    if not os.path.exists(info_dir):
        return 0
    return sum(1 for f in os.listdir(info_dir) if f.endswith(".html"))


def _count_skipped() -> int:
    """Returns number of college IDs in the downloader skip list."""
    skip_file = os.path.join(HTML_DIR, ".skipped_ids")
    if not os.path.exists(skip_file):
        return 0
    with open(skip_file) as f:
        return sum(1 for line in f if line.strip())


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
    parser.add_argument("--parse-per-batch", action="store_true", help="Run offline parsing and export to Excel after every batch of downloads instead of waiting until the end.")

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

        current_batch = 1
        total_processed = 0
        downloaded_any = False
        while total_processed < total_limit:
            logger.info(f"\n========================================\n"
                        f"BATCH {current_batch}: discovering + downloading up to {batch_size} new colleges\n"
                        f"========================================")

            # Grow the discovery target each batch (discovery resumes from the
            # last listing page), capped at total_limit.
            discover_college_urls(max_colleges=min(total_processed + batch_size, total_limit))

            before = _count_info_files()
            before_skipped = _count_skipped()
            downloader_fn(limit=batch_size)
            after = _count_info_files()
            after_skipped = _count_skipped()
            new_count = after - before
            skipped_count = after_skipped - before_skipped

            if new_count > 0:
                total_processed += new_count
                downloaded_any = True
                logger.info(f"Downloaded {new_count} new colleges this batch (total {total_processed}).")
                if args.parse_per_batch:
                    logger.info("Incremental parsing and export triggered for batch...")
                    run_parsing_and_export()
            elif skipped_count > 0:
                total_processed += skipped_count
                logger.info(f"Batch skipped {skipped_count} fully-failed college(s) — advancing to next batch (total {total_processed}).")
            else:
                logger.info("No pending colleges remain — all downloaded or skipped. Stopping.")
                break

            current_batch += 1

        # Always produce JSON + Excel at the end of a run (unless we already
        # exported per-batch). Without this the default pipeline downloads but
        # never generates any output.
        if downloaded_any and not args.parse_per_batch:
            logger.info("Downloads finished for this run. Parsing + exporting once...")
            run_parsing_and_export()

        logger.info("Pipeline Execution Finished.")


if __name__ == "__main__":
    main()

import argparse
import os
import re
from typing import List, Dict, Tuple, Any
from config import HTML_DIR, SUBPAGE_MAPPING
from logger import logger
from discovery import discover_college_urls
from downloader import run_downloader
import parser
import exporter

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
                    # Matches <id>_<slug>.html
                    match = re.match(r"^(\d+)_(.+)\.html$", filename)
                    if match:
                        colleges.add((match.group(1), match.group(2)))
    return sorted(list(colleges))

def run_parsing_and_export():
    """Reads all downloaded HTML files, parses them offline, and exports to JSON and Excel."""
    logger.info("Starting Stage 2: Offline parsing and export...")
    
    downloaded = discover_downloaded_colleges()
    if not downloaded:
        logger.warning(f"No downloaded HTML files found under {HTML_DIR}. Run stage 1 first.")
        return
        
    logger.info(f"Found {len(downloaded)} college(s) to parse.")
    
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
        
        # 1. Parse Info
        info_file = os.path.join(HTML_DIR, "info", f"{college_id}_{slug}.html")
        college_url = f"https://collegedunia.com/university/{college_id}-{slug}"
        
        info_data = {}
        if os.path.exists(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    html = f.read()
                info_data = parser.parse_college_info(html, college_id, college_url)
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
                course_rows = parser.parse_courses(html, college_id, college_url)
                all_courses.extend(course_rows)
            except Exception as e:
                logger.error(f"Error parsing courses for {slug}: {e}")
                
        # 3. Parse Admissions
        admissions_file = os.path.join(HTML_DIR, "admissions", f"{college_id}_{slug}.html")
        if os.path.exists(admissions_file):
            try:
                with open(admissions_file, "r", encoding="utf-8") as f:
                    html = f.read()
                adm_data = parser.parse_admissions(html, college_id)
                all_admissions.append(adm_data)
            except Exception as e:
                logger.error(f"Error parsing admissions for {slug}: {e}")
                
        # 4. Parse Placements & Rankings
        placements_file = os.path.join(HTML_DIR, "placements", f"{college_id}_{slug}.html")
        if os.path.exists(placements_file):
            try:
                with open(placements_file, "r", encoding="utf-8") as f:
                    html = f.read()
                placement_data = parser.parse_placements(html, college_id)
                all_placements.append(placement_data)
                
                ranking_data = parser.parse_rankings(html, college_id)
                all_rankings.extend(ranking_data)
            except Exception as e:
                logger.error(f"Error parsing placements for {slug}: {e}")
                
        # 5. Parse Faculty
        faculty_file = os.path.join(HTML_DIR, "faculty", f"{college_id}_{slug}.html")
        if os.path.exists(faculty_file):
            try:
                with open(faculty_file, "r", encoding="utf-8") as f:
                    html = f.read()
                fac_rows = parser.parse_faculty(html, college_id)
                all_faculty.extend(fac_rows)
            except Exception as e:
                logger.error(f"Error parsing faculty for {slug}: {e}")
                
        # 6. Parse Scholarships
        scholarships_file = os.path.join(HTML_DIR, "scholarships", f"{college_id}_{slug}.html")
        if os.path.exists(scholarships_file):
            try:
                with open(scholarships_file, "r", encoding="utf-8") as f:
                    html = f.read()
                schol_rows = parser.parse_scholarships(html, college_id)
                all_scholarships.extend(schol_rows)
            except Exception as e:
                logger.error(f"Error parsing scholarships for {slug}: {e}")
                
        # 7. Parse Hostel
        hostel_file = os.path.join(HTML_DIR, "hostel", f"{college_id}_{slug}.html")
        if os.path.exists(hostel_file):
            try:
                with open(hostel_file, "r", encoding="utf-8") as f:
                    html = f.read()
                hostel_data = parser.parse_hostel(html, college_id)
                all_hostels.append(hostel_data)
            except Exception as e:
                logger.error(f"Error parsing hostel for {slug}: {e}")
                
        # 8. Parse Reviews
        reviews_file = os.path.join(HTML_DIR, "reviews", f"{college_id}_{slug}.html")
        if os.path.exists(reviews_file):
            try:
                with open(reviews_file, "r", encoding="utf-8") as f:
                    html = f.read()
                rev_rows = parser.parse_reviews(html, college_id)
                all_reviews.extend(rev_rows)
            except Exception as e:
                logger.error(f"Error parsing reviews for {slug}: {e}")
                
    # Compile and export
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
    parser.add_argument("--limit", type=int, default=1, help="Limit number of colleges to process during download")
    
    args = parser.parse_args()
    
    if args.stage1_discover:
        discover_college_urls(max_colleges=5)
    elif args.stage1_download:
        run_downloader(limit=args.limit)
    elif args.stage2_parse:
        run_parsing_and_export()
    else:
        # Run everything
        logger.info("Starting Full End-to-End Scraper Pipeline...")
        discover_college_urls(max_colleges=5)
        run_downloader(limit=args.limit)
        run_parsing_and_export()
        logger.info("Pipeline Execution Finished.")

if __name__ == "__main__":
    main()

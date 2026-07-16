import json
import os
import re
import pandas as pd
from typing import List, Dict, Any
from config import JSON_DIR, EXPORTS_EXCEL, COLLEGE_EXPORTS_DIR
from logger import logger

def save_to_json(data: List[Dict[str, Any]], filename: str):
    """Saves a list of dictionaries as a JSON file in json_data/."""
    os.makedirs(JSON_DIR, exist_ok=True)
    filepath = os.path.join(JSON_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, default=str)
        logger.info(f"Saved {len(data)} records to JSON: {filepath}")
    except Exception as e:
        logger.error(f"Failed to save JSON to {filepath}: {e}")

def export_all_to_excel(
    colleges: List[Dict[str, Any]],
    courses: List[Dict[str, Any]],
    admissions: List[Dict[str, Any]],
    placements: List[Dict[str, Any]],
    rankings: List[Dict[str, Any]],
    faculty: List[Dict[str, Any]],
    scholarships: List[Dict[str, Any]],
    hostels: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]]
):
    """
    Saves lists of dicts directly to JSON files first, 
    then compiles them into a single Excel file with multiple sheets.
    """
    logger.info("Starting data export process...")
    
    # 1. Save all datasets to JSON files first as backup
    save_to_json(colleges, "colleges.json")
    save_to_json(courses, "courses.json")
    save_to_json(admissions, "admissions.json")
    save_to_json(placements, "placements.json")
    save_to_json(rankings, "rankings.json")
    save_to_json(faculty, "faculty.json")
    save_to_json(scholarships, "scholarships.json")
    save_to_json(hostels, "hostel.json")
    save_to_json(reviews, "reviews.json")
    
    # 2. Convert lists of dicts to DataFrames
    dfs = {
        "Colleges": pd.DataFrame(colleges),
        "Courses": pd.DataFrame(courses),
        "Admissions": pd.DataFrame(admissions),
        "Placements": pd.DataFrame(placements),
        "Rankings": pd.DataFrame(rankings),
        "Faculty": pd.DataFrame(faculty),
        "Scholarships": pd.DataFrame(scholarships),
        "Hostel": pd.DataFrame(hostels),
        "Reviews": pd.DataFrame(reviews)
    }
    
    # Create export directory
    os.makedirs(os.path.dirname(EXPORTS_EXCEL), exist_ok=True)
    
    # 3. Write using pd.ExcelWriter
    try:
        with pd.ExcelWriter(EXPORTS_EXCEL, engine="openpyxl") as writer:
            for sheet_name, df in dfs.items():
                if df.empty:
                    # Create an empty DataFrame with standard columns to ensure sheet is created
                    logger.warning(f"DataFrame for sheet '{sheet_name}' is empty. Generating empty template.")
                    df = pd.DataFrame(columns=["college_id", "status"])
                    df.loc[0] = ["No Data Available", "Check Logs"]
                
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Format sheet columns to auto-fit
                workbook = writer.book
                worksheet = writer.sheets[sheet_name]
                for col in worksheet.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = col[0].column_letter
                    worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)
                    
        logger.info(f"Excel workbook compiled and saved successfully to: {EXPORTS_EXCEL}")
        
        # Call college-wise exports
        export_college_wise_excel(
            colleges, courses, admissions, placements, rankings, faculty, scholarships, hostels, reviews
        )
        
    except Exception as e:
        logger.error(f"Failed to generate Excel workbook: {e}")
        raise e

def export_college_wise_excel(
    colleges: List[Dict[str, Any]],
    courses: List[Dict[str, Any]],
    admissions: List[Dict[str, Any]],
    placements: List[Dict[str, Any]],
    rankings: List[Dict[str, Any]],
    faculty: List[Dict[str, Any]],
    scholarships: List[Dict[str, Any]],
    hostels: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]]
):
    """Generates individual college Excel sheets under COLLEGE_EXPORTS_DIR."""
    if not colleges:
        logger.warning("No colleges data available for college-wise Excel export.")
        return
        
    os.makedirs(COLLEGE_EXPORTS_DIR, exist_ok=True)
    
    # Group other datasets by college_id to make filtering efficient
    from collections import defaultdict
    
    courses_by_id = defaultdict(list)
    for x in courses:
        courses_by_id[x.get("college_id")].append(x)
        
    admissions_by_id = defaultdict(list)
    for x in admissions:
        admissions_by_id[x.get("college_id")].append(x)
        
    placements_by_id = defaultdict(list)
    for x in placements:
        placements_by_id[x.get("college_id")].append(x)
        
    rankings_by_id = defaultdict(list)
    for x in rankings:
        rankings_by_id[x.get("college_id")].append(x)
        
    faculty_by_id = defaultdict(list)
    for x in faculty:
        faculty_by_id[x.get("college_id")].append(x)
        
    scholarships_by_id = defaultdict(list)
    for x in scholarships:
        scholarships_by_id[x.get("college_id")].append(x)
        
    hostels_by_id = defaultdict(list)
    for x in hostels:
        hostels_by_id[x.get("college_id")].append(x)
        
    reviews_by_id = defaultdict(list)
    for x in reviews:
        reviews_by_id[x.get("college_id")].append(x)
        
    for college in colleges:
        cid = college.get("college_id")
        if not cid:
            continue
            
        # Get college slug from its URL
        slug = "college"
        url = college.get("url", "")
        match = re.search(r"/(colleges?|university)/(\d+)-([^/?#]+)", url)
        if match:
            slug = match.group(3)
        else:
            name_clean = re.sub(r"[^a-zA-Z0-9\s\-]", "", college.get("name", "")).strip().lower()
            slug = re.sub(r"[\s\-]+", "-", name_clean)
            
        filename = f"{cid}_{slug}.xlsx"
        filepath = os.path.join(COLLEGE_EXPORTS_DIR, filename)
        
        # Build sheets data
        college_dfs = {
            "Colleges": pd.DataFrame([college]),
            "Courses": pd.DataFrame(courses_by_id[cid]),
            "Admissions": pd.DataFrame(admissions_by_id[cid]),
            "Placements": pd.DataFrame(placements_by_id[cid]),
            "Rankings": pd.DataFrame(rankings_by_id[cid]),
            "Faculty": pd.DataFrame(faculty_by_id[cid]),
            "Scholarships": pd.DataFrame(scholarships_by_id[cid]),
            "Hostel": pd.DataFrame(hostels_by_id[cid]),
            "Reviews": pd.DataFrame(reviews_by_id[cid])
        }
        
        if os.path.exists(filepath):
            logger.info(f"Skipping existing college Excel: {filepath}")
            continue

        try:
            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                for sheet_name, df in college_dfs.items():
                    if df.empty:
                        df = pd.DataFrame(columns=["college_id", "status"])
                        df.loc[0] = [cid, "No Data Available"]
                    
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Format sheet columns to auto-fit
                    worksheet = writer.sheets[sheet_name]
                    for col in worksheet.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        col_letter = col[0].column_letter
                        worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)
            logger.info(f"Saved college-wise Excel sheet: {filepath}")
        except Exception as e:
            logger.error(f"Failed to generate individual Excel for college {cid}: {e}")

# Setup & Collaboration Guide

This guide explains how to install, configure, and run the scraper on any laptop — including how to split work across 6 different laptops to run in parallel.

---

## Required Libraries

Install Python 3.10+ first, then run:

```bash
pip install playwright beautifulsoup4 pandas openpyxl
playwright install chromium
```

| Library | Purpose |
| :--- | :--- |
| `playwright` | Headless browser — downloads dynamic college pages |
| `beautifulsoup4` | HTML parser — extracts structured data offline |
| `pandas` | Data manipulation and Excel export |
| `openpyxl` | Excel `.xlsx` file writer (used by pandas) |

---

## Folder Structure

```
one-co/
├── config.py                 # Paths, timeouts, delay settings
├── logger.py                 # Console + file logger
├── discovery.py              # Stage 1: Crawls listing pages to collect URLs
├── downloader.py             # Stage 1: Downloads subpages via Playwright
├── college_parser.py         # Stage 2: Parses HTML into structured dicts
├── exporter.py               # Stage 2: Writes JSON + Excel files
├── main.py                   # CLI runner — all commands go through here
├── status.py                 # Quick status check (counts, pending, etc.)
├── SETUP.md                  # This file
├── urls/
│   ├── college_urls.csv      # Master URL list (all discovered colleges)
│   ├── .discovery_state      # Last listing page reached (auto-managed)
│   └── parts/                # Split URL files for multi-laptop work
│       ├── college_urls_part1.csv
│       ├── college_urls_part2.csv
│       ├── college_urls_part3.csv
│       ├── college_urls_part4.csv
│       ├── college_urls_part5.csv
│       └── college_urls_part6.csv
├── html/                     # Downloaded raw HTML (9 subpages per college)
│   ├── info/
│   ├── courses/
│   ├── admissions/
│   ├── placements/
│   ├── reviews/
│   ├── faculty/
│   ├── scholarships/
│   ├── hostel/
│   └── cutoff/
├── json_data/                # Parsed structured data (JSON backup)
│   ├── colleges.json
│   ├── courses.json
│   ├── admissions.json
│   ├── placements.json
│   ├── rankings.json
│   ├── faculty.json
│   ├── scholarships.json
│   ├── hostel.json
│   └── reviews.json
├── exports/
│   ├── all_colleges.xlsx     # Consolidated Excel workbook
│   └── colleges/             # Per-college individual Excel files
└── logs/
    └── scraper.log
```

---

## Step-by-Step: Full Workflow (One Machine)

### Step 1 — Discover all URLs
```bash
python main.py --discover-only 19455
```
Collegedunia has ~19,455 colleges total. Discovery will stop automatically when all pages are exhausted (~19,455 URLs). Already-discovered URLs are preserved — safe to re-run.

### Step 2 — Split into 6 parts (for 6 laptops)
```bash
python main.py --split 6
```
Creates 6 files in `urls/parts/` (~3,243 URLs each):
- `college_urls_part1.csv` — URLs 1–3243
- `college_urls_part2.csv` — URLs 3244–6486
- `college_urls_part3.csv` — URLs 6487–9729
- `college_urls_part4.csv` — URLs 9730–12972
- `college_urls_part5.csv` — URLs 12973–16215
- `college_urls_part6.csv` — URLs 16216–19455

### Step 3 — Share the folder
Share the entire `one-co/` folder (via Google Drive, USB, or network share).
Each laptop gets the same folder with its assigned part file.

---

## Step-by-Step: Per-Laptop Setup

### 1. Install dependencies
On each laptop, install Python 3.10+ and run:
```bash
pip install playwright beautifulsoup4 pandas openpyxl
playwright install chromium
```

### 2. Replace the master CSV with your assigned part
Each laptop should copy its assigned part file over the master CSV file:

**Laptop 1:**
```bash
copy urls\parts\college_urls_part1.csv urls\college_urls.csv
```
**Laptop 2:**
```bash
copy urls\parts\college_urls_part2.csv urls\college_urls.csv
```
**Laptop 3:**
```bash
copy urls\parts\college_urls_part3.csv urls\college_urls.csv
```
**Laptop 4:**
```bash
copy urls\parts\college_urls_part4.csv urls\college_urls.csv
```
**Laptop 5:**
```bash
copy urls\parts\college_urls_part5.csv urls\college_urls.csv
```
**Laptop 6:**
```bash
copy urls\parts\college_urls_part6.csv urls\college_urls.csv
```

### 3. Clear existing download state (important!)
Each laptop starts fresh — make sure to delete any existing `html/` and `json_data/` contents on laptops 2–6 if you copied the entire repository with already downloaded files, so they only process their own part.

### 4. Run the scraper on each laptop
```bash
python main.py --limit 3500 --batch-size 50
```
Each laptop will download and parse its ~3,243 colleges independently.

---

## Merging Results (After All Laptops Finish)

Once all 6 laptops finish, collect the `json_data/` folder from each laptop. 

1. On the main machine, merge the JSON arrays from each laptop's JSON files (e.g. combine all elements from `colleges.json` from Laptop 1 to Laptop 6 into a single master `colleges.json` list, and repeat for all other JSON files: `courses.json`, `admissions.json`, etc.).
2. Put the merged master JSON files under your master `json_data/` folder.
3. Run the parser command to generate the consolidated Excel file:
```bash
python main.py --stage2-parse
```
This regenerates the consolidated Excel file `exports/all_colleges.xlsx` and individual college sheets under `exports/colleges/` using the combined JSON data.

---

## Useful Commands

| Command | What it does |
| :--- | :--- |
| `python status.py` | Show counts: CSV URLs, downloaded, pending, JSON records |
| `python main.py --discover-only 19455` | Discover up to 19,455 URLs |
| `python main.py --split 6` | Split CSV into 6 part files |
| `python main.py --stage1-download --limit 50` | Download next 50 pending colleges |
| `python main.py --stage2-parse` | Parse all downloaded HTML → JSON + Excel |
| `python main.py --limit 3500 --batch-size 50` | Full loop: download + parse in batches of 50 |

---

## Time Estimates

| Batch size | Time per batch | 3,243 colleges total |
| :--- | :--- | :--- |
| 10 colleges | ~8–10 min | ~26–32 hours per laptop |
| 50 colleges | ~40–50 min | ~26–32 hours per laptop |

> Each college = 9 subpages × ~25 sec + 2 sec delay = ~4–5 min per college.
> Running 6 laptops in parallel reduces the total pipeline run time from ~400 hours down to ~26–32 hours (~1.5 days).

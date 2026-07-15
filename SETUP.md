# Setup & Collaboration Guide

This guide explains how to install, configure, and run the scraper on any laptop — including how to split work across multiple machines.

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
│       └── ...
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
python main.py --discover-only 15000
```
Collegedunia has ~10,000 colleges total. Discovery will stop automatically when all pages are exhausted (~9,999 URLs). Already-discovered URLs are preserved — safe to re-run.

### Step 2 — Split into 5 parts (for 5 laptops)
```bash
python main.py --split 5
```
Creates 5 files in `urls/parts/` (~2,000 URLs each):
- `college_urls_part1.csv` — URLs 1–2000
- `college_urls_part2.csv` — URLs 2001–4000
- `college_urls_part3.csv` — URLs 4001–6000
- `college_urls_part4.csv` — URLs 6001–8000
- `college_urls_part5.csv` — URLs 8001–9999

### Step 3 — Share the folder
Share the entire `one-co/` folder (via Google Drive, USB, or network share).
Each laptop gets the same folder with its assigned part file.

---

## Step-by-Step: Per-Laptop Setup

### 1. Install dependencies
```bash
pip install playwright beautifulsoup4 pandas openpyxl
playwright install chromium
```

### 2. Replace the master CSV with your assigned part
Each laptop should copy its assigned part file over the master CSV:

**Laptop 1:**
```bash
copy urls\parts\college_urls_part1.csv urls\college_urls.csv
```
**Laptop 2:**
```bash
copy urls\parts\college_urls_part2.csv urls\college_urls.csv
```
*(Repeat for laptops 3, 4, 5 with their respective part files)*

### 3. Clear existing download state (important!)
Each laptop starts fresh — delete any existing HTML and JSON from the shared folder:
```bash
# Only do this on laptops 2–5 (not the main machine that already has 581 done)
# Delete html/ and json_data/ contents before starting
```

### 4. Run the scraper on each laptop
```bash
python main.py --limit 2000 --batch-size 10
```
Each laptop will download and parse its ~2,000 colleges independently.

---

## Merging Results (After All Laptops Finish)

Collect the `json_data/` folder from each laptop. Then on the main machine, manually merge the JSON arrays from each `colleges.json`, `courses.json`, etc. into the master `json_data/` files, then run:

```bash
python main.py --stage2-parse
```
This regenerates the consolidated `exports/all_colleges.xlsx` from the merged JSON.

---

## Useful Commands

| Command | What it does |
| :--- | :--- |
| `python status.py` | Show counts: CSV URLs, downloaded, pending, JSON records |
| `python main.py --discover-only 15000` | Discover up to 15,000 URLs |
| `python main.py --split 5` | Split CSV into 5 part files |
| `python main.py --stage1-download --limit 50` | Download next 50 pending colleges |
| `python main.py --stage2-parse` | Parse all downloaded HTML → JSON + Excel |
| `python main.py --limit 2000 --batch-size 10` | Full loop: download + parse in batches of 10 |

---

## Time Estimates

| Batch size | Time per batch | 3,000 colleges total |
| :--- | :--- | :--- |
| 10 colleges | ~8–10 min | ~16–20 hours per laptop |
| 50 colleges | ~40–50 min | ~16–20 hours per laptop |

> Each college = 9 subpages × ~25 sec + 2 sec delay = ~4–5 min per college.
> Total: ~9,999 colleges × ~4 min = ~666 hours single machine.
> Running 5 laptops in parallel reduces total time to ~130–140 hours (~5–6 days).

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
python main.py --limit 3500 --batch-size 100
```
Each laptop will download its ~3,243 colleges, then parse + export **once** at the
end (parsing is offline and fast; re-exporting the growing Excel workbook after
every batch was quadratic and has been removed).

**Faster / more robust: decouple the two stages.** Download everything first, then
parse once. This survives interruptions (HTML stays on disk) and avoids any
per-batch export cost:
```bash
python main.py --stage1-download --limit 3500   # download only (repeat-safe; resumes)
python main.py --stage2-parse                    # parse all HTML → JSON + Excel, once
```

> ⚠️ **Geo-restriction — read this first.** Collegedunia is served via CloudFront
> and blocks requests from outside India with an HTTP **403** page. If a laptop is
> not on an Indian IP, every page returns a ~1 KB error page. The downloader now
> **detects these blocks and refuses to save them** (the college stays *pending*
> instead of being silently marked done), so you won't corrupt the dataset — but
> that laptop will make zero progress. Run from India, or use an India-based
> VPN/proxy. Verify with `python status.py` after the first batch: if "Downloaded"
> stays at 0 and the log shows `Blocked/error HTTP 403`, the IP is the problem.

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

Original: each college = 9 subpages × ~25 sec + 2 sec delay ≈ **4–5 min/college**
→ ~26–32 hours per laptop, ~400 hours total across the pipeline.

### Speed optimizations applied (per-request, lossless)

These cut the per-college time without changing what data is captured:

| Optimization | Effect |
| :--- | :--- |
| **Block images / fonts / media** (`config.BLOCK_RESOURCE_TYPES`) | Pages fetch only the HTML/text we actually parse — the single biggest safe win. Stylesheets are kept (Playwright needs CSS to compute element visibility). |
| **Fixed the dead scroll-break** | Heavy pages used to always burn the full 10 × 0.8 s = 8 s of scrolling. The loop now exits as soon as the page height stops growing. |
| **Trimmed fixed waits** | Hydration wait 2.0 s → 1.2 s (`HYDRATION_WAIT_MS`); base delay 2 s → 1 s (`DELAY_BETWEEN_REQUESTS`). |
| **Parse once, not per batch** | Removed the quadratic re-export of the whole Excel workbook after every batch. |

Together these should roughly **halve** per-request time. All knobs live in
`config.py` — tune them per your bandwidth and how aggressively the site rate-limits.

> **Validate before a full run.** These speed knobs *can* silently drop lazy-loaded
> data if pushed too hard. On an India-located laptop that can actually reach the
> site, download ~5 colleges, run `--stage2-parse`, and confirm all 9 subpages
> populate in the JSON. (This could not be verified from a geo-blocked machine.)

### Next lever: concurrency (test before trusting)

The current downloader is fully **sequential** — one subpage at a time. Real
parallelism (downloading a college's 9 subpages, or several colleges, at once) is
the path to another big speed-up, but it also raises the risk of CloudFront
CAPTCHAs / IP bans — remember 6 laptops each firing N concurrent requests hit one
host simultaneously. If you pursue it, wire up the already-defined
`config.CONCURRENCY_LIMIT` (start at 3–4), test on a small sample, and watch for
403/429 before scaling.

> Running 6 laptops in parallel already reduces total run time from ~400 h to
> ~26–32 h; the optimizations above bring each laptop down further.

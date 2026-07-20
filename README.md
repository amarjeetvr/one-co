# Collegedunia Enterprise Scraper & Parsing Pipeline

A modular, production-grade 2-stage web scraping and parsing pipeline for `collegedunia.com`. The pipeline is written entirely in Python, utilizing **Playwright** to crawl and download page assets dynamically, and **BeautifulSoup** + **Pandas** to extract and organize structured datasets offline.

---

## Key Features

1. **Robust 2-Stage Architecture:**
   - **Stage 1 (Downloader):** Downloads raw HTML subpages. Handles dynamic overlays, cookie consents, lazy-loaded lists, and clicks expand buttons ("View More", "Read More") before page-write. Includes rotational request delays to be polite.
   - **Stage 2 (Parser):** Offline processing. Reads raw downloaded HTML files from disk and processes them completely offline, avoiding redundant network request blocks.
2. **Built-in Resume Support:** Bypasses downloading any page asset that already exists locally on disk, ensuring safety, speed, and recovery from connection interruptions.
3. **Dual Structured Exports:**
   - Consolidated JSON backups stored under `json_data/`.
   - Consolidated Excel workbook `exports/all_colleges.xlsx` containing all colleges.
   - Separate, formatted individual college sheets stored under `exports/colleges/<college_id>_<slug>.xlsx`.
4. **Dynamic Data Classification:** Automatically extracts and organizes B.Tech, M.Tech, M.Sc, MBA, and other custom courses; infers duration, course levels (UG/PG/Doctorate), and exams (JEE, GATE, CAT, etc.) dynamically.
5. **Performance-Tuned Downloads:** Blocks parse-irrelevant assets (images/fonts/media), trims fixed waits, and exits scrolling early once the page settles — roughly halving per-page time with no data loss. All knobs live in `config.py`. An optional **concurrent** downloader (`--concurrent`) fetches a college's 9 subpages in parallel.
6. **Honest Failure Handling:** Distinguishes a **404** (page genuinely absent — normal for missing subpages) from a **403/429 block** (kept *pending* for retry), and refuses to save CloudFront/captcha error pages so the dataset is never poisoned. `python status.py` audits subpage completeness.

> ⚠️ **Geo-restriction:** `collegedunia.com` is served via CloudFront and returns **HTTP 403** to requests from outside India. Run from an Indian IP (or India-based VPN/proxy), or every page is blocked. See **[SETUP.md](SETUP.md)** for details and the multi-laptop parallel workflow.

---

## Folder Structure

```
one-co/
├── config.py                 # Configuration (paths, timeouts, delays, speed & concurrency knobs)
├── logger.py                 # Core log formatter (writes to console & scraper.log)
├── discovery.py              # Stage 1: URL crawler via listing scrolls
├── downloader.py             # Stage 1: Sequential subpage downloader via Playwright
├── downloader_async.py       # Stage 1: Optional concurrent downloader (--concurrent)
├── college_parser.py         # Stage 2: BS4 offline parser for sheets
├── exporter.py               # Stage 2: JSON and Excel file exporter
├── main.py                   # Command-line runner coordinating the stages
├── status.py                 # Status check: counts, pending, subpage-completeness audit
├── requirements.txt          # Python packages
├── SETUP.md                  # Multi-laptop setup, tuning & operational guide
├── urls/
│   ├── college_urls.csv      # Discovered seed URLs to download
│   └── parts/                # Split URL files for multi-laptop parallel runs
├── html/                     # Raw HTML, 9 subpages per college (info, courses, hostel, placements, …)
├── json_data/                # Secondary structured JSON data backup
├── exports/                  # Excel Exports
│   ├── all_colleges.xlsx     # Consolidated sheets workbook
│   └── colleges/             # College-wise individual spreadsheets
└── logs/
    └── scraper.log           # Output logs
```

---

## Quick Start Guide

### 1. Installation

Set up a virtual environment and install the required dependencies:

```bash
# Clone the repository and navigate in
cd one-co

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Install Playwright browser dependencies
playwright install chromium
```

*(Note: Dependencies include `beautifulsoup4`, `pandas`, `openpyxl`, and `playwright`)*

---

### 2. Execution Workflows

#### Workflow A: Run the Pipeline End-to-End (Simple)
To automatically discover college URLs, download pages, and generate the Excel export in one go (parsing runs **once at the end**):
```bash
# Crawls directories, downloads new colleges, and exports sheets (limit 10 colleges)
python main.py --all --limit 10

# Optional flags:
#   --concurrent         fetch each college's 9 subpages in parallel (faster; validate first)
#   --parse-per-batch    export the Excel after every batch instead of once at the end
#   --batch-size 100     colleges downloaded per batch (default 50)
```

> Resumable: already-downloaded colleges are skipped, so re-running continues where it stopped. If a batch is blocked (403/429) the run stops early and says so — just re-run to resume.

---

#### Workflow B: Step-by-Step Crawling & Exporting (Recommended for Production)

##### **Step 1: URL Discovery**
Crawls Collegedunia directories (like `/india-colleges`) to collect target URLs. This will automatically check for duplicates and write unique links to `urls/college_urls.csv`.
```bash
python main.py --stage1-discover
```
*Note: You can also manually add specific Collegedunia URLs to `urls/college_urls.csv` at any time!*

##### **Step 2: Subpage Downloading**
Downloads the required subpage routes (e.g. Courses & Fees, Placement, Reviews, Hostel, Scholarships) for the URLs in the CSV list. 
```bash
# Download HTML pages for the first 10 colleges in the CSV list
python main.py --stage1-download --limit 10

# Or download each college's subpages concurrently (faster — see SETUP.md before scaling):
python main.py --stage1-download --limit 10 --concurrent
```
*(Tip: Already downloaded colleges are skipped automatically, allowing safe retries and resume runs. `HTTP 404` lines are normal — they mean a subpage simply doesn't exist for that college; only `Blocked/error HTTP 403/429` indicates a block.)*

##### **Step 3: Offline Parsing & Excel Generation**
Extracts data from the raw HTML files on disk, creates JSON records, and compiles the Excel workbooks:
```bash
python main.py --stage2-parse
```
This updates the consolidated file `exports/all_colleges.xlsx` and creates individual college sheets under `exports/colleges/`.

---

#### Workflow C: Scale Across Multiple Laptops

For the full ~19,455-college run, split the master URL list into parts and run each part on a separate machine:
```bash
python main.py --discover-only 19455   # discover all URLs
python main.py --split 6               # split into urls/parts/college_urls_part1..6.csv
python status.py                       # counts, pending, and subpage-completeness audit
```
See **[SETUP.md](SETUP.md)** for the complete per-laptop setup, result-merging, tuning knobs, and time estimates.

---

## Output Sheets & Mapped Data

Every Excel workbook contains the following **9 structured sheets**:

| Sheet Name | Extracted Metrics |
| :--- | :--- |
| **Colleges** | Name, Ownership (Public/Private), Type, Established Year, Accreditation, Affiliation, NIRF/QS Ranking, City, State, Contacts |
| **Courses** | Degree, Course Name, Specialization, Total Fees, Duration, Type (Full Time/Part Time), Eligibility, Entrance Exams, Level (UG/PG/PhD) |
| **Admissions** | Selection Process, Eligibility criteria, Accepted Exams, Deadlines, Dates |
| **Placements** | Highest Packages, Average Packages, Median Packages, Placement %, Top Recruiters list |
| **Rankings** | Ranking Body, Rank, Ranking Year |
| **Faculty** | Faculty Name, Designation, Department |
| **Scholarships** | Scholarship Name, Eligibility Rules, Amount |
| **Hostel** | Hostel Fees, Facilities |
| **Reviews** | Student reviewer name, Rating score (1-5), Review text |

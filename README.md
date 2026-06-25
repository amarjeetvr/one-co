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

---

## Folder Structure

```
one-co/
├── config.py                 # Configuration settings (paths, timeouts, paths)
├── logger.py                 # Core log formatter (writes to console & scraper.log)
├── discovery.py              # Stage 1: URL crawler via listing scrolls
├── downloader.py             # Stage 1: Dynamic subpage downloader via Playwright
├── parser.py                 # Stage 2: BS4 offline parser for sheets
├── exporter.py               # Stage 2: JSON and Excel file exporter
├── main.py                   # Command-line runner coordinating the stages
├── requirements.txt          # Python packages
├── urls/
│   └── college_urls.csv      # Discovered seed URLs to download
├── html/                     # Raw pages directories (info, courses, hostel, placements, etc.)
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
To automatically discover college URLs, download pages, and generate separate Excel files in one go:
```bash
# Crawls directories, downloads new colleges, and exports sheets (limit 10 colleges)
python main.py --all --limit 10
```

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
```
*(Tip: Already downloaded colleges are skipped automatically, allowing safe retries and resume runs).*

##### **Step 3: Offline Parsing & Excel Generation**
Extracts data from the raw HTML files on disk, creates JSON records, and compiles the Excel workbooks:
```bash
python main.py --stage2-parse
```
This updates the consolidated file `exports/all_colleges.xlsx` and creates individual college sheets under `exports/colleges/`.

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

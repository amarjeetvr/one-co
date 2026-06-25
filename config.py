import os

# Base Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URLS_DIR = os.path.join(BASE_DIR, "urls")
HTML_DIR = os.path.join(BASE_DIR, "html")
JSON_DIR = os.path.join(BASE_DIR, "json_data")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Files
COLLEGE_URLS_CSV = os.path.join(URLS_DIR, "college_urls.csv")
EXPORTS_EXCEL = os.path.join(EXPORTS_DIR, "all_colleges.xlsx")
COLLEGE_EXPORTS_DIR = os.path.join(EXPORTS_DIR, "colleges")
LOG_FILE = os.path.join(LOGS_DIR, "scraper.log")

# Playwright Browser Settings
HEADLESS = True
TIMEOUT = 30000  # 30 seconds
NAVIGATION_TIMEOUT = 60000  # 60 seconds

# Scraper Settings
CONCURRENCY_LIMIT = 2  # Keep concurrency low to prevent detection and rate limiting
DELAY_BETWEEN_REQUESTS = 2.0  # seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0

# Subpages to download for each college
SUBPAGE_MAPPING = {
    "info": "",  # Base URL
    "courses": "/courses-fees",
    "admissions": "/admission",
    "placements": "/placement",
    "reviews": "/reviews",
    "faculty": "/faculty",
    "scholarships": "/scholarship",
    "hostel": "/hostel",
    "cutoff": "/cutoff"
}

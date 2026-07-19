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
DELAY_BETWEEN_REQUESTS = 1.0  # seconds (base; a small random jitter is added on top)
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0

# --- Speed tuning ---------------------------------------------------------
# We only ever parse the *text* of the DOM offline, so downloading images,
# fonts, media and (optionally) tracking scripts is pure waste. Blocking them
# is the single biggest safe speed-up: pages load far faster and use a
# fraction of the bandwidth, with zero loss of parsed data.
# NOTE: stylesheets are intentionally NOT blocked — Playwright computes
# element visibility (used by the scroll/expand logic) from CSS.
BLOCK_RESOURCE_TYPES = {"image", "media", "font"}

# Milliseconds to wait after DOMContentLoaded for client-side hydration.
HYDRATION_WAIT_MS = 1200

# Max gradual-scroll steps used to trigger lazy loading. The loop now exits
# early once the page height stops growing, so this is just an upper bound.
MAX_SCROLL_STEPS = 10
SCROLL_STEP_WAIT_MS = 600

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

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
# Base delay between requests. CloudFront on this host rate-limits by IP, so
# this is the primary anti-block lever — politeness IS throughput here (being
# blocked is the slowest outcome). Raise it if you still see 403s; lower it
# only after a sample run stays clean. A small random jitter is added on top.
DELAY_BETWEEN_REQUESTS = 2.5  # seconds

# --- Anti-block / retry (403 / 429 rate-limit handling) ------------------
# When the site rate-limits us it returns one of these statuses. Instead of
# giving up immediately, wait and retry — but with a LONG backoff, because a
# short retry just hammers the host during its cool-down and gets us blocked
# harder. `Retry-After` from the response is honored when present.
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0
RETRY_STATUSES = {403, 429, 503}
RETRY_BASE_DELAY = 20.0  # seconds; attempt N waits RETRY_BASE_DELAY * BACKOFF_FACTOR**N

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

# --- Concurrency (async downloader, opt-in via `--concurrent`) -----------
# Max subpages fetched at the same time within ONE browser context. This is
# the number of simultaneous requests that hit collegedunia per laptop, so
# keep it modest — remember 6 laptops multiply this. Start at 3–4 and only
# raise it after confirming a sample run doesn't trigger 403/429 blocks.
# Set to 1 to effectively serialize (equivalent to the sync path).
#
# ⚠️ EVIDENCE FROM THE FIELD: on Indian IPs the sequential path worked but the
# concurrent path got 403-blocked — i.e. CloudFront here rate-limits by request
# burst, not by browser fingerprint. So `--concurrent` is OFF by default and
# this is capped LOW. Raise it only if a sample run stays 403-free.
SUBPAGE_CONCURRENCY = 2
# Milliseconds to stagger the launch of concurrent subpage requests, so a
# college's subpages don't all hit the host in the same instant.
REQUEST_STAGGER_MS = 500

# --- Light stealth (cheap insurance) -------------------------------------
# The block is rate-based, not fingerprint-based, so this is NOT the main fix —
# just low-cost hardening: hide the automation flag so a headless run looks a
# bit less scripted. See downloader.apply_stealth().
STEALTH = True
ACCEPT_LANGUAGE = "en-IN,en;q=0.9"

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

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
Each laptop discovers + downloads its colleges in batches, then parses + exports
**once at the end** (parsing is offline and fast; re-exporting the growing Excel
workbook after every batch was quadratic and has been removed). Add
`--parse-per-batch` if you want an incremental Excel after every batch instead
(useful to watch progress, at the cost of repeated exports).

If a batch makes no progress, the run now reports *why* honestly:
- **all pending done** → `No pending colleges remain — all downloaded. Stopping.`
- **blocked / stalled** → `Batch made no progress, but N still pending … Stopping
  early; re-run to resume.` (It no longer falsely claims the pipeline "Finished"
  when a 403/429 window stalled it — just re-run to pick up where it left off.)

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

> ℹ️ **`HTTP 404` in the logs is usually normal — not an error.** Many colleges
> simply do not have every subpage (no `/hostel`, `/cutoff`, `/scholarship`,
> `/faculty`, …). The downloader now classifies responses instead of lumping them
> together:
> - **404 / 410 on a subpage** → logged at `INFO`: *"subpage 'hostel' does not exist
>   for this college — skipping (normal, not an error)."* No data is lost.
> - **404 / 410 on the base page** (bare `/college/{id}-{slug}`) → logged at
>   `WARNING` as `NOT FOUND … no data captured`: that college was removed from the
>   site since discovery. These are rare; grep for `NOT FOUND` to count them.
> - **403 / 429 / 5xx** → logged at `ERROR` as `Blocked/error` and kept *pending*
>   for a re-run (a real block/rate-limit, not a missing page).
>
> So `grep 'HTTP 404' logs/scraper.log` and check the URL suffix: suffix present =
> harmless missing subpage; bare base URL = a genuinely removed college.

> ⚠️ **Known limitation — partial-download holes.** A college is marked "done" as
> soon as its **info** page is saved; the other 8 subpages are *not* re-checked. If
> info saves but a sibling subpage fails (a transient 403/429/timeout), that college
> is skipped forever with missing data. The guards prevent saving *garbage*, but not
> marking a college *complete-while-incomplete*. **Concurrency makes this more
> likely** (a parallel burst is more prone to a partial rate-limit than a spaced-out
> sequential run). Mitigations:
> - `python status.py` now prints a **subpage completeness audit** — colleges with
>   fewer than 9 subpages are flagged. Run it after each batch.
> - Some subpages are legitimately absent (a college with no `/cutoff`), so a partial
>   count isn't always an error — spot-check flagged colleges in a browser.
> - **Follow-up fix (not yet implemented):** track per-subpage failures and retry
>   only the missing ones, distinguishing "failed" from "legitimately absent."

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
| `python status.py` | Show counts + subpage-completeness audit (flags partial colleges) |
| `python main.py --discover-only 19455` | Discover up to 19,455 URLs and stop |
| `python main.py --split 6` | Split CSV into 6 part files |
| `python main.py --stage1-download --limit 50` | Download next 50 pending colleges (sequential) |
| `python main.py --stage1-download --limit 50 --concurrent` | Same, but fetch each college's subpages in parallel |
| `python main.py --stage2-parse` | Parse all downloaded HTML → JSON + Excel (once) |
| `python main.py --limit 3500 --batch-size 100` | Full loop: discover + download in batches, parse once at end |
| `python main.py --limit 3500 --batch-size 100 --parse-per-batch` | Full loop, exporting Excel after every batch |

**Flags:** `--concurrent` (parallel subpages, see below) and `--parse-per-batch`
(export each batch) can be combined with the full-loop or `--stage1-download` runs.

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

### Next lever: concurrency (implemented, opt-in — A/B before trusting)

The default downloader is **sequential** (one subpage at a time). An **async
downloader** (`downloader_async.py`) is now available that fetches a college's 9
subpages **in parallel**, bounded by `config.SUBPAGE_CONCURRENCY` (default 4).
Enable it with the `--concurrent` flag:

```bash
python main.py --stage1-download --limit 3500 --concurrent
```

It reuses the exact same URL selection, block-detection, resource-blocking and
config knobs as the sequential path, so the only variable is concurrency. Colleges
are still processed one at a time, so **at most `SUBPAGE_CONCURRENCY` requests hit
collegedunia at once per laptop.**

> ⚠️ Concurrency raises the risk of CloudFront **403** / rate-limit **429** blocks —
> and 6 laptops each firing `SUBPAGE_CONCURRENCY` requests multiply on one host.
> **A/B test on a sample before a full run** (on an India-located laptop):
>
> ```bash
> # baseline (sequential)
> time python main.py --stage1-download --limit 10
> rm -rf html/*                       # reset
> # concurrent
> time python main.py --stage1-download --limit 10 --concurrent
> ```
>
> Compare wall-clock **and** grep the log for `Blocked/error` — if concurrency
> introduces 403/429s that the sequential run didn't have, lower
> `SUBPAGE_CONCURRENCY` (try 2–3) or stay sequential. Then `--stage2-parse` both and
> confirm the JSON is identical in completeness.

### Getting 403-blocked? (rate-limit — no proxy needed)

Field result: on Indian IPs the **sequential** path worked but **`--concurrent`
got 403-blocked**. Same browser/headers in both → the block is **rate-based (too
many requests per IP), not fingerprint-based**. So the fix is *slow down*, not
stealth or proxies. The code now handles this:

| Lever | What changed |
| :--- | :--- |
| **Slower base rate** | `DELAY_BETWEEN_REQUESTS` restored to **2.5s** (was cut to 1.0). This is the primary anti-block knob — raise it further if 403s persist. |
| **Concurrency off / low** | `--concurrent` stays opt-in; `SUBPAGE_CONCURRENCY` default lowered to **2**, and concurrent requests are **staggered** by `REQUEST_STAGGER_MS`. |
| **Retry with long backoff** | On `403/429/503` the request now retries up to `MAX_RETRIES` with an exponential backoff starting at `RETRY_BASE_DELAY` (20s), honoring the server's `Retry-After`. Transient rate-limits self-heal instead of leaving the page pending. |
| **Light stealth (insurance)** | `--disable-blink-features=AutomationControlled` + `navigator.webdriver` masked + `Accept-Language: en-IN`. Cheap hardening only — not the real fix, since the block isn't fingerprint-based. |

**Run the sequential path (the known-good one):**
```bash
python main.py --stage1-download --limit 3500        # NOT --concurrent
```

**Discriminating test if 403s still appear:** re-run the blocked sample
**sequentially with a bigger delay** — edit `config.DELAY_BETWEEN_REQUESTS = 4`:
- 403s vanish → confirmed rate-based; keep the slower rate (politeness = throughput,
  since being blocked is the slowest outcome). Find the fastest delay that stays clean
  by ramping **down** from a safe value, not up.
- 403s persist even sequential + slow → then it may be fingerprint/IP-reputation;
  only then consider a proxy or headful (`HEADLESS = False`).

> Running 6 laptops in parallel already reduces total run time from ~400 h to
> ~26–32 h; the optimizations above bring each laptop down further.

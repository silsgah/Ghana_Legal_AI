"""Discover and download new Ghana court cases from ghalii.org.

Self-contained scraper for use inside Modal — adapted from the Airflow
GhaliiScraper but without Airflow dependencies. Writes directly to
PostgreSQL `pipeline_cases` table.

Usage (standalone):
    python discover_cases.py            # Discover + download, max 5 pages
    python discover_cases.py --pages 20 # Deeper scrape

Called programmatically from modal_app.py `run_discovery()`.
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from loguru import logger
except ImportError:
    import logging as _logging
    logger = _logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://ghalii.org"
ALL_JUDGMENTS_URL = "https://ghalii.org/judgments/all/"
DEFAULT_REQUEST_DELAY = 5.0  # Match robots.txt Crawl-delay: 5
DEFAULT_MAX_PAGES = 5

# Full browser-like headers to avoid Cloudflare / WAF blocks on datacenter IPs.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Known courts and their URL slugs
SLUG_TO_COURT_ID = {
    "ghasc": "GHASC",
    "ghaca": "GHACA",
    "ghahc": "GHAHC",
    "ghacc": "GHACC",
    "ghadc": "GHADC",
    "ecowascj": "ECOWASCJ",
    "afchpr": "AFCHPR",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def court_id_from_url(url: str) -> str:
    for slug, court_id in SLUG_TO_COURT_ID.items():
        if f"/judgment/{slug}/" in url:
            return court_id
    return "UNKNOWN"


def case_id_from_url(url: str) -> str:
    """Derive a stable case_id from the URL path.

    e.g. https://ghalii.org/akn/gh/judgment/ghasc/2025/10/eng@2025-02-16
      -> GHASC_2025_10
    """
    court_id = court_id_from_url(url)
    match = re.search(r"/judgment/\w+/(\d{4})/(\d+)/", url)
    if match:
        year, number = match.group(1), match.group(2)
        return f"{court_id}_{year}_{number}"
    parts = url.rstrip("/").split("/")
    slug = "_".join(parts[-2:])
    return f"{court_id}_{slug}"


def _get_sync_db_url() -> Optional[str]:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "pooler.supabase.com" in db_url and ":5432" in db_url:
        db_url = db_url.replace(":5432", ":6543")
    return db_url


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

MAX_PAGES_PER_YEAR = 10  # ghalii.org caps pagination at 10 pages per listing URL


def discover_available_years() -> List[int]:
    """Discover all available years from the ghalii.org judgments listing.

    Parses year links like /judgments/all/2023/ from the main page.
    Returns sorted list of years (ascending: oldest first).
    """
    session = _make_session()
    try:
        resp = session.get(ALL_JUDGMENTS_URL, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch years listing: {e}")
        return []

    years = set()
    for match in re.finditer(r"/judgments/all/(\d{4})/", resp.text):
        years.add(int(match.group(1)))

    result = sorted(years)
    if result:
        logger.info(f"Found {len(result)} years on ghalii.org: {result[0]}–{result[-1]}")
    else:
        logger.warning("No years found on ghalii.org listing page")
    return result


def discover_cases_from_ghalii(
    max_pages: int = DEFAULT_MAX_PAGES,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    start_page: int = 1,
    sort_order: str = "-date",
    year: Optional[int] = None,
) -> Tuple[List[Dict], Dict[str, int]]:
    """Scrape ghalii.org for case listings.

    Args:
        max_pages: how many pages to scrape (a "batch").
        request_delay: seconds to sleep between page fetches.
        start_page: page index to start from (1-based).
        sort_order: ghalii sort param. ``-date`` = newest first (incremental),
                    ``date`` = oldest first.
        year: if set, scrape ``/judgments/all/{year}/`` instead of the global
              listing. Used by backfill mode to walk year-by-year.

    Returns:
        (cases, meta) where meta = {
            'pages_scraped': int,           # how many pages actually fetched
            'last_page_attempted': int,
            'reached_end': bool,            # True if a page returned 0 cases (end of pagination)
        }
    """
    from bs4 import BeautifulSoup

    session = _make_session()

    # Helper: detect Cloudflare / WAF challenge pages
    def _is_cloudflare_challenge(text: str) -> bool:
        markers = [
            "cf-browser-verification",
            "Checking your browser",
            "challenge-platform",
            "_cf_chl",
            "Attention Required",
            "cf-turnstile",
            "Just a moment",
        ]
        return any(m in text for m in markers)

    # Build base URL depending on whether we're scraping a specific year
    if year:
        base_listing_url = f"{ALL_JUDGMENTS_URL}{year}/"
    else:
        base_listing_url = ALL_JUDGMENTS_URL

    all_cases: List[Dict] = []
    seen_urls: Set[str] = set()
    end_page = start_page + max_pages - 1
    last_page = start_page - 1
    reached_end = False
    pages_scraped = 0

    for page in range(start_page, end_page + 1):
        last_page = page
        url = f"{base_listing_url}?page={page}&sort={sort_order}"
        logger.info(f"Fetching listing page {page}: {url}")

        try:
            # Set Referer for subsequent pages to look like real browsing
            extra_headers = {}
            if page > start_page:
                extra_headers["Referer"] = f"{base_listing_url}?page={page - 1}&sort={sort_order}"
            resp = session.get(url, timeout=30, headers=extra_headers)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page}: {e}")
            break

        # ghalii.org returns 404 once you paginate past the listing's hard cap
        # (currently 10 pages = ~500 cases for /judgments/all/). Treat that as
        # end-of-pagination, not as a transient error, so the cursor advances
        # past it and the mode flips to incremental.
        if resp.status_code == 404:
            logger.info(f"Page {page} returned 404 — end of pagination.")
            reached_end = True
            break

        try:
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Page {page} returned {resp.status_code}: {e}")
            break

        # --- Cloudflare / WAF detection ---
        resp_text = resp.text
        if _is_cloudflare_challenge(resp_text):
            logger.error(
                f"Page {page}: Cloudflare challenge page detected — "
                f"the server is blocking this IP (likely a datacenter IP). "
                f"Response length: {len(resp_text)} chars. "
                f"First 300 chars: {resp_text[:300]}"
            )
            break

        soup = BeautifulSoup(resp_text, "html.parser")
        page_cases = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/judgment/" not in href or "source" in href:
                continue
            if not re.search(r"/judgment/\w+/\d{4}/\d+/", href):
                continue
            case_text = link.get_text(strip=True)
            if not case_text:
                continue

            full_url = urljoin(BASE_URL, href)
            cid = case_id_from_url(full_url)

            page_cases.append({
                "case_id": cid,
                "url": full_url,
                "pdf_url": urljoin(BASE_URL, href.rstrip("/") + "/source.pdf"),
                "title": case_text,
                "court_id": court_id_from_url(full_url),
            })

        pages_scraped += 1

        if not page_cases:
            # Log diagnostic info so we can tell WHY no cases were found
            title_tag = soup.find("title")
            page_title = title_tag.get_text(strip=True) if title_tag else "(no title)"
            link_count = len(soup.find_all("a", href=True))
            logger.warning(
                f"No cases found on page {page} — end of pagination or blocked. "
                f"Page title: '{page_title}', total links: {link_count}, "
                f"response length: {len(resp_text)} chars. "
                f"First 500 chars: {resp_text[:500]}"
            )
            reached_end = True
            break

        new_count = 0
        for case in page_cases:
            if case["url"] not in seen_urls:
                seen_urls.add(case["url"])
                all_cases.append(case)
                new_count += 1

        logger.info(f"Page {page}: found {new_count} new cases (total: {len(all_cases)})")

        # Within-session dedup: if a page returned only URLs we've already
        # collected this run, ghalii is repeating itself — usually the end of
        # pagination wrapping back. Treat as end-of-listing.
        if new_count == 0:
            logger.info("Page returned only already-seen URLs — treating as end of pagination.")
            reached_end = True
            break

        if page < end_page:
            time.sleep(request_delay)

    meta = {
        "pages_scraped": pages_scraped,
        "last_page_attempted": last_page,
        "reached_end": reached_end,
    }
    logger.info(f"Scrape batch complete: {len(all_cases)} cases, meta={meta}")
    return all_cases, meta


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------

def get_existing_case_ids() -> Set[str]:
    """Get all case_ids already in the pipeline_cases table."""
    db_url = _get_sync_db_url()
    if not db_url:
        logger.warning("DATABASE_URL not configured")
        return set()

    try:
        import psycopg
        with psycopg.connect(db_url, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT case_id FROM pipeline_cases")
                ids = {row[0] for row in cur.fetchall()}
                logger.info(f"Found {len(ids)} existing cases in PostgreSQL")
                return ids
    except Exception as e:
        logger.error(f"Failed to query existing cases: {e}")
        return set()


def insert_new_cases(cases: List[Dict]) -> int:
    """Insert new cases into pipeline_cases with status='pending'."""
    if not cases:
        return 0

    db_url = _get_sync_db_url()
    if not db_url:
        return 0

    try:
        import psycopg
        rows = [
            (
                case["case_id"],
                case["url"],
                case["pdf_url"],
                case["title"],
                case["court_id"],
                case.get("pdf_path"),
            )
            for case in cases
        ]

        with psycopg.connect(db_url, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                # Use executemany — ON CONFLICT DO NOTHING skips duplicates
                cur.executemany(
                    """INSERT INTO pipeline_cases
                       (case_id, url, pdf_url, title, court_id, pdf_path, status, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
                       ON CONFLICT (case_id) DO NOTHING""",
                    rows,
                )
                inserted = cur.rowcount  # total rows affected across all statements
            conn.commit()

        logger.info(f"Inserted {inserted} new cases into pipeline_cases")
        return inserted
    except Exception as e:
        logger.error(f"Failed to insert cases: {e}")
        return 0



# ---------------------------------------------------------------------------
# PDF downloader
# ---------------------------------------------------------------------------

def download_case_pdfs(
    cases: List[Dict],
    data_dir: Path,
    request_delay: float = 0.5,
) -> Dict[str, int]:
    """Download PDFs for the given cases.

    Saves to: data_dir/cases/{court_id}/{case_id}.pdf

    Returns: {downloaded: N, skipped: N, failed: N}
    """
    session = _make_session()
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}

    for i, case in enumerate(cases):
        court_dir = data_dir / "cases" / case["court_id"]
        pdf_path = court_dir / f"{case['case_id']}.pdf"

        if pdf_path.exists():
            logger.info(f"Already on disk: {case['case_id']}")
            stats["skipped"] += 1
            continue

        try:
            resp = session.get(case["pdf_url"], timeout=60, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "application/pdf" not in content_type and "octet-stream" not in content_type:
                logger.warning(f"Unexpected content-type for {case['case_id']}: {content_type}")
                stats["failed"] += 1
                continue

            content = resp.content
            if not content[:4] == b"%PDF":
                logger.warning(f"Invalid PDF magic bytes for {case['case_id']}")
                stats["failed"] += 1
                continue

            court_dir.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(content)
            logger.info(f"Downloaded: {case['case_id']} ({len(content) / 1024:.1f} KB)")
            stats["downloaded"] += 1

        except requests.RequestException as e:
            logger.error(f"Download failed for {case['case_id']}: {e}")
            stats["failed"] += 1

        if i < len(cases) - 1:
            time.sleep(request_delay)

    return stats


# ---------------------------------------------------------------------------
# Discovery state (cursor)
# ---------------------------------------------------------------------------

DEFAULT_BACKFILL_BATCH_SIZE = 5
INCREMENTAL_PAGES = 2  # newest-first pages to scan in incremental mode


def get_discovery_state() -> Dict:
    """Read the singleton discovery_state row, creating it if missing."""
    db_url = _get_sync_db_url()
    if not db_url:
        return {
            "mode": "backfill",
            "backfill_next_page": 1,
            "batch_size": DEFAULT_BACKFILL_BATCH_SIZE,
            "backfill_completed_at": None,
        }

    import psycopg
    with psycopg.connect(db_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT mode, backfill_next_page, batch_size, backfill_completed_at "
                "FROM discovery_state WHERE id = 1"
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO discovery_state (id, mode, backfill_next_page, batch_size, updated_at) "
                    "VALUES (1, 'backfill', 1, %s, NOW()) ON CONFLICT (id) DO NOTHING",
                    (DEFAULT_BACKFILL_BATCH_SIZE,),
                )
                conn.commit()
                return {
                    "mode": "backfill",
                    "backfill_next_page": 1,
                    "batch_size": DEFAULT_BACKFILL_BATCH_SIZE,
                    "backfill_completed_at": None,
                }
            return {
                "mode": row[0],
                "backfill_next_page": row[1],
                "batch_size": row[2],
                "backfill_completed_at": row[3],
            }


def update_discovery_state(**fields) -> None:
    """Update arbitrary columns on the singleton discovery_state row."""
    if not fields:
        return
    db_url = _get_sync_db_url()
    if not db_url:
        return
    set_parts = [f"{k} = %s" for k in fields]
    set_parts.append("updated_at = NOW()")
    values = list(fields.values())

    import psycopg
    with psycopg.connect(db_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE discovery_state SET {', '.join(set_parts)} WHERE id = 1",
                values,
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_discovery(
    max_pages: Optional[int] = None,
    data_dir: Optional[Path] = None,
    batch_size_override: Optional[int] = None,
) -> Dict:
    """Mode-aware discovery: scrape → filter → download → insert.

    Reads ``discovery_state`` for the current cursor and mode.

    - **Backfill mode**: walks year-by-year through ghalii.org's archive.
      ``backfill_next_page`` stores the *year* to process next (e.g. 1958).
      ``batch_size`` controls how many years to process per run.
      Each year is scraped across all its paginated pages (up to 10).
      When all years are exhausted, mode flips to 'incremental'.
    - **Incremental mode**: scrapes the first ``INCREMENTAL_PAGES`` pages
      newest-first from the global listing. Dedup catches anything we
      already have; the rest is genuinely new.

    ``max_pages`` is accepted for backwards compat with old call sites but
    only honored as a one-off override in incremental mode.
    """
    if data_dir is None:
        data_dir = Path("/data")

    state = get_discovery_state()
    mode = state["mode"]
    batch_size = batch_size_override or state["batch_size"] or DEFAULT_BACKFILL_BATCH_SIZE

    all_scraped: List[Dict] = []
    total_pages_scraped = 0
    flipped_to_incremental = False
    cursor_before = state["backfill_next_page"] or 1958
    cursor_after = cursor_before
    years_processed: List[int] = []

    if mode == "backfill":
        # --- Year-by-year backfill ---
        current_year_cursor = state["backfill_next_page"] or 1958
        available_years = discover_available_years()

        if not available_years:
            logger.error("Could not discover available years from ghalii.org")
            return {
                "scraped": 0, "new": 0, "already_known": 0,
                "downloaded": 0, "download_skipped": 0, "download_failed": 0,
                "inserted": 0, "mode": mode,
                "cursor_before": current_year_cursor, "cursor_after": current_year_cursor,
                "pages_scraped": 0, "reached_end": False,
                "flipped_to_incremental": False,
                "summary": "Failed to discover available years from ghalii.org.",
            }

        # Filter to years >= cursor
        years_to_process = [y for y in available_years if y >= current_year_cursor]
        # Take only batch_size years
        years_batch = years_to_process[:batch_size]

        logger.info(
            f"=== Discovery starting (mode=backfill, years={years_batch}, "
            f"cursor={current_year_cursor}, total_remaining={len(years_to_process)}) ==="
        )

        for yr in years_batch:
            cases, meta = discover_cases_from_ghalii(
                max_pages=MAX_PAGES_PER_YEAR,
                start_page=1,
                sort_order="date",
                year=yr,
            )
            all_scraped.extend(cases)
            total_pages_scraped += meta["pages_scraped"]
            years_processed.append(yr)
            logger.info(f"Year {yr}: scraped {len(cases)} cases across {meta['pages_scraped']} pages")

            # Delay between years
            if yr != years_batch[-1]:
                time.sleep(DEFAULT_REQUEST_DELAY)

        # Advance cursor to the year AFTER the last processed
        if years_batch:
            # Find the next year in the full list after the last processed year
            last_processed = years_batch[-1]
            remaining = [y for y in available_years if y > last_processed]
            if remaining:
                cursor_after = remaining[0]
                update_discovery_state(backfill_next_page=cursor_after)
            else:
                # All years processed — backfill complete!
                from datetime import datetime, timezone
                update_discovery_state(
                    mode="incremental",
                    backfill_completed_at=datetime.now(timezone.utc),
                )
                flipped_to_incremental = True
                cursor_after = last_processed + 1
                logger.success("Backfill complete — all years scraped, switching to incremental mode.")

    else:
        # --- Incremental mode ---
        pages_to_scrape = max_pages or INCREMENTAL_PAGES
        logger.info(
            f"=== Discovery starting (mode=incremental, sort=-date, "
            f"pages={pages_to_scrape}) ==="
        )
        scraped, scrape_meta = discover_cases_from_ghalii(
            max_pages=pages_to_scrape,
            start_page=1,
            sort_order="-date",
        )
        all_scraped = scraped
        total_pages_scraped = scrape_meta["pages_scraped"]

    # --- Dedup against pipeline_cases ---
    new_cases: List[Dict] = []
    already_known = 0
    inserted = 0
    dl_stats = {"downloaded": 0, "skipped": 0, "failed": 0}

    if all_scraped:
        existing_ids = get_existing_case_ids()
        new_cases = [c for c in all_scraped if c["case_id"] not in existing_ids]
        already_known = len(all_scraped) - len(new_cases)
        logger.info(
            f"Scraped {len(all_scraped)} cases: {len(new_cases)} new, "
            f"{already_known} already known"
        )

        if new_cases:
            # Insert into PostgreSQL (status='pending')
            inserted = insert_new_cases(new_cases)

            # Best-effort PDF download
            try:
                dl_stats = download_case_pdfs(new_cases, data_dir)
                logger.info(
                    f"Download results: {dl_stats['downloaded']} downloaded, "
                    f"{dl_stats['skipped']} skipped, {dl_stats['failed']} failed"
                )
            except Exception as e:
                logger.warning(f"PDF download step failed (non-blocking): {e}")

    years_str = f" (years: {years_processed})" if years_processed else ""
    summary_text = (
        f"Scraped {len(all_scraped)} cases from ghalii.org{years_str}. "
        f"Found {len(new_cases)} new cases. "
        f"Downloaded {dl_stats['downloaded']} PDFs. "
        f"Inserted {inserted} into pipeline."
    )

    summary = {
        "scraped": len(all_scraped),
        "new": len(new_cases),
        "already_known": already_known,
        "downloaded": dl_stats["downloaded"],
        "download_skipped": dl_stats.get("skipped", 0),
        "download_failed": dl_stats.get("failed", 0),
        "inserted": inserted,
        "mode": mode,
        "cursor_before": cursor_before,
        "cursor_after": cursor_after,
        "pages_scraped": total_pages_scraped,
        "reached_end": flipped_to_incremental,
        "flipped_to_incremental": flipped_to_incremental,
        "years_processed": years_processed,
        "summary": summary_text,
    }

    logger.info(f"=== Discovery complete: {summary} ===")
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discover new cases from ghalii.org")
    parser.add_argument(
        "--batch-size", type=int, default=None,
        help="Pages to scrape this run (overrides discovery_state.batch_size)",
    )
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else None
    result = run_discovery(batch_size_override=args.batch_size, data_dir=data_dir)
    print(f"\nResult: {result}")

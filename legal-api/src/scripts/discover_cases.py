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
from typing import Dict, List, Optional, Set
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
DEFAULT_REQUEST_DELAY = 1.5
DEFAULT_MAX_PAGES = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GhanaLegalAI/1.0"
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

def discover_cases_from_ghalii(
    max_pages: int = DEFAULT_MAX_PAGES,
    request_delay: float = DEFAULT_REQUEST_DELAY,
) -> List[Dict]:
    """Scrape ghalii.org/judgments/all/ for case listings.

    Returns list of dicts: {case_id, url, pdf_url, title, court_id}
    """
    from bs4 import BeautifulSoup

    session = _make_session()
    all_cases = []
    seen_urls: Set[str] = set()

    for page in range(1, max_pages + 1):
        url = f"{ALL_JUDGMENTS_URL}?page={page}&sort=-date"
        logger.info(f"Fetching listing page {page}: {url}")

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
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

        if not page_cases:
            logger.info(f"No cases found on page {page}, stopping pagination.")
            break

        new_count = 0
        for case in page_cases:
            if case["url"] not in seen_urls:
                seen_urls.add(case["url"])
                all_cases.append(case)
                new_count += 1

        logger.info(f"Page {page}: found {new_count} new cases (total: {len(all_cases)})")

        if new_count == 0:
            logger.info("No new cases on this page, stopping.")
            break

        time.sleep(request_delay)

    logger.info(f"Discovery complete: {len(all_cases)} total cases from {min(page, max_pages)} pages")
    return all_cases


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
        with psycopg.connect(db_url, prepare_threshold=0) as conn:
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

        with psycopg.connect(db_url, prepare_threshold=0) as conn:
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
# Main entry point
# ---------------------------------------------------------------------------

def run_discovery(max_pages: int = 5, data_dir: Optional[Path] = None) -> Dict:
    """Full discovery pipeline: scrape → filter → download → insert to DB.

    Returns summary dict.
    """
    if data_dir is None:
        data_dir = Path("/data")

    logger.info(f"=== Starting case discovery (max_pages={max_pages}) ===")

    # Step 1: Scrape ghalii.org
    scraped = discover_cases_from_ghalii(max_pages=max_pages)

    if not scraped:
        return {
            "scraped": 0,
            "new": 0,
            "already_known": 0,
            "downloaded": 0,
            "download_failed": 0,
            "inserted": 0,
        }

    # Step 2: Filter to only new cases
    existing_ids = get_existing_case_ids()
    new_cases = [c for c in scraped if c["case_id"] not in existing_ids]
    already_known = len(scraped) - len(new_cases)

    logger.info(
        f"Scraped {len(scraped)} cases: {len(new_cases)} new, {already_known} already known"
    )

    if not new_cases:
        return {
            "scraped": len(scraped),
            "new": 0,
            "already_known": already_known,
            "downloaded": 0,
            "download_failed": 0,
            "inserted": 0,
        }

    # Step 3: Download PDFs for new cases
    dl_stats = download_case_pdfs(new_cases, data_dir)
    logger.info(
        f"Download results: {dl_stats['downloaded']} downloaded, "
        f"{dl_stats['skipped']} skipped, {dl_stats['failed']} failed"
    )

    # Step 4: Insert into PostgreSQL (only cases that have a PDF on disk)
    cases_with_pdfs = []
    for case in new_cases:
        pdf_path = data_dir / "cases" / case["court_id"] / f"{case['case_id']}.pdf"
        if pdf_path.exists():
            case["pdf_path"] = str(pdf_path)
            cases_with_pdfs.append(case)

    inserted = insert_new_cases(cases_with_pdfs)

    summary = {
        "scraped": len(scraped),
        "new": len(new_cases),
        "already_known": already_known,
        "downloaded": dl_stats["downloaded"],
        "download_skipped": dl_stats["skipped"],
        "download_failed": dl_stats["failed"],
        "inserted": inserted,
    }

    logger.info(f"=== Discovery complete: {summary} ===")
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discover new cases from ghalii.org")
    parser.add_argument("--pages", type=int, default=5, help="Max pages to scrape")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else None
    result = run_discovery(max_pages=args.pages, data_dir=data_dir)
    print(f"\nResult: {result}")

"""Web scraper for ghalii.org case discovery and metadata extraction."""

import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from ghana_legal_plugins.court_config import (
    ALL_JUDGMENTS_URL,
    DEFAULT_MAX_PAGES,
    DEFAULT_REQUEST_DELAY,
    court_id_from_url,
)

logger = logging.getLogger("airflow.task")

BASE_URL = "https://ghalii.org"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GhanaLegalAI/1.0"
}


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def _case_id_from_url(url: str) -> str:
    """Derive a stable case_id from the URL path.

    e.g. https://ghalii.org/akn/gh/judgment/ghasc/2025/10/eng@2025-02-16
      -> GHASC_2025_10
    """
    court_id = court_id_from_url(url)
    # Extract year/number from the URL path
    match = re.search(r"/judgment/\w+/(\d{4})/(\d+)/", url)
    if match:
        year, number = match.group(1), match.group(2)
        return f"{court_id}_{year}_{number}"
    # Fallback: use last two path segments
    parts = url.rstrip("/").split("/")
    slug = "_".join(parts[-2:])
    return f"{court_id}_{slug}"


class GhaliiScraper:
    """Scrapes ghalii.org unified judgments page for all Ghana court cases."""

    def __init__(
        self,
        request_delay: float = DEFAULT_REQUEST_DELAY,
        max_pages: int = DEFAULT_MAX_PAGES,
    ):
        self.request_delay = request_delay
        self.max_pages = max_pages
        self.session = _make_session()

    def discover_all_cases(self, max_pages: Optional[int] = None) -> List[Dict]:
        """Paginate through the unified listing and extract case links.

        Returns list of dicts with keys: case_id, url, pdf_url, title, court_id
        """
        max_pages = max_pages or self.max_pages
        all_cases = []
        seen_urls = set()

        for page in range(1, max_pages + 1):
            url = f"{ALL_JUDGMENTS_URL}?page={page}&sort=-date"
            logger.info(f"Fetching listing page {page}: {url}")

            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Failed to fetch page {page}: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            page_cases = self._extract_case_links(soup)

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

            time.sleep(self.request_delay)

        logger.info(f"Discovery complete: {len(all_cases)} total cases across {min(page, max_pages)} pages")
        return all_cases

    def _extract_case_links(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract case links from a listing page."""
        cases = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Match judgment URL pattern: /akn/gh/judgment/<court>/...
            if "/judgment/" not in href or "source" in href:
                continue
            # Must match known pattern with year/number
            if not re.search(r"/judgment/\w+/\d{4}/\d+/", href):
                continue

            case_text = link.get_text(strip=True)
            if not case_text:
                continue

            full_url = urljoin(BASE_URL, href)
            court_id = court_id_from_url(full_url)
            case_id = _case_id_from_url(full_url)

            cases.append({
                "case_id": case_id,
                "url": full_url,
                "pdf_url": urljoin(BASE_URL, href.rstrip("/") + "/source.pdf"),
                "title": case_text,
                "court_id": court_id,
            })
        return cases

    def extract_case_metadata(self, case_url: str) -> Dict:
        """Visit case detail page and parse structured metadata."""
        metadata = {}
        try:
            resp = self.session.get(case_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract from dt/dd pairs on ghalii detail pages
            for dt in soup.find_all("dt"):
                label = dt.get_text(strip=True).lower().rstrip(":")
                dd = dt.find_next_sibling("dd")
                if dd:
                    value = dd.get_text(strip=True)
                    if "judge" in label:
                        metadata["judges"] = [j.strip() for j in value.split(",")]
                    elif "citation" in label:
                        metadata["citation"] = value
                    elif "date" in label:
                        metadata["decision_date"] = value
                    elif "topic" in label or "subject" in label:
                        metadata["topics"] = [t.strip() for t in value.split(",")]

            # Fallback: extract from h1
            h1 = soup.find("h1")
            if h1:
                metadata.setdefault("full_title", h1.get_text(strip=True))

            time.sleep(self.request_delay)
        except requests.RequestException as e:
            logger.warning(f"Could not extract metadata from {case_url}: {e}")

        return metadata

    def download_pdf(self, pdf_url: str, output_path: Path) -> bool:
        """Download a PDF file. Returns True on success."""
        try:
            resp = self.session.get(pdf_url, timeout=60, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "application/pdf" not in content_type and "octet-stream" not in content_type:
                logger.warning(f"Unexpected content-type for {pdf_url}: {content_type}")
                return False

            output_path.parent.mkdir(parents=True, exist_ok=True)
            content = resp.content

            # Validate PDF magic bytes
            if not content[:4] == b"%PDF":
                logger.warning(f"Invalid PDF magic bytes for {pdf_url}")
                return False

            output_path.write_bytes(content)
            logger.info(f"Downloaded: {output_path.name} ({len(content) / 1024:.1f} KB)")
            return True

        except requests.RequestException as e:
            logger.error(f"Download failed for {pdf_url}: {e}")
            return False

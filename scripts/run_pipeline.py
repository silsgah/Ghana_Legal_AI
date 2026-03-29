#!/usr/bin/env python3
"""Ghana Legal AI — Case ingestion pipeline.

Run manually or via cron:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --max-pages 5    # limit pages for testing

Cron example (weekly Monday 6AM):
    0 6 * * 1 cd /path/to/ghana-legal-ai && python scripts/run_pipeline.py >> data/pipeline.log 2>&1
"""

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MANIFEST_PATH = DATA_DIR / "pipeline_manifest.json"

# Add legal-api to path for Qdrant retriever
sys.path.insert(0, str(PROJECT_ROOT / "legal-api" / "src"))

# Load .env
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "legal-api" / "src" / ".env")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Court config
# ---------------------------------------------------------------------------
BASE_URL = "https://ghalii.org"
ALL_JUDGMENTS_URL = "https://ghalii.org/judgments/all/"

SLUG_TO_COURT = {
    "ghasc": "GHASC",
    "ghaca": "GHACA",
    "ghahc": "GHAHC",
    "ghacc": "GHACC",
    "ghadc": "GHADC",
    "ecowascj": "ECOWASCJ",
    "afchpr": "AFCHPR",
}

# Only ingest Ghanaian courts (set to None to include all)
GHANAIAN_COURTS = {"GHASC", "GHACA", "GHAHC", "GHACC", "GHADC"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GhanaLegalAI/1.0"
}


def court_id_from_url(url: str) -> str:
    for slug, court_id in SLUG_TO_COURT.items():
        if f"/judgment/{slug}/" in url:
            return court_id
    return "UNKNOWN"


def case_id_from_url(url: str) -> str:
    court_id = court_id_from_url(url)
    match = re.search(r"/judgment/\w+/(\d{4})/(\d+)/", url)
    if match:
        return f"{court_id}_{match.group(1)}_{match.group(2)}"
    parts = url.rstrip("/").split("/")
    return f"{court_id}_{'_'.join(parts[-2:])}"


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
@dataclass
class CaseRecord:
    case_id: str
    url: str
    pdf_url: str
    title: str
    court_id: str
    status: str = "discovered"
    discovered_at: str = ""
    updated_at: str = ""
    metadata: Dict = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0

    def __post_init__(self):
        now = datetime.utcnow().isoformat()
        if not self.discovered_at:
            self.discovered_at = now
        if not self.updated_at:
            self.updated_at = now


class PipelineManifest:
    def __init__(self, path: Path):
        self.path = path
        self.cases: Dict[str, CaseRecord] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            for cid, rec in data.get("cases", {}).items():
                self.cases[cid] = CaseRecord(**rec)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"cases": {cid: asdict(r) for cid, r in self.cases.items()}}
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, str(self.path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def add_case(self, rec: CaseRecord) -> bool:
        if rec.case_id in self.cases:
            return False
        self.cases[rec.case_id] = rec
        return True

    def update(self, case_id: str, **kwargs):
        if case_id not in self.cases:
            return
        rec = self.cases[case_id]
        for k, v in kwargs.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        rec.updated_at = datetime.utcnow().isoformat()

    def get(self, case_id: str) -> Optional[CaseRecord]:
        return self.cases.get(case_id)

    def by_status(self, status: str) -> List[CaseRecord]:
        return [r for r in self.cases.values() if r.status == status]

    def failed_retriable(self, max_retries: int = 3) -> List[CaseRecord]:
        return [r for r in self.cases.values()
                if r.status == "failed" and r.retry_count < max_retries]


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def discover_cases(session: requests.Session, max_pages: int = 100) -> List[Dict]:
    from bs4 import BeautifulSoup

    all_cases = []
    seen = set()

    for page in range(1, max_pages + 1):
        url = f"{ALL_JUDGMENTS_URL}?page={page}&sort=-date"
        logger.info(f"Page {page}: {url}")

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed page {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        page_cases = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/judgment/" not in href or "source" in href:
                continue
            if not re.search(r"/judgment/\w+/\d{4}/\d+/", href):
                continue
            text = link.get_text(strip=True)
            if not text:
                continue

            full_url = urljoin(BASE_URL, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            court = court_id_from_url(full_url)
            # Skip non-Ghanaian courts if filter is set
            if GHANAIAN_COURTS and court not in GHANAIAN_COURTS:
                continue

            page_cases.append({
                "case_id": case_id_from_url(full_url),
                "url": full_url,
                "pdf_url": urljoin(BASE_URL, href.rstrip("/") + "/source.pdf"),
                "title": text,
                "court_id": court,
            })

        if not page_cases:
            logger.info(f"No cases on page {page}, stopping.")
            break

        all_cases.extend(page_cases)
        logger.info(f"  -> {len(page_cases)} cases (total: {len(all_cases)})")
        time.sleep(1.5)

    return all_cases


def extract_case_metadata(session: requests.Session, case_url: str) -> Dict:
    from bs4 import BeautifulSoup

    meta = {}
    try:
        resp = session.get(case_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for dt in soup.find_all("dt"):
            label = dt.get_text(strip=True).lower().rstrip(":")
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            value = dd.get_text(strip=True)
            if "judge" in label:
                meta["judges"] = [j.strip() for j in value.split(",")]
            elif "citation" in label:
                meta["citation"] = value
            elif "date" in label:
                meta["decision_date"] = value
            elif "topic" in label or "subject" in label:
                meta["topics"] = [t.strip() for t in value.split(",")]

        h1 = soup.find("h1")
        if h1:
            meta.setdefault("full_title", h1.get_text(strip=True))

        time.sleep(1.5)
    except requests.RequestException as e:
        logger.warning(f"Metadata extraction failed for {case_url}: {e}")
    return meta


def download_pdf(session: requests.Session, pdf_url: str, output_path: Path) -> bool:
    try:
        resp = session.get(pdf_url, timeout=60)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "pdf" not in ct and "octet-stream" not in ct:
            logger.warning(f"Bad content-type for {pdf_url}: {ct}")
            return False
        content = resp.content
        if content[:4] != b"%PDF":
            logger.warning(f"Bad magic bytes for {pdf_url}")
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        logger.info(f"  Downloaded: {output_path.name} ({len(content)/1024:.1f} KB)")
        return True
    except requests.RequestException as e:
        logger.error(f"  Download failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_pdf(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return False
    with open(path, "rb") as f:
        if f.read(4) != b"%PDF":
            return False
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        if len(reader.pages) == 0:
            return False
        # Check extractable text
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            if len(text) > 100:
                return True
        return len(text) > 100
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Parent-Child Chunking + Ingestion
# ---------------------------------------------------------------------------
LEGAL_SECTION_PATTERNS = [
    r"^(?:HELD|RULING|JUDGMENT|ORDER|RATIO DECIDENDI|OBITER DICTUM)[:\s]",
    r"^(?:FACTS|BACKGROUND|INTRODUCTION)[:\s]",
    r"^(?:ISSUES?\s+(?:FOR\s+)?DETERMINATION)[:\s]",
    r"^(?:ANALYSIS|REASONING|DISCUSSION|CONSIDERATION)[:\s]",
    r"^(?:CONCLUSION|DISPOSITION|DECISION)[:\s]",
    r"^(?:PER\s+\w+\s+JS?C)[:\s]",
    r"^(?:DISSENTING\s+OPINION|CONCURRING\s+OPINION)[:\s]",
]


def split_into_legal_sections(text: str) -> List[Dict[str, str]]:
    """Split legal text into semantic sections (parent chunks).

    Returns list of {heading, content} dicts. Falls back to
    paragraph-based splitting if no legal headings found.
    """
    # Build combined pattern with multiline flag applied once at the top
    combined = "|".join(f"({p})" for p in LEGAL_SECTION_PATTERNS)
    splits = re.split(combined, text, flags=re.MULTILINE)

    # re.split with groups returns None entries — filter and recombine
    parts = [s for s in splits if s is not None and s.strip()]

    if len(parts) <= 1:
        # No legal headings found — split by double newlines into ~2000 char parents
        return _paragraph_split(text, target_size=2000)

    sections = []
    current_heading = "Preamble"
    current_content = ""

    for part in parts:
        stripped = part.strip()
        # Check if this part is a heading
        is_heading = False
        for pattern in LEGAL_SECTION_PATTERNS:
            if re.match(pattern, stripped, re.MULTILINE):
                # Save previous section
                if current_content.strip():
                    sections.append({"heading": current_heading, "content": current_content.strip()})
                current_heading = stripped.rstrip(":").strip()
                current_content = ""
                is_heading = True
                break
        if not is_heading:
            current_content += " " + stripped

    # Don't forget last section
    if current_content.strip():
        sections.append({"heading": current_heading, "content": current_content.strip()})

    # If sections are too large, sub-split them
    result = []
    for section in sections:
        if len(section["content"]) > 3000:
            sub_parts = _paragraph_split(section["content"], target_size=2000)
            for i, sp in enumerate(sub_parts):
                sp["heading"] = f"{section['heading']} (Part {i+1})"
                result.append(sp)
        else:
            result.append(section)

    return result if result else [{"heading": "Full Text", "content": text}]


def _paragraph_split(text: str, target_size: int = 2000) -> List[Dict[str, str]]:
    """Split text into chunks at paragraph boundaries, targeting ~target_size chars."""
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) > target_size and current:
            chunks.append({"heading": "Section", "content": current.strip()})
            current = para
        else:
            current += "\n\n" + para if current else para

    if current.strip():
        chunks.append({"heading": "Section", "content": current.strip()})

    return chunks


def create_child_chunks(parent_text: str, chunk_size: int = 512, overlap: int = 100) -> List[str]:
    """Split a parent section into smaller child chunks for embedding."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    return [chunk.page_content for chunk in splitter.create_documents([parent_text])]


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = ", ".join(str(v) for v in value) if value else ""
        elif isinstance(value, dict):
            sanitized[key] = json.dumps(value)
        else:
            sanitized[key] = str(value)
    return sanitized


def ingest_cases(case_ids: List[str], manifest: PipelineManifest):
    """Parent-child chunking ingestion to Qdrant.

    For each case:
    1. Extract full text from PDF
    2. Split into legal sections (parent chunks ~2000 chars)
    3. Split each parent into child chunks (512 chars) for embedding
    4. Store child chunks with parent_content in metadata for retrieval
    5. Upsert to Qdrant with deterministic IDs
    """
    from langchain_community.document_loaders import PyPDFLoader
    from ghana_legal.application.rag.qdrant_retriever import get_qdrant_retriever

    if not case_ids:
        logger.info("Nothing to ingest.")
        return {"successful": 0, "failed": 0}

    retriever = get_qdrant_retriever(
        collection_name="legal_docs",
        embedding_model_id="sentence-transformers/all-MiniLM-L6-v2",
        k=3, device="cpu", use_reranker=False,
    )

    total_chunks = 0
    successful = 0
    failed = 0

    for case_id in case_ids:
        rec = manifest.get(case_id)
        if not rec:
            continue

        pdf_path = DATA_DIR / "cases" / rec.court_id / f"{case_id}.pdf"
        if not pdf_path.exists():
            continue

        try:
            # 1. Extract full text
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()
            full_text = "\n\n".join(p.page_content for p in pages)

            if len(full_text) < 100:
                logger.warning(f"  {case_id}: too little text, skipping")
                continue

            # 2. Split into legal sections (parents)
            sections = split_into_legal_sections(full_text)
            logger.info(f"  {case_id}: {len(sections)} sections from {len(pages)} pages")

            # 3. For each parent, create child chunks
            texts = []
            metadatas = []
            ids = []

            for sec_idx, section in enumerate(sections):
                parent_content = section["content"]
                children = create_child_chunks(parent_content)

                for child_idx, child_text in enumerate(children):
                    chunk_id = f"{case_id}_s{sec_idx}_c{child_idx}"

                    meta = {
                        "case_id": case_id,
                        "court_id": rec.court_id,
                        "title": rec.title,
                        "section_heading": section["heading"],
                        "parent_content": parent_content,  # Full section for retrieval
                        "chunk_index": child_idx,
                        "section_index": sec_idx,
                        "total_sections": len(sections),
                        "document_type": "case_law",
                        "jurisdiction": "Ghana",
                        "source_type": "case_law",
                        "filename": pdf_path.name,
                    }
                    # Add scraped metadata
                    if rec.metadata:
                        for k, v in rec.metadata.items():
                            if k not in meta and v:
                                meta[k] = v

                    texts.append(child_text)
                    metadatas.append(sanitize_metadata(meta))
                    ids.append(chunk_id)

            # 4. Batch upsert
            batch_size = 20
            for i in range(0, len(texts), batch_size):
                try:
                    retriever.add_texts(
                        texts=texts[i:i+batch_size],
                        metadatas=metadatas[i:i+batch_size],
                        ids=ids[i:i+batch_size],
                    )
                    successful += len(texts[i:i+batch_size])
                except Exception as e:
                    logger.error(f"  Batch failed for {case_id}: {e}")
                    failed += len(texts[i:i+batch_size])

            total_chunks += len(texts)
            manifest.update(case_id, status="indexed")

        except Exception as e:
            logger.error(f"  Failed to ingest {case_id}: {e}")
            manifest.update(case_id, status="failed", error=str(e))

    manifest.save()
    logger.info(f"Ingestion done: {successful}/{total_chunks} chunks successful, {failed} failed")
    return {"successful": successful, "failed": failed, "total_chunks": total_chunks}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(max_pages: int = 100):
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("Ghana Legal AI — Ingestion Pipeline")
    logger.info("=" * 60)

    manifest = PipelineManifest(MANIFEST_PATH)
    session = make_session()

    # Re-queue retriable failures
    retriable = manifest.failed_retriable()
    for rec in retriable:
        manifest.update(rec.case_id, status="discovered", retry_count=rec.retry_count + 1)
    if retriable:
        logger.info(f"Re-queued {len(retriable)} retriable failures")

    # Step 1: Discover
    logger.info("\n--- DISCOVER ---")
    cases = discover_cases(session, max_pages=max_pages)
    logger.info(f"Found {len(cases)} total cases on ghalii.org")

    new_ids = []
    for c in cases:
        rec = CaseRecord(
            case_id=c["case_id"], url=c["url"], pdf_url=c["pdf_url"],
            title=c["title"], court_id=c["court_id"],
        )
        if manifest.add_case(rec):
            new_ids.append(c["case_id"])

    retriable_ids = [r.case_id for r in retriable]
    to_process = new_ids + retriable_ids
    manifest.save()
    logger.info(f"New: {len(new_ids)}, retriable: {len(retriable_ids)}, total to process: {len(to_process)}")

    if not to_process:
        logger.info("Nothing new to process. Done.")
        return

    # Step 2: Download
    logger.info("\n--- DOWNLOAD ---")
    downloaded = []
    for cid in to_process:
        rec = manifest.get(cid)
        if not rec:
            continue
        pdf_path = DATA_DIR / "cases" / rec.court_id / f"{cid}.pdf"
        if pdf_path.exists():
            manifest.update(cid, status="downloaded")
            downloaded.append(cid)
            continue
        if download_pdf(session, rec.pdf_url, pdf_path):
            manifest.update(cid, status="downloaded")
            downloaded.append(cid)
        else:
            manifest.update(cid, status="failed", error="download_failed")
        time.sleep(1.5)
    manifest.save()
    logger.info(f"Downloaded: {len(downloaded)}/{len(to_process)}")

    # Step 3: Validate
    logger.info("\n--- VALIDATE ---")
    validated = []
    for cid in downloaded:
        rec = manifest.get(cid)
        pdf_path = DATA_DIR / "cases" / rec.court_id / f"{cid}.pdf"
        if validate_pdf(pdf_path):
            manifest.update(cid, status="validated")
            validated.append(cid)
        else:
            manifest.update(cid, status="failed", error="validation_failed")
    manifest.save()
    logger.info(f"Validated: {len(validated)}/{len(downloaded)}")

    # Step 4: Extract metadata
    logger.info("\n--- METADATA ---")
    for cid in validated:
        rec = manifest.get(cid)
        meta = extract_case_metadata(session, rec.url)
        meta["title"] = rec.title
        meta["court_id"] = rec.court_id
        meta["pdf_path"] = str(DATA_DIR / "cases" / rec.court_id / f"{cid}.pdf")
        manifest.update(cid, metadata=meta)
    manifest.save()
    logger.info(f"Metadata extracted for {len(validated)} cases")

    # Step 5: Ingest to Qdrant
    logger.info("\n--- INGEST ---")
    stats = ingest_cases(validated, manifest)

    # Step 6: Report
    duration = (datetime.utcnow() - start).total_seconds()
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "duration_seconds": round(duration, 1),
        "discovered": len(new_ids),
        "downloaded": len(downloaded),
        "validated": len(validated),
        **stats,
    }
    report_dir = DATA_DIR / "pipeline_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.write_text(json.dumps(report, indent=2))

    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"  Duration: {duration:.0f}s ({duration/60:.1f}min)")
    logger.info(f"  New cases: {len(new_ids)}")
    logger.info(f"  Downloaded: {len(downloaded)}")
    logger.info(f"  Validated: {len(validated)}")
    logger.info(f"  Chunks ingested: {stats['successful']}")
    logger.info(f"  Report: {report_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghana Legal AI ingestion pipeline")
    parser.add_argument("--max-pages", type=int, default=100, help="Max listing pages to scrape")
    args = parser.parse_args()
    run(max_pages=args.max_pages)

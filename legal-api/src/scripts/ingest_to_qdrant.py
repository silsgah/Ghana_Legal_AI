#!/usr/bin/env python3
"""
Comprehensive script to ingest Ghana legal PDFs into Qdrant Cloud.

Adapted from ingest_cases_to_chroma.py for Qdrant Cloud production use.

This script:
1. Queries PostgreSQL for pending cases
2. Loads matching PDFs from data directories
3. Parses legal structure (case names, citations, dates)
4. Splits into optimal chunks
5. Generates Voyage AI embeddings
6. Stores in Qdrant Cloud with rich metadata
7. Marks successfully ingested cases as 'indexed' in PostgreSQL
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Set
from datetime import datetime
import re
import json

# Add src to path for imports
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
sys.path.insert(0, str(src_dir))

from dotenv import load_dotenv
load_dotenv(src_dir / ".env")

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from tqdm import tqdm

from ghana_legal.config import settings

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


# ---------------------------------------------------------------------------
# PostgreSQL helpers (sync via psycopg3, already in requirements)
# ---------------------------------------------------------------------------

def _get_sync_db_url() -> str:
    """Build a sync-compatible PostgreSQL connection string."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        # Try loading from settings as fallback
        try:
            db_url = settings.DATABASE_URL
        except Exception:
            pass

    if not db_url:
        return ""

    # Convert SQLAlchemy async driver prefix to standard
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    # Supabase pgBouncer requires port 6543 for transaction pooling
    if "pooler.supabase.com" in db_url and ":5432" in db_url:
        db_url = db_url.replace(":5432", ":6543")
    return db_url


def get_pending_case_ids_from_db() -> Set[str]:
    """Query PostgreSQL for case IDs with pending/downloaded status."""
    try:
        import psycopg
    except ImportError:
        logger.warning("psycopg not installed, falling back to manifest file")
        return set()

    db_url = _get_sync_db_url()
    if not db_url:
        logger.warning("DATABASE_URL not configured, cannot query pending cases")
        return set()

    try:
        with psycopg.connect(db_url, prepare_threshold=0) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT case_id FROM pipeline_cases WHERE status IN ('pending', 'downloaded')"
                )
                ids = {row[0] for row in cur.fetchall()}
                logger.info(f"Found {len(ids)} pending cases in PostgreSQL")
                return ids
    except Exception as e:
        logger.error(f"Failed to query pending cases from PostgreSQL: {e}")
        return set()


def update_db_statuses(case_ids: Set[str]) -> int:
    """Mark cases as 'indexed' in PostgreSQL after successful Qdrant upload."""
    if not case_ids:
        return 0

    try:
        import psycopg
    except ImportError:
        logger.warning("psycopg not installed, cannot update DB statuses")
        return 0

    db_url = _get_sync_db_url()
    if not db_url:
        logger.warning("DATABASE_URL not configured, cannot update statuses")
        return 0

    try:
        with psycopg.connect(db_url, prepare_threshold=0) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE pipeline_cases SET status = 'indexed', updated_at = NOW() "
                    "WHERE case_id = ANY(%s) AND status IN ('pending', 'downloaded')",
                    (list(case_ids),)
                )
                count = cur.rowcount
            conn.commit()
            logger.success(f"✓ Updated {count} cases to 'indexed' in PostgreSQL")
            return count
    except Exception as e:
        logger.error(f"Failed to update DB statuses: {e}")
        return 0


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

class CaseMetadataExtractor:
    """Extract metadata from Ghana Supreme Court case filenames and content."""

    @staticmethod
    def extract_from_filename(filename: str) -> Dict[str, Any]:
        metadata = {
            "filename": filename,
            "document_type": "case_law",
            "jurisdiction": "Ghana",
            "court": "Supreme Court"
        }

        name = filename.replace(".pdf", "")

        # Detect constitution
        if "constitution" in name.lower():
            metadata["document_type"] = "constitution"
            metadata["court"] = "N/A"
            return metadata

        # Try to extract parties
        parties_match = re.match(r"^(.+?)[-_](?:J\d+|VRS|v[\s_])", name, re.IGNORECASE)
        if parties_match:
            parties = parties_match.group(1).replace("_", " ").replace("-", " ")
            metadata["parties"] = parties

        # Extract year
        year_match = re.search(r'(\d{4})', name)
        if year_match:
            metadata["year"] = int(year_match.group(1))

        if "GHASC" in name:
            metadata["court"] = "Ghana Supreme Court"
        elif "GHACA" in name:
            metadata["court"] = "Ghana Court of Appeal"

        return metadata


# ---------------------------------------------------------------------------
# PDF loading
# ---------------------------------------------------------------------------

def load_pdf_documents(data_dirs: List[Path], max_cases: int = 50) -> List[Document]:
    """Load Constitution PDFs and pending case PDFs incrementally.

    - Always loads Constitution PDFs (no filtering).
    - For case directories, only loads PDFs that are 'pending' in PostgreSQL.
    - Caps case loading at max_cases to stay within Modal timeout limits.
    """
    all_documents = []

    # Get pending case IDs from PostgreSQL
    pending_case_ids = get_pending_case_ids_from_db()
    pending_filenames = {f"{cid}.pdf" for cid in pending_case_ids}

    logger.info(f"Targeting {len(pending_filenames)} pending cases for ingestion")

    for data_dir in data_dirs:
        if not data_dir.exists():
            logger.warning(f"Directory not found, skipping: {data_dir}")
            continue

        pdf_files = sorted(data_dir.rglob("*.pdf"))

        # For case directories: filter to pending-only and cap
        is_case_dir = "cases" in data_dir.name.lower()
        if is_case_dir:
            if pending_filenames:
                pdf_files = [p for p in pdf_files if p.name in pending_filenames]
            pdf_files = pdf_files[:max_cases]

        if not pdf_files:
            logger.info(f"No eligible PDFs in {data_dir.name}")
            continue

        label = "case" if is_case_dir else "constitution"
        logger.info(f"Loading {len(pdf_files)} {label} PDF(s) from {data_dir.name}/")

        for pdf_path in tqdm(pdf_files, desc=f"Loading {data_dir.name}", unit="file"):
            try:
                loader = PyPDFLoader(str(pdf_path))
                pages = loader.load()

                if not pages:
                    logger.warning(f"No content extracted from {pdf_path.name}")
                    continue

                combined_content = "\n\n".join([page.page_content for page in pages])
                file_metadata = CaseMetadataExtractor.extract_from_filename(pdf_path.name)

                # Determine source type
                source_type = "constitution" if "constitution" in str(data_dir).lower() or "constitution" in pdf_path.name.lower() else "case_law"
                file_metadata["source_type"] = source_type
                file_metadata["source"] = str(pdf_path)
                file_metadata["total_pages"] = len(pages)
                file_metadata["ingestion_date"] = datetime.now().isoformat()

                doc = Document(page_content=combined_content, metadata=file_metadata)
                all_documents.append(doc)

                logger.success(f"✓ Loaded: {pdf_path.name} ({len(pages)} pages)")

            except Exception as e:
                logger.error(f"✗ Failed to load {pdf_path.name}: {e}")

    logger.info(f"\nTotal documents loaded: {len(all_documents)}")
    return all_documents


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def split_documents(documents: List[Document], chunk_size: int = 512, chunk_overlap: int = 100) -> List[Document]:
    """Split documents into optimal chunks for embeddings."""
    logger.info(f"Splitting {len(documents)} documents (chunk_size={chunk_size}, overlap={chunk_overlap})")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunked_docs = []
    for doc in tqdm(documents, desc="Splitting documents", unit="doc"):
        chunks = splitter.split_documents([doc])
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        chunked_docs.extend(chunks)

    logger.info(f"Created {len(chunked_docs)} chunks from {len(documents)} documents")
    return chunked_docs


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------

def sanitize_metadata_for_qdrant(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize metadata for Qdrant payload compatibility."""
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            continue  # Skip None values for Qdrant
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            if value:
                sanitized[key] = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            sanitized[key] = json.dumps(value)
        else:
            sanitized[key] = str(value)
    return sanitized


def ingest_to_qdrant(documents: List[Document]) -> Dict[str, Any]:
    """Ingest documents into Qdrant Cloud with progress tracking."""
    from ghana_legal.application.rag.qdrant_retriever import get_qdrant_retriever

    logger.info(f"Starting Qdrant Cloud ingestion for {len(documents)} chunks...")

    # Get Qdrant retriever (initializes client + embedding model)
    retriever = get_qdrant_retriever(
        collection_name="legal_docs",
        embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
        k=settings.RAG_TOP_K,
        device=settings.RAG_DEVICE,
        use_reranker=False,  # No reranker needed during ingestion
    )

    # Batch ingestion
    batch_size = 20
    total_batches = (len(documents) + batch_size - 1) // batch_size

    successful = 0
    failed = 0

    logger.info(f"Ingesting in batches of {batch_size} (total: {total_batches} batches)")

    for i in tqdm(range(0, len(documents), batch_size), desc="Ingesting batches", unit="batch"):
        batch = documents[i:i + batch_size]

        try:
            texts = [doc.page_content for doc in batch]
            metadatas = [sanitize_metadata_for_qdrant(doc.metadata) for doc in batch]
            ids = [
                f"{doc.metadata.get('source_type', 'doc')}_{doc.metadata.get('filename', 'unknown')}_{doc.metadata.get('chunk_index', i)}"
                for doc in batch
            ]

            retriever.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            successful += len(batch)

        except Exception as e:
            logger.error(f"Batch ingestion failed: {e}")
            failed += len(batch)

    stats = {
        "total_chunks": len(documents),
        "successful": successful,
        "failed": failed,
        "success_rate": (successful / len(documents)) * 100 if documents else 0
    }

    logger.info(f"\nIngestion Summary:")
    logger.info(f"  Total chunks: {stats['total_chunks']}")
    logger.info(f"  Successful: {stats['successful']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info(f"  Success rate: {stats['success_rate']:.1f}%")

    return stats


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    """Main ingestion pipeline for Qdrant Cloud."""
    logger.info("=" * 80)
    logger.info("Ghana Legal AI - Qdrant Cloud Ingestion Pipeline")
    logger.info("=" * 80)

    # Verify Qdrant credentials
    qdrant_url = os.getenv("QDRANT_URL", settings.QDRANT_URL)
    qdrant_key = os.getenv("QDRANT_API_KEY", settings.QDRANT_API_KEY)

    if not qdrant_url or not qdrant_key:
        logger.error("QDRANT_URL and QDRANT_API_KEY must be set in .env")
        sys.exit(1)

    logger.info(f"Target: Qdrant Cloud at {qdrant_url[:50]}...")

    start_time = datetime.now()

    # Define all data directories — resolves to /data/ inside Modal
    project_root = Path(__file__).resolve().parents[3]
    data_dirs = [
        project_root / "data" / "ghana_legal" / "constitution",
        project_root / "data" / "ghana_legal" / "cases",
        project_root / "data" / "cases",
    ]

    logger.info(f"Scanning {len(data_dirs)} data directories...")

    # Step 1: Load PDFs (filtered to pending cases via PostgreSQL)
    documents = load_pdf_documents(data_dirs)
    if not documents:
        logger.warning("No documents to process. All cases may already be indexed.")
        return

    # Step 2: Split into chunks
    chunked_docs = split_documents(
        documents,
        chunk_size=512,
        chunk_overlap=100
    )

    # Step 3: Ingest to Qdrant Cloud
    stats = ingest_to_qdrant(chunked_docs)

    # Step 4: Update PostgreSQL — mark ingested cases as 'indexed'
    if stats["successful"] > 0:
        loaded_case_ids = {
            doc.metadata.get("filename", "").replace(".pdf", "")
            for doc in documents
            if doc.metadata.get("source_type") == "case_law"
        }
        if loaded_case_ids:
            update_db_statuses(loaded_case_ids)

    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("\n" + "=" * 80)
    logger.info("QDRANT CLOUD INGESTION COMPLETE!")
    logger.info("=" * 80)
    logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    logger.info(f"Documents processed: {len(documents)}")
    logger.info(f"Total chunks ingested: {stats['successful']}")
    logger.info(f"Average chunks per document: {stats['successful']/len(documents):.1f}")
    logger.info("=" * 80)

    logger.success("\n✓ Your Qdrant Cloud vector store is now loaded with Ghana legal data!")


if __name__ == "__main__":
    main()

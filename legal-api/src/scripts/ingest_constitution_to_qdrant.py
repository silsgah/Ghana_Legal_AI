#!/usr/bin/env python3
"""
Dedicated script to ingest the Ghana Constitution (1992) into Qdrant Cloud.

Usage (from project root):
    cd legal-api/src
    python scripts/ingest_constitution_to_qdrant.py

Options:
    --wipe        Delete existing constitution vectors before reingesting (clean slate)
    --verify-only Check how many constitution chunks are in Qdrant (no ingestion)
    --chunk-size  Chunk size for text splitting (default: 512)
    --chunk-overlap Overlap between chunks (default: 100)
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# ── Path setup ──────────────────────────────────────────────────────────────
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
project_root = src_dir.parent.parent        # ghana-legal-ai/
sys.path.insert(0, str(src_dir))

from dotenv import load_dotenv
load_dotenv(src_dir / ".env")

# ── Imports (after path/env setup) ──────────────────────────────────────────
from loguru import logger
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from ghana_legal.config import settings

# ── Logging ──────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
)

CONSTITUTION_DIR = project_root / "data" / "ghana_legal" / "constitution"
COLLECTION_NAME = "legal_docs"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Strip None values and convert unsupported types for Qdrant payloads."""
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = ", ".join(str(v) for v in value) if value else ""
        elif isinstance(value, dict):
            import json
            sanitized[key] = json.dumps(value)
        else:
            sanitized[key] = str(value)
    return sanitized


def load_constitution_pdf(chunk_size: int = 512, chunk_overlap: int = 100) -> List[Document]:
    """Load and chunk the Ghana Constitution PDF."""
    if not CONSTITUTION_DIR.exists():
        logger.error(f"Constitution directory not found: {CONSTITUTION_DIR}")
        sys.exit(1)

    pdf_files = list(CONSTITUTION_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error(f"No PDF files found in: {CONSTITUTION_DIR}")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} constitution PDF(s):")
    for f in pdf_files:
        logger.info(f"  • {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

    all_chunks: List[Document] = []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    for pdf_path in pdf_files:
        logger.info(f"Loading: {pdf_path.name}")
        try:
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()

            if not pages:
                logger.warning(f"No content extracted from {pdf_path.name}")
                continue

            logger.info(f"  Loaded {len(pages)} pages, splitting into chunks...")
            chunks = splitter.split_documents(pages)

            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "document_type": "constitution",
                    "source_type": "constitution",
                    "jurisdiction": "Ghana",
                    "court": "N/A",
                    "filename": pdf_path.name,
                    "source": str(pdf_path),
                    "total_pages": len(pages),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "ingestion_date": datetime.now().isoformat(),
                })

            all_chunks.extend(chunks)
            logger.success(f"  ✓ {pdf_path.name} → {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"  ✗ Failed to load {pdf_path.name}: {e}")

    logger.info(f"\nTotal constitution chunks ready for ingestion: {len(all_chunks)}")
    return all_chunks


def get_qdrant_client():
    """Initialise and return a raw Qdrant client."""
    from qdrant_client import QdrantClient

    url = os.getenv("QDRANT_URL", "")
    api_key = os.getenv("QDRANT_API_KEY", "")

    if not url or not api_key:
        logger.error("QDRANT_URL and QDRANT_API_KEY must be set in .env")
        sys.exit(1)

    logger.info(f"Connecting to Qdrant Cloud: {url[:50]}...")
    client = QdrantClient(url=url, api_key=api_key)
    logger.success("Connected to Qdrant Cloud ✓")
    return client


def ensure_payload_indexes(client):
    """Create keyword payload indexes needed for filtered search in Qdrant.

    Without these indexes, any filter on these fields returns a 400 error.
    Safe to call even if the index already exists.
    """
    from qdrant_client.http.models import PayloadSchemaType

    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        return  # Nothing to index yet

    fields_to_index = ["source_type", "document_type", "jurisdiction", "court"]
    for field in fields_to_index:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.success(f"  Payload index created/verified: '{field}'")
        except Exception as e:
            # Index may already exist — that's fine
            logger.debug(f"  Index for '{field}' already exists or skipped: {e}")


def verify_collection(client, verbose: bool = True) -> int:
    """Return the number of constitution vectors already in Qdrant."""
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue

    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        if verbose:
            logger.warning(f"Collection '{COLLECTION_NAME}' does not exist yet.")
        return 0

    total_points = client.get_collection(COLLECTION_NAME).points_count or 0

    try:
        result = client.count(
            collection_name=COLLECTION_NAME,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="source_type",
                        match=MatchValue(value="constitution"),
                    )
                ]
            ),
            exact=True,
        )
        constitution_count = result.count
    except Exception as e:
        logger.warning(f"Filtered count failed ({e}), returning total.")
        constitution_count = total_points

    if verbose:
        logger.info(f"Collection '{COLLECTION_NAME}':")
        logger.info(f"  Total vectors          : {total_points}")
        logger.info(f"  Constitution vectors   : {constitution_count}")

    return constitution_count


def wipe_constitution_vectors(client):
    """Delete all constitution-tagged points from the collection."""
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue

    logger.warning("Deleting existing constitution vectors from Qdrant...")
    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source_type",
                        match=MatchValue(value="constitution"),
                    )
                ]
            ),
        )
        logger.success("✓ Existing constitution vectors removed.")
    except Exception as e:
        logger.error(f"Failed to delete constitution vectors: {e}")
        sys.exit(1)


def ingest_chunks(client, chunks: List[Document]):
    """Embed and upsert chunks into Qdrant."""
    from ghana_legal.application.rag.embeddings import get_embedding_model
    from qdrant_client.http.models import PointStruct, VectorParams, Distance

    # ── Ensure collection exists ─────────────────────────────────────────────
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        logger.info(f"Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=settings.RAG_TEXT_EMBEDDING_MODEL_DIM,  # 1024 for voyage-law-2
                distance=Distance.COSINE,
            ),
        )
        logger.success(f"Collection '{COLLECTION_NAME}' created ✓")

    # ── Load embedding model (Voyage AI) ─────────────────────────────────────
    logger.info(f"Loading Voyage AI embedding model: {settings.RAG_TEXT_EMBEDDING_MODEL_ID}")
    embedding_model = get_embedding_model(settings.RAG_TEXT_EMBEDDING_MODEL_ID)
    logger.success("Voyage AI embedding model loaded ✓")

    # ── Batch upsert ─────────────────────────────────────────────────────────
    batch_size = 20
    successful = 0
    failed = 0

    logger.info(f"Ingesting {len(chunks)} chunks in batches of {batch_size}...")

    for i in tqdm(range(0, len(chunks), batch_size), desc="Ingesting", unit="batch"):
        batch = chunks[i : i + batch_size]
        try:
            texts = [doc.page_content for doc in batch]
            embeddings = embedding_model.embed_documents(texts)

            points = []
            for j, (doc, emb) in enumerate(zip(batch, embeddings)):
                chunk_id = (
                    f"constitution_{doc.metadata.get('filename', 'unknown')}"
                    f"_{doc.metadata.get('chunk_index', i + j)}"
                )
                payload = {"page_content": doc.page_content}
                payload.update(sanitize_metadata(doc.metadata))

                points.append(
                    PointStruct(
                        id=abs(hash(chunk_id)) % (2**63),
                        vector=emb,
                        payload=payload,
                    )
                )

            client.upsert(collection_name=COLLECTION_NAME, points=points)
            successful += len(batch)

        except Exception as e:
            logger.error(f"Batch {i // batch_size + 1} failed: {e}")
            failed += len(batch)

    logger.info("\n--- Ingestion Summary ---")
    logger.info(f"  Chunks attempted : {len(chunks)}")
    logger.info(f"  Successful       : {successful}")
    logger.info(f"  Failed           : {failed}")
    logger.info(f"  Success rate     : {successful / len(chunks) * 100:.1f}%")

    return successful, failed


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingest Ghana Constitution into Qdrant Cloud"
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete existing constitution vectors before reingesting (clean reingest)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only check how many constitution chunks exist in Qdrant; no ingestion",
    )
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("  Ghana Legal AI — Constitution → Qdrant Cloud Ingestion")
    logger.info("=" * 70)
    logger.info(f"  Constitution dir : {CONSTITUTION_DIR}")
    logger.info(f"  Collection       : {COLLECTION_NAME}")
    logger.info(f"  Qdrant URL       : {os.getenv('QDRANT_URL', 'NOT SET')[:55]}...")
    logger.info(f"  Embedding model  : {settings.RAG_TEXT_EMBEDDING_MODEL_ID}")
    logger.info(f"  Chunk size       : {args.chunk_size}")
    logger.info(f"  Chunk overlap    : {args.chunk_overlap}")
    logger.info("=" * 70)

    client = get_qdrant_client()

    # ── Create payload indexes (needed for filtered search) ──────────────────
    logger.info("Ensuring Qdrant payload indexes exist...")
    ensure_payload_indexes(client)

    # ── Verify-only mode ─────────────────────────────────────────────────────
    if args.verify_only:
        count = verify_collection(client)
        if count > 0:
            logger.success(f"✓ {count} constitution vectors found in Qdrant.")
        else:
            logger.warning("⚠  No constitution vectors found. Run without --verify-only to ingest.")
        return

    # ── Check current state ───────────────────────────────────────────────────
    existing_count = verify_collection(client)
    if existing_count > 0 and not args.wipe:
        logger.warning(
            f"\n⚠  {existing_count} constitution vectors already exist in Qdrant."
        )
        logger.warning(
            "   Run with --wipe to delete them and do a clean reingest."
        )
        logger.warning(
            "   Or proceed to ADD additional chunks (possible duplicates)."
        )
        answer = input("\nContinue anyway? [y/N]: ").strip().lower()
        if answer != "y":
            logger.info("Aborted.")
            return
    elif existing_count == 0:
        pass  # Fresh ingest, no wipe needed

    # ── Wipe existing ─────────────────────────────────────────────────────────
    if args.wipe and existing_count > 0:
        wipe_constitution_vectors(client)

    # ── Load + chunk PDF ──────────────────────────────────────────────────────
    start = datetime.now()
    chunks = load_constitution_pdf(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    if not chunks:
        logger.error("No chunks produced. Aborting.")
        sys.exit(1)

    # ── Ingest ────────────────────────────────────────────────────────────────
    successful, failed = ingest_chunks(client, chunks)

    # ── Final verification ────────────────────────────────────────────────────
    logger.info("\nVerifying ingestion...")
    final_count = verify_collection(client)

    elapsed = (datetime.now() - start).total_seconds()

    logger.info("\n" + "=" * 70)
    if failed == 0:
        logger.success("✓ Constitution ingested into Qdrant Cloud successfully!")
    else:
        logger.warning(f"⚠  Ingestion completed with {failed} failed chunks.")
    logger.info(f"  Duration              : {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info(f"  Chunks ingested       : {successful}")
    logger.info(f"  Constitution in Qdrant: {final_count}")
    logger.info("=" * 70)
    logger.info("\nNext steps:")
    logger.info("  1. Restart backend:  make start-backend")
    logger.info("  2. Test a query:     'What does the Ghana Constitution say about fundamental human rights?'")
    logger.info("  3. Verify via script: python scripts/verify_ingestion.py")


if __name__ == "__main__":
    main()

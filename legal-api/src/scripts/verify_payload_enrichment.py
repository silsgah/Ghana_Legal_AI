#!/usr/bin/env python3
"""Verify that Qdrant payloads carry case_id and paragraph_id after re-ingestion.

Pulls a sample of points and a sample retrieval, reports the field coverage.
Exit code is non-zero if either sample is missing the enrichment fields, so
this can gate a CI step.

Usage:
    python -m scripts.verify_payload_enrichment
"""

import os
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
sys.path.insert(0, str(src_dir))

from dotenv import load_dotenv
load_dotenv(src_dir / ".env")

from loguru import logger

from ghana_legal.application.rag.qdrant_retriever import get_qdrant_retriever
from ghana_legal.config import settings


REQUIRED_FIELDS = ("case_id", "paragraph_id", "paragraph_hash")
SAMPLE_QUERY = "What does the Constitution say about fundamental human rights?"


def _field_coverage(metadatas: list[dict]) -> dict[str, float]:
    if not metadatas:
        return {f: 0.0 for f in REQUIRED_FIELDS}
    n = len(metadatas)
    return {f: sum(1 for m in metadatas if m.get(f)) / n for f in REQUIRED_FIELDS}


def main() -> int:
    retriever = get_qdrant_retriever(
        collection_name="legal_docs",
        embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
        k=10,
        device=settings.RAG_DEVICE,
        use_reranker=False,
    )

    logger.info("Sampling 20 random points from collection...")
    scroll, _ = retriever.client.scroll(
        collection_name=retriever.collection_name,
        limit=20,
        with_payload=True,
    )
    sample_metas = [(p.payload or {}) for p in scroll]
    sample_cov = _field_coverage(sample_metas)

    logger.info("Running sample retrieval to confirm fields survive _vector_search...")
    docs = retriever.retrieve(SAMPLE_QUERY)
    retrieval_cov = _field_coverage([d.metadata for d in docs])

    logger.info("=" * 60)
    logger.info("Field coverage in random sample (n=%d):", len(sample_metas))
    for f, pct in sample_cov.items():
        logger.info(f"  {f:20s} {pct * 100:5.1f}%")

    logger.info("Field coverage on retrieval result (k=%d):", len(docs))
    for f, pct in retrieval_cov.items():
        logger.info(f"  {f:20s} {pct * 100:5.1f}%")
    logger.info("=" * 60)

    if docs:
        top = docs[0].metadata
        logger.info(
            f"Top retrieved hit: case_id={top.get('case_id', 'MISSING')} "
            f"paragraph_id={top.get('paragraph_id', 'MISSING')}"
        )

    failures = [f for f, pct in sample_cov.items() if pct < 0.95]
    failures += [f for f, pct in retrieval_cov.items() if pct < 0.95]
    if failures:
        logger.error(f"FAIL: fields below 95% coverage: {sorted(set(failures))}")
        return 1
    logger.success("PASS: all enrichment fields present in ≥95% of sampled points")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Modal deployment entry point for Ghana Legal AI backend.

Wraps the existing FastAPI application as a Modal ASGI web endpoint.
Serves the API at: https://<your-modal-username>--ghana-legal-ai-api.modal.run

Usage:
    modal serve modal_app.py    # Dev mode (hot-reload)
    modal deploy modal_app.py   # Production deploy
"""

import modal

# ---------------------------------------------------------------------------
# Modal Image — installs all Python dependencies
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .pip_install("langchain-voyageai", "voyageai", "qdrant-client", "datasketch")
    .add_local_dir("src", remote_path="/root/src")
    .add_local_dir("../data", remote_path="/data")
)

# ---------------------------------------------------------------------------
# Modal App
# ---------------------------------------------------------------------------
app = modal.App("ghana-legal-ai")

# ---------------------------------------------------------------------------
# FastAPI Web Endpoint
# ---------------------------------------------------------------------------
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ghana-legal-secrets")],
    timeout=900,  # 15 min for web requests
    memory=2048,
)
@modal.asgi_app()
def api():
    """Serve the FastAPI application."""
    import sys
    sys.path.insert(0, "/root/src")

    from ghana_legal.infrastructure.api import app as fastapi_app
    return fastapi_app


# ---------------------------------------------------------------------------
# Dedicated Ingestion Function — runs in its own container with generous timeout
# ---------------------------------------------------------------------------
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ghana-legal-secrets")],
    timeout=1800,  # 30 min — plenty of room for Voyage AI embedding batches
    memory=2048,
)
def run_ingestion(run_id: int, max_cases: int = 10):
    """Ingest pending legal PDFs into Qdrant Cloud.

    Spawned asynchronously from the admin API via:
        run_ingestion.spawn(run_id=..., max_cases=10)

    This function:
    1. Runs the ingest_to_qdrant pipeline (PDF → Voyage AI → Qdrant)
    2. Updates the IngestionRun row in PostgreSQL with final status
    3. Logs diagnostics (matched case_ids, chunks processed, etc.)
    """
    import sys
    import os
    import traceback
    sys.path.insert(0, "/root/src")

    from datetime import datetime, timezone
    from loguru import logger

    logger.info(f"=== Modal run_ingestion started | run_id={run_id} max_cases={max_cases} ===")

    # --- Helper to update the IngestionRun row (sync psycopg) ---
    def update_run(**fields):
        """Update the IngestionRun row in PostgreSQL using sync psycopg."""
        import psycopg
        db_url = os.environ.get("DATABASE_URL", "")
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        if "pooler.supabase.com" in db_url and ":5432" in db_url:
            db_url = db_url.replace(":5432", ":6543")

        # Build SET clause dynamically
        set_parts = []
        values = []
        for key, val in fields.items():
            set_parts.append(f"{key} = %s")
            # Serialize dicts to JSON for the 'result' column
            if isinstance(val, dict):
                import json
                values.append(json.dumps(val))
            else:
                values.append(val)
        values.append(run_id)

        try:
            with psycopg.connect(db_url, prepare_threshold=0) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE ingestion_runs SET {', '.join(set_parts)} WHERE id = %s",
                        values,
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update IngestionRun {run_id}: {e}")

    # --- Run the ingestion pipeline ---
    try:
        from scripts.ingest_to_qdrant import load_pdf_documents, split_documents, ingest_to_qdrant
        from scripts.ingest_to_qdrant import update_db_statuses
        from ghana_legal.config import settings
        from pathlib import Path

        start_time = datetime.now(timezone.utc)

        # Resolve data directories (inside Modal container: /data/)
        project_root = Path("/root/src").resolve().parents[0]
        data_dirs = [
            Path("/data/ghana_legal/constitution"),
            Path("/data/ghana_legal/cases"),
            Path("/data/cases"),
        ]

        logger.info(f"Data directories: {[str(d) for d in data_dirs]}")
        for d in data_dirs:
            if d.exists():
                pdfs = list(d.rglob("*.pdf"))
                logger.info(f"  {d}: {len(pdfs)} PDFs")
            else:
                logger.warning(f"  {d}: DOES NOT EXIST")

        # Step 1: Load PDFs (filtered to pending cases via PostgreSQL)
        documents = load_pdf_documents(data_dirs, max_cases=max_cases)

        if not documents:
            logger.warning("No documents to process — all cases may already be indexed or no PDF matches found.")
            update_run(
                status="completed",
                completed_at=datetime.now(timezone.utc),
                result={"exit_code": 0, "summary": "No pending documents to process. All cases may already be indexed."},
            )
            return {"status": "completed", "documents": 0, "chunks": 0}

        # Log which case_ids were loaded (diagnostic for the numbers issue)
        loaded_case_ids = {doc.metadata.get("case_id") for doc in documents if doc.metadata.get("case_id")}
        logger.info(f"Loaded {len(documents)} pages from {len(loaded_case_ids)} cases: {list(loaded_case_ids)[:20]}")

        # Step 2: Split into chunks
        chunked_docs = split_documents(documents, chunk_size=512, chunk_overlap=100)

        # Step 3: Ingest to Qdrant Cloud
        stats = ingest_to_qdrant(chunked_docs)

        # Step 4: Update PostgreSQL — mark ingested cases as 'indexed'
        updated_count = 0
        if stats["successful"] > 0:
            # Derive case_id from the filename (e.g. GHADC_2026_2.pdf → GHADC_2026_2)
            case_law_ids = {
                doc.metadata.get("filename", "").replace(".pdf", "")
                for doc in documents
                if doc.metadata.get("source_type") == "case_law" and doc.metadata.get("filename")
            }
            case_law_ids.discard("")  # remove empty strings
            if case_law_ids:
                updated_count = update_db_statuses(case_law_ids)
                logger.info(f"Marked {updated_count} cases as 'indexed' in PostgreSQL")
            else:
                logger.warning("No case_law filenames found to mark as indexed")

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        summary = (
            f"✓ Ingested {stats['successful']} chunks from {len(loaded_case_ids)} cases in {elapsed:.0f}s. "
            f"DB updated: {updated_count} cases marked indexed."
        )
        logger.success(summary)

        update_run(
            status="completed",
            completed_at=datetime.now(timezone.utc),
            result={"exit_code": 0, "summary": summary},
        )

        return {"status": "completed", "documents": len(documents), "chunks": stats["successful"]}

    except Exception as e:
        logger.error(f"Ingestion failed: {e}\n{traceback.format_exc()}")
        update_run(
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error=str(e)[:500],
        )
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Dedicated Discovery Function — scrapes ghalii.org for new cases
# ---------------------------------------------------------------------------
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ghana-legal-secrets")],
    timeout=1800,  # 30 min — scraping + downloading PDFs takes time
    memory=1024,
)
def run_discovery(run_id: int, max_pages: int = 5):
    """Discover and download new cases from ghalii.org.

    Spawned asynchronously from the admin API via:
        run_discovery.spawn(run_id=..., max_pages=5)

    This function:
    1. Scrapes ghalii.org/judgments/all/ for case listings
    2. Filters out cases already in PostgreSQL
    3. Downloads PDFs for new cases to /data/cases/{court_id}/
    4. Inserts new rows into pipeline_cases (status='pending')
    5. Updates the DiscoveryRun row with results
    """
    import sys
    import os
    import traceback
    sys.path.insert(0, "/root/src")

    from datetime import datetime, timezone
    from loguru import logger

    logger.info(f"=== Modal run_discovery started | run_id={run_id} max_pages={max_pages} ===")

    # --- Helper to update the DiscoveryRun row ---
    def update_run(**fields):
        import psycopg
        import json as _json
        db_url = os.environ.get("DATABASE_URL", "")
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        if "pooler.supabase.com" in db_url and ":5432" in db_url:
            db_url = db_url.replace(":5432", ":6543")

        set_parts = []
        values = []
        for key, val in fields.items():
            set_parts.append(f"{key} = %s")
            if isinstance(val, dict):
                values.append(_json.dumps(val))
            else:
                values.append(val)
        values.append(run_id)

        try:
            with psycopg.connect(db_url, prepare_threshold=0) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE discovery_runs SET {', '.join(set_parts)} WHERE id = %s",
                        values,
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update DiscoveryRun {run_id}: {e}")

    # --- Run discovery ---
    try:
        from scripts.discover_cases import run_discovery as _discover
        from pathlib import Path

        result = _discover(max_pages=max_pages, data_dir=Path("/data"))

        summary = (
            f"Scraped {result['scraped']} cases from ghalii.org. "
            f"Found {result['new']} new cases. "
            f"Downloaded {result['downloaded']} PDFs. "
            f"Inserted {result['inserted']} into pipeline."
        )
        logger.success(summary)

        update_run(
            status="completed",
            completed_at=datetime.now(timezone.utc),
            result={**result, "summary": summary},
        )

        return {"status": "completed", **result}

    except Exception as e:
        logger.error(f"Discovery failed: {e}\n{traceback.format_exc()}")
        update_run(
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error=str(e)[:500],
        )
        return {"status": "failed", "error": str(e)}



@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ghana-legal-secrets")],
    timeout=300,
    memory=2048,
)
def verify_payloads():
    """One-shot: assert Qdrant payloads carry case_id + paragraph_id + paragraph_hash.

    Run with:  modal run modal_app.py::verify_payloads
    Returns 0 on pass, 1 on fail. Run after the post-PR1 re-ingestion finishes.
    """
    import sys
    sys.path.insert(0, "/root/src")
    sys.path.insert(0, "/root/src/scripts")

    from verify_payload_enrichment import main
    return main()


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ghana-legal-secrets")],
    timeout=3600,
    memory=2048,
)
def migrate_legacy_payloads():
    """Backfill case_id, paragraph_id, paragraph_hash on Qdrant points ingested
    before PR 1. Uses Qdrant batch_update_points with set_payload operations
    (additive — does not touch vectors or existing fields), so no Voyage AI
    re-embedding is needed.

    Idempotent: points that already carry case_id+paragraph_id+paragraph_hash
    are skipped, so re-running after a partial completion picks up where it
    left off without redoing any work.

    Run with:  modal run modal_app.py::migrate_legacy_payloads
    """
    import hashlib
    import re
    import sys
    sys.path.insert(0, "/root/src")

    from loguru import logger
    from qdrant_client import models
    from ghana_legal.application.rag.qdrant_retriever import get_qdrant_retriever
    from ghana_legal.config import settings

    normalize_re = re.compile(r"\s+")

    def phash(text: str) -> str:
        return hashlib.sha1(
            normalize_re.sub(" ", text).strip().lower().encode("utf-8")
        ).hexdigest()[:10]

    retriever = get_qdrant_retriever(
        collection_name="legal_docs",
        embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
        k=10,
        device=settings.RAG_DEVICE,
        use_reranker=False,
    )
    client = retriever.client

    cursor = None
    migrated = 0
    skipped = 0
    page_size = 200
    batch_num = 0

    while True:
        points, cursor = client.scroll(
            collection_name="legal_docs",
            limit=page_size,
            offset=cursor,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break

        operations = []
        for p in points:
            payload = p.payload or {}
            # Skip post-PR1 or already-migrated points.
            if payload.get("case_id") and payload.get("paragraph_hash") and payload.get("paragraph_id"):
                skipped += 1
                continue

            filename = payload.get("filename", "") or ""
            case_id = filename[:-4] if filename.endswith(".pdf") else (filename or None)
            chunk_index = payload.get("chunk_index", 0)
            page_content = payload.get("page_content", "") or ""

            new_fields = {}
            if case_id and not payload.get("case_id"):
                new_fields["case_id"] = case_id
            if not payload.get("paragraph_id"):
                # legacy.* prefix marks points lacking real page_number metadata;
                # validator can still bind on (case_id, paragraph_id) uniqueness.
                new_fields["paragraph_id"] = f"legacy.c{chunk_index}"
            if page_content and not payload.get("paragraph_hash"):
                new_fields["paragraph_hash"] = phash(page_content)

            if new_fields:
                operations.append(
                    models.SetPayloadOperation(
                        set_payload=models.SetPayload(
                            payload=new_fields,
                            points=[p.id],
                        )
                    )
                )

        if operations:
            client.batch_update_points(
                collection_name="legal_docs",
                update_operations=operations,
                wait=False,
            )
            migrated += len(operations)

        batch_num += 1
        if batch_num % 10 == 0:
            logger.info(f"… {migrated} migrated, {skipped} skipped (batch {batch_num})")

        if cursor is None:
            break

    logger.success(f"Migration complete: {migrated} migrated, {skipped} already current")
    return {"migrated": migrated, "skipped": skipped}

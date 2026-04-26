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
    timeout=900,  # 15 min — ingestion background task needs time to complete
    memory=2048,
)
@modal.asgi_app()
def api():
    """Serve the FastAPI application."""
    import sys
    sys.path.insert(0, "/root/src")

    from ghana_legal.infrastructure.api import app as fastapi_app
    return fastapi_app


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

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

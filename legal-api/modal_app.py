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

manifest_volume = modal.NetworkFileSystem.from_name("ghana-legal-manifest-nfs", create_if_missing=True)

# ---------------------------------------------------------------------------
# FastAPI Web Endpoint
# ---------------------------------------------------------------------------
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ghana-legal-secrets")],
    timeout=300,  # 5 min max per request (SSE streaming)
    memory=2048,
    network_file_systems={"/manifest_state": manifest_volume}
)
@modal.asgi_app()
def api():
    """Serve the FastAPI application."""
    import sys
    sys.path.insert(0, "/root/src")

    from ghana_legal.infrastructure.api import app as fastapi_app
    return fastapi_app

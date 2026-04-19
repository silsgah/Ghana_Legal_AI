#!/usr/bin/env python3
"""
Scratch script: Wipe the Qdrant 'legal_docs' collection entirely.

This is required when switching embedding models (e.g., from HuggingFace 384-dim
to Voyage AI 1024-dim) because Qdrant enforces a fixed vector dimension per collection.
Running this script deletes the entire collection. It will be recreated automatically
with the correct 1024-dimension configuration on the next ingest run.

Usage (from legal-api/src/):
    python scratch/wipe_qdrant.py
"""
import os
import sys
import requests
from pathlib import Path

# Add src to path and load .env
src_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(src_dir))
from dotenv import load_dotenv
load_dotenv(src_dir / ".env")

COLLECTION_NAME = "legal_docs"

def main():
    url = os.getenv("QDRANT_URL", "").rstrip("/")
    api_key = os.getenv("QDRANT_API_KEY", "")

    if not url or not api_key:
        print("❌  QDRANT_URL and QDRANT_API_KEY must be set in .env")
        sys.exit(1)

    # Some Qdrant cloud URLs need the port 6333 for REST if not provided
    if "cloud.qdrant.io" in url and not url.endswith(":6333"):
        url = f"{url}:6333"

    print(f"Connecting to Qdrant REST API: {url[:55]}...")
    
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    # List collections
    try:
        resp = requests.get(f"{url}/collections", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        collections = [c["name"] for c in data.get("result", {}).get("collections", [])]
    except Exception as e:
        print(f"❌ Failed to connect or list collections: {e}")
        # Could be port 443 is correct for this specific cluster type. Let's fallback to standard port if 6333 failed
        if ":6333" in url:
            url = url.replace(":6333", "")
            print(f"Retrying without explicit port: {url[:55]}...")
            try:
                resp = requests.get(f"{url}/collections", headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                collections = [c["name"] for c in data.get("result", {}).get("collections", [])]
            except Exception as e2:
                print(f"❌ Failed fallback connection: {e2}")
                sys.exit(1)
        else:
            sys.exit(1)

    print(f"\nExisting collections: {collections}")

    if COLLECTION_NAME not in collections:
        print(f"\n⚠️  Collection '{COLLECTION_NAME}' does not exist — nothing to wipe.")
        return

    confirm = input(f"\n⚠️  Are you sure you want to DELETE '{COLLECTION_NAME}' and ALL its vectors? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted — no changes made.")
        return

    print(f"\nDeleting collection '{COLLECTION_NAME}'...")
    try:
        delete_resp = requests.delete(f"{url}/collections/{COLLECTION_NAME}", headers=headers, timeout=30)
        delete_resp.raise_for_status()
        print(f"✅  Collection '{COLLECTION_NAME}' deleted successfully.")
        print("\nNext step: run the ingestion script to re-embed with voyage-law-2.")
    except Exception as e:
        print(f"❌ Failed to delete collection: {e}")

if __name__ == "__main__":
    main()

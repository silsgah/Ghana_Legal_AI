
import sys
import os
from pathlib import Path
from loguru import logger

# Ensure legal-api/src is in python path to import ghana_legal
# This assumes the standard directory structure relative to this file
# airflow/plugins/ghana_legal/indexing.py -> ../../../legal-api/src
current_file = Path(__file__).resolve()
project_root = current_file.parents[3] # ghana-legal-ai
legal_api_src = project_root / "legal-api" / "src"

if str(legal_api_src) not in sys.path:
    sys.path.append(str(legal_api_src))

try:
    from ghana_legal.application.data.ingest import ingest_data
except ImportError as e:
    logger.error(f"Failed to import ghana_legal: {e}")
    # Fallback or re-raise depending on how strict we want to be during parsing
    ingest_data = None

def index_new_cases():
    """
    Wrapper for the main Ingestion pipeline.
    This triggers the embedding and vector store update.
    Idempotency is handled by the ingest logic (checking existing IDs).
    """
    if not ingest_data:
        raise ImportError("Could not import ingest_data. Check PYTHONPATH.")
        
    logger.info("Starting automated indexing of new cases...")
    ingest_data()
    logger.info("Indexing complete.")
    return "Indexing Successful"

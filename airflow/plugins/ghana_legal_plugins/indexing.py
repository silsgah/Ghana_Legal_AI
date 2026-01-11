
import sys
import os
from pathlib import Path
from loguru import logger

def index_new_cases():
    """
    Wrapper for the main Ingestion pipeline.
    This triggers the embedding and vector store update.
    Idempotency is handled by the ingest logic (checking existing IDs).
    """
    # 1. Setup Path Resolution (Runtime)
    # Use the environment variable defined in docker-compose.yml
    project_root_str = os.environ.get("PROJECT_ROOT")

    if project_root_str:
        project_root = Path(project_root_str)
    else:
        # Fallback for local testing (relative path)
        # airflow/plugins/ghana_legal/indexing.py -> ../../../
        current_file = Path(__file__).resolve()
        project_root = current_file.parents[3] 

    legal_api_src = project_root / "legal-api" / "src"
    
    # 2. Debug Logging
    logger.info(f"DEBUG: Project Root calculated as: {project_root}")
    logger.info(f"DEBUG: Appending to sys.path: {legal_api_src}")
    
    if str(legal_api_src) not in sys.path:
        sys.path.append(str(legal_api_src))
        
    # Check directory existence
    if legal_api_src.exists():
        try:
            contents = os.listdir(legal_api_src)
            logger.info(f"DEBUG: Contents of src: {contents}")
            # Check specifically for ghana_legal package
            if "ghana_legal" in contents:
                logger.info("DEBUG: Found 'ghana_legal' package in src.")
            else:
                logger.error("DEBUG: 'ghana_legal' package NOT found in src!")
        except Exception as e:
             logger.error(f"DEBUG: Error listing src contents: {e}")
    else:
        logger.error(f"DEBUG: src directory NOT FOUND at {legal_api_src}")

    # 3. Lazy Import & Execution
    try:
        from ghana_legal.application.data.ingest import ingest_data
    except ImportError as e:
        logger.error(f"Failed to import ghana_legal: {e}")
        logger.error(f"Current sys.path: {sys.path}")
        raise ImportError(f"Could not import ingest_data. Check Worker Logs. Error: {e}")
        
    logger.info("Starting automated indexing of new cases...")
    ingest_data()
    logger.info("Indexing complete.")
    return "Indexing Successful"

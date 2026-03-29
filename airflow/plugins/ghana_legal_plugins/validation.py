"""PDF validation utilities for the ingestion pipeline."""

import logging
from pathlib import Path

logger = logging.getLogger("airflow.task")


def validate_pdf(path: Path) -> bool:
    """Basic PDF validation: magic bytes, minimum size, PyPDF readable."""
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return False

    # Minimum size check (>1KB)
    if path.stat().st_size < 1024:
        logger.warning(f"PDF too small ({path.stat().st_size} bytes): {path.name}")
        return False

    # Magic bytes check
    with open(path, "rb") as f:
        header = f.read(4)
    if header != b"%PDF":
        logger.warning(f"Invalid PDF header for {path.name}: {header!r}")
        return False

    # PyPDF readability check
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        if len(reader.pages) == 0:
            logger.warning(f"PDF has 0 pages: {path.name}")
            return False
    except Exception as e:
        logger.warning(f"PyPDF failed to read {path.name}: {e}")
        return False

    return True


def validate_content_extraction(path: Path) -> bool:
    """Verify that meaningful text can be extracted from the PDF."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            if len(text) > 100:
                return True
        logger.warning(f"Extracted only {len(text)} chars from {path.name}")
        return len(text) > 100
    except Exception as e:
        logger.warning(f"Content extraction failed for {path.name}: {e}")
        return False

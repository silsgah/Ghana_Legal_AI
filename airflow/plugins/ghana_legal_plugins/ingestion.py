"""Qdrant ingestion for newly processed cases.

All heavy imports (langchain, sentence-transformers, qdrant) are deferred
to function calls so Airflow's plugin scanner doesn't block startup.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger("airflow.task")

# Embedding constants (mirror legal-api/src/ghana_legal/config.py)
EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
COLLECTION_NAME = "legal_docs"


def sanitize_metadata_for_qdrant(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize metadata for Qdrant payload compatibility."""
    import json as _json
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            if value:
                sanitized[key] = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            sanitized[key] = _json.dumps(value)
        else:
            sanitized[key] = str(value)
    return sanitized


def split_documents(documents, chunk_size: int = 512, chunk_overlap: int = 100):
    """Split documents into chunks for embeddings."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    chunked = []
    for doc in documents:
        chunks = splitter.split_documents([doc])
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        chunked.extend(chunks)
    return chunked


def _get_retriever():
    """Lazily import and return the Qdrant retriever."""
    project_root = os.environ.get("PROJECT_ROOT", "")
    if project_root:
        legal_api_src = os.path.join(project_root, "legal-api", "src")
        if legal_api_src not in sys.path:
            sys.path.insert(0, legal_api_src)

    from ghana_legal.application.rag.qdrant_retriever import get_qdrant_retriever
    return get_qdrant_retriever(
        collection_name=COLLECTION_NAME,
        embedding_model_id=EMBEDDING_MODEL_ID,
        k=3,
        device="cpu",
        use_reranker=False,
    )


def ingest_new_cases(pdf_paths: List[str], case_metadata: Dict[str, Dict]) -> Dict[str, Any]:
    """Load specified PDFs, chunk, enrich with metadata, and upsert to Qdrant.

    Args:
        pdf_paths: List of absolute paths to PDF files to ingest.
        case_metadata: Dict mapping case_id -> metadata dict from scraper.

    Returns:
        Stats dict with successful/failed counts.
    """
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_core.documents import Document

    if not pdf_paths:
        logger.info("No PDFs to ingest.")
        return {"total_chunks": 0, "successful": 0, "failed": 0}

    retriever = _get_retriever()

    # Load PDFs into documents
    documents = []
    for pdf_path in pdf_paths:
        path = Path(pdf_path)
        try:
            loader = PyPDFLoader(str(path))
            pages = loader.load()
            if not pages:
                logger.warning(f"No content from {path.name}")
                continue

            combined = "\n\n".join(p.page_content for p in pages)

            file_meta = {
                "filename": path.name,
                "source": str(path),
                "total_pages": len(pages),
                "document_type": "case_law",
                "jurisdiction": "Ghana",
                "source_type": "case_law",
            }

            # Enrich with scraped metadata if available
            for case_id, meta in case_metadata.items():
                if case_id in str(path) or meta.get("pdf_path") == str(path):
                    file_meta.update({
                        k: v for k, v in meta.items()
                        if k not in ("pdf_path",) and v
                    })
                    file_meta["case_id"] = case_id
                    break

            doc = Document(page_content=combined, metadata=file_meta)
            documents.append(doc)

        except Exception as e:
            logger.error(f"Failed to load {path.name}: {e}")

    if not documents:
        return {"total_chunks": 0, "successful": 0, "failed": 0}

    # Chunk
    chunked_docs = split_documents(documents)
    logger.info(f"Split {len(documents)} documents into {len(chunked_docs)} chunks")

    # Upsert in batches
    batch_size = 20
    successful = 0
    failed = 0

    for i in range(0, len(chunked_docs), batch_size):
        batch = chunked_docs[i:i + batch_size]
        try:
            texts = [doc.page_content for doc in batch]
            metadatas = [sanitize_metadata_for_qdrant(doc.metadata) for doc in batch]
            ids = [
                f"{doc.metadata.get('court_id', 'GHASC')}_{doc.metadata.get('filename', 'unknown')}_{doc.metadata.get('chunk_index', 0)}"
                for doc in batch
            ]
            retriever.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            successful += len(batch)
        except Exception as e:
            logger.error(f"Batch ingestion failed: {e}")
            failed += len(batch)

    stats = {
        "total_chunks": len(chunked_docs),
        "successful": successful,
        "failed": failed,
    }
    logger.info(f"Ingestion complete: {successful} successful, {failed} failed out of {len(chunked_docs)} chunks")
    return stats

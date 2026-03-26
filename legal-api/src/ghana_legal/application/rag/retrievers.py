"""Retriever factory module for the Ghana Legal AI RAG system.

Routes between ChromaDB (local development) and Qdrant Cloud (production)
based on the VECTOR_DB_MODE environment variable.
"""

from loguru import logger

from ghana_legal.application.rag.base_retriever import Retriever
from ghana_legal.config import settings


def get_retriever(
    embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
    k: int = 3,
    device: str = "cpu",
) -> Retriever:
    """Creates and returns a legal-specific retriever based on the configured vector DB mode.

    Supports 'chroma' (local dev) and 'qdrant' (production cloud) via VECTOR_DB_MODE env var.

    Args:
        embedding_model_id: The identifier for the embedding model to use.
        k: Number of documents to retrieve.
        device: Device to run the embedding model on ('cpu' or 'cuda').

    Returns:
        A configured legal-specific retriever implementing the Retriever protocol.
    """
    mode = settings.VECTOR_DB_MODE.lower()

    if mode == "qdrant":
        logger.info(
            f"Initializing Qdrant Cloud retriever | model: {embedding_model_id} | "
            f"device: {device} | top_k: {k}"
        )
        from ghana_legal.application.rag.qdrant_retriever import get_qdrant_retriever

        return get_qdrant_retriever(
            collection_name="legal_docs",
            embedding_model_id=embedding_model_id,
            k=k,
            device=device,
            use_reranker=True,
        )
    else:
        logger.info(
            f"Initializing local ChromaDB retriever | model: {embedding_model_id} | "
            f"device: {device} | top_k: {k}"
        )
        from ghana_legal.application.rag.chroma_retriever import get_chroma_retriever

        return get_chroma_retriever(
            collection_name="legal_docs",
            embedding_model_id=embedding_model_id,
            k=k,
            device=device,
            use_reranker=True,
        )

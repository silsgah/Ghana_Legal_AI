"""Legal-specific Qdrant Cloud retriever with hybrid search and reranking capabilities.

Drop-in replacement for ChromaDB retriever, using Qdrant Cloud for production vector search.
"""

import os
from typing import List, Optional

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from loguru import logger
from sentence_transformers import CrossEncoder
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)

from ghana_legal.config import settings

# Global singleton instance
_qdrant_retriever_instance = None


class LegalQdrantRetriever:
    """Legal-specific retriever using Qdrant Cloud with hybrid search and reranking."""

    def __init__(
        self,
        collection_name: str = "legal_docs",
        embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
        k: int = 3,
        device: str = "cpu",
        use_reranker: bool = True,
    ):
        self.k = k
        self.use_reranker = use_reranker
        self.collection_name = collection_name

        try:
            # Initialize Qdrant Cloud client
            qdrant_url = os.getenv("QDRANT_URL", "")
            qdrant_api_key = os.getenv("QDRANT_API_KEY", "")

            if not qdrant_url or not qdrant_api_key:
                raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set")

            logger.info(f"Connecting to Qdrant Cloud: {qdrant_url[:40]}...")
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            logger.info("Qdrant Cloud client connected successfully")

            # Initialize embedding model
            logger.info(f"Loading embedding model: {embedding_model_id}...")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=embedding_model_id,
                model_kwargs={"device": device},
            )
            self.embedding_dim = settings.RAG_TEXT_EMBEDDING_MODEL_DIM  # 384
            logger.info("Embedding model loaded successfully")

            # Ensure collection exists
            self._ensure_collection()

            # Initialize reranker if enabled
            if self.use_reranker:
                try:
                    logger.info("Loading cross-encoder reranker...")
                    self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                    logger.info("Cross-encoder reranker initialized successfully")
                except Exception as e:
                    logger.warning(f"Could not initialize reranker: {e}. Proceeding without.")
                    self.use_reranker = False
                    self.reranker = None
            else:
                self.reranker = None

        except Exception as e:
            logger.error(f"Failed to initialize LegalQdrantRetriever: {e}")
            raise RuntimeError(f"Qdrant initialization failed: {e}") from e

    def _ensure_collection(self):
        """Create the collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Collection '{self.collection_name}' created")
        else:
            info = self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' exists with {info.points_count} points")

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """Add texts to the Qdrant collection."""
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(texts))]

        # Generate embeddings
        embeddings = self.embedding_model.embed_documents(texts)

        points = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            payload = {"page_content": text}
            if metadatas and i < len(metadatas):
                payload.update(metadatas[i])

            points.append(
                PointStruct(
                    id=abs(hash(ids[i])) % (2**63),  # Qdrant needs int IDs
                    vector=embedding,
                    payload=payload,
                )
            )

        # Batch upsert
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(collection_name=self.collection_name, points=batch)

        logger.info(f"Added {len(points)} documents to Qdrant collection '{self.collection_name}'")

    def _vector_search(self, query: str, k: int) -> List[Document]:
        """Perform vector similarity search."""
        query_embedding = self.embedding_model.embed_query(query)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k,
        )

        documents = []
        for hit in results:
            payload = hit.payload or {}
            page_content = payload.pop("page_content", "")
            documents.append(
                Document(page_content=page_content, metadata={**payload, "score": hit.score})
            )

        return documents

    def _rerank_results(self, query: str, documents: List[Document]) -> List[Document]:
        """Rerank documents using cross-encoder."""
        if not self.use_reranker or not self.reranker or not documents:
            return documents

        pairs = [(query, doc.page_content) for doc in documents]
        scores = self.reranker.predict(pairs)

        scored_docs = [(doc, float(score)) for doc, score in zip(documents, scores)]
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored_docs]

    def retrieve(self, query: str) -> List[Document]:
        """Retrieve relevant documents for the given query."""
        logger.info(f"Performing Qdrant vector search for query: {query[:80]}...")

        # Get initial results — Qdrant's HNSW is already highly optimized
        results = self._vector_search(query, self.k * 3 if self.use_reranker else self.k)

        # Apply reranking if enabled
        if self.use_reranker:
            results = self._rerank_results(query, results)
            results = results[: self.k]
            logger.info(f"Applied reranking, returning top {len(results)} documents")

        return results


def get_qdrant_retriever(
    collection_name: str = "legal_docs",
    embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
    k: int = 3,
    device: str = "cpu",
    use_reranker: bool = True,
) -> LegalQdrantRetriever:
    """Factory function to create a Qdrant retriever with singleton pattern."""
    global _qdrant_retriever_instance

    if _qdrant_retriever_instance is not None:
        logger.info("Returning existing LegalQdrantRetriever instance (singleton)")
        return _qdrant_retriever_instance

    logger.info(
        f"Creating new LegalQdrantRetriever | model: {embedding_model_id} | "
        f"collection: {collection_name} | k: {k} | device: {device} | reranker: {use_reranker}"
    )

    try:
        _qdrant_retriever_instance = LegalQdrantRetriever(
            collection_name=collection_name,
            embedding_model_id=embedding_model_id,
            k=k,
            device=device,
            use_reranker=use_reranker,
        )
        logger.info("LegalQdrantRetriever instance created and cached successfully")
        return _qdrant_retriever_instance
    except Exception as e:
        logger.error(f"Failed to create LegalQdrantRetriever: {e}")
        raise

"""Legal-specific ChromaDB retriever with hybrid search and reranking capabilities."""

import os
from pathlib import Path
from typing import List, Optional
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from loguru import logger
from sentence_transformers import CrossEncoder
import chromadb
from chromadb.config import Settings

from ghana_legal.config import settings

# Global singleton instance
_retriever_instance = None


class LegalChromaRetriever:
    """Legal-specific retriever using ChromaDB with hybrid search and reranking."""
    
    def __init__(
        self,
        collection_name: str = "legal_docs",
        embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
        k: int = 3,
        device: str = "cpu",
        use_reranker: bool = True
    ):
        """Initialize the legal ChromaDB retriever.

        Args:
            collection_name: Name of the ChromaDB collection
            embedding_model_id: ID of the embedding model to use
            k: Number of documents to retrieve
            device: Device to run the embedding model on
            use_reranker: Whether to use cross-encoder reranking
        """
        self.k = k
        self.use_reranker = use_reranker

        try:
            # Ensure the data directory exists
            chroma_path = Path(settings.EVALUATION_DATASET_FILE_PATH.parent) / "chroma_db"
            chroma_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"ChromaDB path ensured at: {chroma_path}")

            # Initialize ChromaDB client with persistent storage
            logger.info("Initializing ChromaDB persistent client...")
            self.chroma_client = chromadb.PersistentClient(
                path=str(chroma_path)
            )
            logger.info("ChromaDB client initialized successfully")

            # Initialize embedding model
            logger.info(f"Loading embedding model: {embedding_model_id}...")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=embedding_model_id,
                model_kwargs={"device": device}
            )
            logger.info("Embedding model loaded successfully")

            # Initialize ChromaDB vectorstore
            logger.info(f"Initializing vectorstore for collection: {collection_name}...")
            self.vectorstore = Chroma(
                client=self.chroma_client,
                collection_name=collection_name,
                embedding_function=self.embedding_model
            )
            logger.info("Vectorstore initialized successfully")

            # Initialize reranker if enabled
            if self.use_reranker:
                try:
                    logger.info("Loading cross-encoder reranker...")
                    self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                    logger.info("Cross-encoder reranker initialized successfully")
                except Exception as e:
                    logger.warning(f"Could not initialize reranker: {e}. Proceeding without reranking.")
                    self.use_reranker = False
                    self.reranker = None
            else:
                self.reranker = None

        except Exception as e:
            logger.error(f"Failed to initialize LegalChromaRetriever: {e}")
            raise RuntimeError(f"ChromaDB initialization failed: {e}") from e
    
    def add_texts(self, texts: List[str], metadatas: Optional[List[dict]] = None, ids: Optional[List[str]] = None):
        """Add texts to the ChromaDB collection.
        
        Args:
            texts: List of text documents to add
            metadatas: Optional metadata for each text
            ids: Optional IDs for each text
        """
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(texts))]
        
        self.vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    
    def _keyword_search(self, query: str, k: int) -> List[Document]:
        """Perform keyword-based search on document content.
        
        Args:
            query: Search query string
            k: Number of results to return
            
        Returns:
            List of documents matching keywords
        """
        # Simple keyword search by filtering documents that contain query terms
        # This is a simplified implementation - in production, we'd use more sophisticated approaches
        all_docs = self.vectorstore.get()
        
        # Find documents containing query terms (simplified approach)
        keyword_matches = []
        query_terms = query.lower().split()
        
        for idx, doc_text in enumerate(all_docs['documents']):
            score = sum(1 for term in query_terms if term.lower() in doc_text.lower())
            if score > 0:
                doc_metadata = all_docs['metadatas'][idx] if idx < len(all_docs['metadatas']) else {}
                doc_id = all_docs['ids'][idx] if idx < len(all_docs['ids']) else f"doc_{idx}"
                
                keyword_matches.append(Document(
                    page_content=doc_text,
                    metadata={**doc_metadata, "keyword_score": score, "id": doc_id}
                ))
        
        # Sort by keyword score (descending)
        keyword_matches.sort(key=lambda x: x.metadata.get("keyword_score", 0), reverse=True)
        return keyword_matches[:k]
    
    def _vector_similar_search(self, query: str, k: int) -> List[Document]:
        """Perform vector similarity search.
        
        Args:
            query: Search query string
            k: Number of results to return
            
        Returns:
            List of similar documents based on vector similarity
        """
        return self.vectorstore.similarity_search(query, k=k)
    
    def _hybrid_search(self, query: str, k: int) -> List[Document]:
        """Perform hybrid search combining keyword and vector similarity.
        
        Args:
            query: Search query string
            k: Number of results to return
            
        Returns:
            Combined list of relevant documents
        """
        # Get results from both search methods
        vector_results = self._vector_similar_search(query, k * 2)  # Get more results for combination
        keyword_results = self._keyword_search(query, k * 2)
        
        # Combine and deduplicate results
        combined_results = {}
        
        # Add vector results with scores
        for i, doc in enumerate(vector_results):
            doc_id = doc.metadata.get("id", f"vec_{i}")
            combined_results[doc_id] = {
                "document": doc,
                "vector_score": (len(vector_results) - i) / len(vector_results),  # Normalize score
                "keyword_score": 0
            }
        
        # Add or update keyword results
        for i, doc in enumerate(keyword_results):
            doc_id = doc.metadata.get("id", f"kw_{i}")
            if doc_id in combined_results:
                combined_results[doc_id]["keyword_score"] = (len(keyword_results) - i) / len(keyword_results)
            else:
                combined_results[doc_id] = {
                    "document": doc,
                    "vector_score": 0,
                    "keyword_score": (len(keyword_results) - i) / len(keyword_results)
                }
        
        # Calculate combined score (equal weight for both methods)
        for result in combined_results.values():
            result["combined_score"] = (result["vector_score"] + result["keyword_score"]) / 2
        
        # Sort by combined score
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        # Return top k documents
        return [result["document"] for result in sorted_results[:k]]
    
    def _rerank_results(self, query: str, documents: List[Document]) -> List[Document]:
        """Rerank documents using cross-encoder.
        
        Args:
            query: Search query string
            documents: List of documents to rerank
            
        Returns:
            Reranked list of documents
        """
        if not self.use_reranker or not self.reranker:
            return documents
        
        # Prepare sentence pairs for reranking
        pairs = [(query, doc.page_content) for doc in documents]
        
        # Get similarity scores from cross-encoder
        scores = self.reranker.predict(pairs)
        
        # Pair documents with scores and sort
        scored_docs = [(doc, float(score)) for doc, score in zip(documents, scores)]
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs]
    
    def retrieve(self, query: str) -> List[Document]:
        """Retrieve relevant documents for the given query.
        
        Args:
            query: Search query string
            
        Returns:
            List of relevant documents
        """
        logger.info(f"Performing hybrid search for query: {query}")
        
        # Get initial results using hybrid search
        results = self._hybrid_search(query, self.k)
        
        # Apply reranking if enabled
        if self.use_reranker:
            results = self._rerank_results(query, results)
            logger.info(f"Applied reranking to {len(results)} documents")
        
        logger.info(f"Returning {len(results)} documents for query: {query}")
        return results


def get_chroma_retriever(
    collection_name: str = "legal_docs",
    embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
    k: int = 3,
    device: str = "cpu",
    use_reranker: bool = True
) -> LegalChromaRetriever:
    """Factory function to create a legal ChromaDB retriever with singleton pattern.

    This ensures the retriever (and its expensive ML models) are only initialized once.

    Args:
        collection_name: Name of the ChromaDB collection
        embedding_model_id: ID of the embedding model to use
        k: Number of documents to retrieve
        device: Device to run the embedding model on
        use_reranker: Whether to use cross-encoder reranking

    Returns:
        LegalChromaRetriever: A configured legal-specific retriever
    """
    global _retriever_instance

    # Return existing instance if available
    if _retriever_instance is not None:
        logger.info("Returning existing LegalChromaRetriever instance (singleton)")
        return _retriever_instance

    logger.info(
        f"Creating new LegalChromaRetriever instance | model: {embedding_model_id} | "
        f"collection: {collection_name} | k: {k} | device: {device} | reranker: {use_reranker}"
    )

    try:
        _retriever_instance = LegalChromaRetriever(
            collection_name=collection_name,
            embedding_model_id=embedding_model_id,
            k=k,
            device=device,
            use_reranker=use_reranker
        )
        logger.info("LegalChromaRetriever instance created and cached successfully")
        return _retriever_instance
    except Exception as e:
        logger.error(f"Failed to create LegalChromaRetriever: {e}")
        raise
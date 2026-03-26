"""Long-term memory management for the Ghana Legal AI system.

Provides document ingestion (LongTermMemoryCreator) and retrieval (LongTermMemoryRetriever)
that work with any vector database backend via the Retriever protocol.
"""

from langchain_core.documents import Document
from loguru import logger

from ghana_legal.application.data import deduplicate_documents, get_extraction_generator
from ghana_legal.application.rag.base_retriever import Retriever
from ghana_legal.application.rag.retrievers import get_retriever
from ghana_legal.application.rag.splitters import Splitter, get_splitter
from ghana_legal.config import settings
from ghana_legal.domain.legal_expert import LegalExpertExtract
from ghana_legal.application.rag.legal_parser import get_legal_parser, LegalDocument


class LongTermMemoryCreator:
    """Ingests legal documents into the vector store with metadata enrichment."""

    def __init__(self, retriever: Retriever, splitter: Splitter) -> None:
        self.retriever = retriever
        self.splitter = splitter
        self.legal_parser = get_legal_parser()

    @classmethod
    def build_from_settings(cls) -> "LongTermMemoryCreator":
        retriever = get_retriever(
            embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
            k=settings.RAG_TOP_K,
            device=settings.RAG_DEVICE,
        )
        splitter = get_splitter(chunk_size=settings.RAG_CHUNK_SIZE)

        return cls(retriever, splitter)

    def __call__(self, experts: list[LegalExpertExtract]) -> None:
        if len(experts) == 0:
            logger.warning("No experts to extract. Exiting.")
            return

        extraction_generator = get_extraction_generator(experts)
        for expert_name, docs in extraction_generator:
            chunked_docs = self.splitter.split_documents(docs)
            chunked_docs = deduplicate_documents(chunked_docs, threshold=0.7)

            # Prepare batch data for ingestion
            texts = []
            metadatas = []
            ids = []

            for i, doc in enumerate(chunked_docs):
                # Parse document to extract legal structure
                legal_doc = self.legal_parser.parse_document(
                    doc.page_content, source=expert_name
                )

                # Build structured metadata
                metadata = {
                    **doc.metadata,
                    "expert_type": expert_name,
                    "title": legal_doc.title,
                    "article": legal_doc.article,
                    "section": legal_doc.section,
                    "subsection": legal_doc.subsection,
                    "court": legal_doc.court,
                    "case_number": legal_doc.case_number,
                    "date": legal_doc.date,
                    "citations": legal_doc.citations,
                    "jurisdiction": legal_doc.jurisdiction,
                    "document_type": legal_doc.document_type,
                }

                texts.append(doc.page_content)
                metadatas.append(metadata)
                ids.append(f"{expert_name}_doc_{i}")

            # Use the Retriever protocol's add_texts method (works for both ChromaDB and Qdrant)
            if texts:
                self.retriever.add_texts(texts=texts, metadatas=metadatas, ids=ids)
                logger.info(
                    f"Ingested {len(texts)} chunks for expert '{expert_name}'"
                )


class LongTermMemoryRetriever:
    """Retrieves relevant legal documents from the vector store."""

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    @classmethod
    def build_from_settings(cls) -> "LongTermMemoryRetriever":
        retriever = get_retriever(
            embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
            k=settings.RAG_TOP_K,
            device=settings.RAG_DEVICE,
        )

        return cls(retriever)

    def __call__(self, query: str) -> list[Document]:
        """Retrieve documents using the configured retriever's hybrid search + reranking."""
        return self.retriever.retrieve(query)

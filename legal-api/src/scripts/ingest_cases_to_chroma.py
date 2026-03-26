#!/usr/bin/env python3
"""
Comprehensive script to ingest Ghana Supreme Court case PDFs into ChromaDB.

This script:
1. Loads all PDFs from data/cases/
2. Parses legal structure (case names, citations, dates)
3. Splits into optimal chunks
4. Deduplicates content
5. Generates embeddings
6. Stores in ChromaDB with rich metadata
7. Provides detailed progress and statistics
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import re

# Add src to path for imports
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
sys.path.insert(0, str(src_dir))

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from tqdm import tqdm

from ghana_legal.config import settings
from ghana_legal.application.rag.chroma_retriever import get_chroma_retriever
from ghana_legal.application.rag.legal_parser import LegalTextParser
from ghana_legal.application.data.deduplicate_documents import deduplicate_documents


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


class CaseMetadataExtractor:
    """Extract metadata from Ghana Supreme Court case filenames and content."""

    @staticmethod
    def extract_from_filename(filename: str) -> Dict[str, Any]:
        """
        Extract metadata from standardized case filename.

        Format: Plaintiff_v_Defendant_CaseNumber_Year_Court_CaseID_Date.pdf
        Example: Adjei_v_Mckorley_J4012024_2025_GHASC_40_25_June_2025.pdf
        """
        metadata = {
            "filename": filename,
            "document_type": "case_law",
            "jurisdiction": "Ghana",
            "court": "Supreme Court"
        }

        # Remove .pdf extension
        name = filename.replace(".pdf", "")

        # Try to extract parties (everything before first J and year pattern)
        parties_match = re.match(r"^(.+?)_(?:J\d+|VRS)", name, re.IGNORECASE)
        if parties_match:
            parties = parties_match.group(1).replace("_", " ")
            metadata["parties"] = parties

            # Try to split into plaintiff and defendant
            if " v " in parties.lower():
                parts = re.split(r'\s+v\s+', parties, flags=re.IGNORECASE)
                if len(parts) == 2:
                    metadata["plaintiff"] = parts[0].strip()
                    metadata["defendant"] = parts[1].strip()
            elif " vrs " in parties.lower():
                parts = re.split(r'\s+vrs\s+', parties, flags=re.IGNORECASE)
                if len(parts) == 2:
                    metadata["plaintiff"] = parts[0].strip()
                    metadata["defendant"] = parts[1].strip()

        # Extract case number (J followed by digits)
        case_num_match = re.search(r'J(\d+/?\d*)', name)
        if case_num_match:
            metadata["case_number"] = case_num_match.group(0)

        # Extract year
        year_match = re.search(r'_(\d{4})_', name)
        if year_match:
            metadata["year"] = int(year_match.group(1))

        # Extract court identifier
        if "GHASC" in name:
            metadata["court"] = "Ghana Supreme Court"
            metadata["court_code"] = "GHASC"
        elif "GHACA" in name:
            metadata["court"] = "Ghana Court of Appeal"
            metadata["court_code"] = "GHACA"

        # Extract date
        date_match = re.search(r'(\d{1,2})_([A-Za-z]+)_(\d{4})', name)
        if date_match:
            day = date_match.group(1)
            month = date_match.group(2)
            year = date_match.group(3)
            metadata["date_string"] = f"{day} {month} {year}"

        return metadata

    @staticmethod
    def extract_from_content(content: str) -> Dict[str, Any]:
        """Extract additional metadata from case content."""
        metadata = {}

        # Extract citations (e.g., [2025] GHASC 40)
        citation_pattern = r'\[(\d{4})\]\s+(GHASC|GHACA)\s+(\d+)'
        citations = re.findall(citation_pattern, content)
        if citations:
            metadata["citations"] = [f"[{c[0]}] {c[1]} {c[2]}" for c in citations]

        # Extract judge names (look for "J." or "JSC" after names)
        judge_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:J\.?|JSC)'
        judges = re.findall(judge_pattern, content[:5000])  # Check first 5000 chars
        if judges:
            metadata["judges"] = list(set(judges[:5]))  # First 5 unique judges

        # Extract legal topics/keywords (common legal terms in Ghana)
        legal_keywords = [
            "constitutional", "contract", "criminal", "land", "property",
            "negligence", "damages", "appeal", "jurisdiction", "interpretation"
        ]
        found_keywords = [kw for kw in legal_keywords if kw.lower() in content.lower()[:10000]]
        if found_keywords:
            metadata["legal_topics"] = found_keywords

        return metadata


def load_pdf_documents(data_dir: Path) -> List[Document]:
    """Load all PDF documents from directory with metadata extraction."""
    logger.info(f"Loading PDFs from: {data_dir}")

    if not data_dir.exists():
        logger.error(f"Directory not found: {data_dir}")
        return []

    pdf_files = sorted(data_dir.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files")

    documents = []
    failed_files = []

    for pdf_path in tqdm(pdf_files, desc="Loading PDFs", unit="file"):
        try:
            # Load PDF
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()

            if not pages:
                logger.warning(f"No content extracted from {pdf_path.name}")
                continue

            # Combine pages
            combined_content = "\n\n".join([page.page_content for page in pages])

            # Extract metadata
            file_metadata = CaseMetadataExtractor.extract_from_filename(pdf_path.name)
            content_metadata = CaseMetadataExtractor.extract_from_content(combined_content)

            # Merge metadata
            metadata = {
                **file_metadata,
                **content_metadata,
                "source": str(pdf_path),
                "total_pages": len(pages),
                "ingestion_date": datetime.now().isoformat(),
                "expert_type": "case_law",  # For retrieval filtering
            }

            doc = Document(
                page_content=combined_content,
                metadata=metadata
            )
            documents.append(doc)

            logger.success(f"✓ Loaded: {pdf_path.name} ({len(pages)} pages)")

        except Exception as e:
            logger.error(f"✗ Failed to load {pdf_path.name}: {e}")
            failed_files.append((pdf_path.name, str(e)))

    logger.info(f"\nLoading Summary:")
    logger.info(f"  Success: {len(documents)}/{len(pdf_files)}")
    logger.info(f"  Failed: {len(failed_files)}/{len(pdf_files)}")

    if failed_files:
        logger.warning("\nFailed files:")
        for filename, error in failed_files:
            logger.warning(f"  - {filename}: {error}")

    return documents


def split_documents(documents: List[Document], chunk_size: int = 512, chunk_overlap: int = 100) -> List[Document]:
    """Split documents into optimal chunks for embeddings."""
    logger.info(f"Splitting {len(documents)} documents (chunk_size={chunk_size}, overlap={chunk_overlap})")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunked_docs = []
    for doc in tqdm(documents, desc="Splitting documents", unit="doc"):
        chunks = splitter.split_documents([doc])

        # Add chunk index to metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)

        chunked_docs.extend(chunks)

    logger.info(f"Created {len(chunked_docs)} chunks from {len(documents)} documents")
    logger.info(f"Average chunks per document: {len(chunked_docs) / len(documents):.1f}")

    return chunked_docs


def parse_legal_structure(documents: List[Document]) -> List[Document]:
    """Parse legal structure from documents and enrich metadata."""
    logger.info("Parsing legal structure from chunks...")

    parser = LegalTextParser()

    for doc in tqdm(documents, desc="Parsing legal structure", unit="chunk"):
        try:
            # Parse legal structure
            legal_doc = parser.parse_document(
                doc.page_content,
                source=doc.metadata.get("filename", "unknown")
            )

            # Add legal structure metadata
            doc.metadata.update({
                "legal_title": legal_doc.title,
                "legal_article": legal_doc.article,
                "legal_section": legal_doc.section,
                "legal_subsection": legal_doc.subsection,
                "legal_case_number": legal_doc.case_number,
                "legal_citations": legal_doc.citations,
            })

        except Exception as e:
            logger.debug(f"Could not parse legal structure: {e}")
            continue

    logger.success("Legal structure parsing complete")
    return documents


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata to ensure ChromaDB compatibility.

    ChromaDB only accepts str, int, float, bool, or None values.
    This function converts lists to comma-separated strings.
    """
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = None
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            # Convert list to comma-separated string
            if value:  # Non-empty list
                sanitized[key] = ", ".join(str(v) for v in value)
            else:
                sanitized[key] = None
        elif isinstance(value, dict):
            # Convert dict to JSON string
            import json
            sanitized[key] = json.dumps(value)
        else:
            # Convert other types to string
            sanitized[key] = str(value)
    return sanitized


def ingest_to_chromadb(documents: List[Document]) -> Dict[str, Any]:
    """Ingest documents into ChromaDB with progress tracking."""
    logger.info(f"Starting ChromaDB ingestion for {len(documents)} chunks...")

    # Get retriever (singleton, loads models once)
    retriever = get_chroma_retriever(
        collection_name="legal_docs",
        embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
        k=settings.RAG_TOP_K,
        device=settings.RAG_DEVICE,
        use_reranker=True
    )

    # Batch ingestion for efficiency
    batch_size = 10
    total_batches = (len(documents) + batch_size - 1) // batch_size

    successful = 0
    failed = 0

    logger.info(f"Ingesting in batches of {batch_size} (total: {total_batches} batches)")

    for i in tqdm(range(0, len(documents), batch_size), desc="Ingesting batches", unit="batch"):
        batch = documents[i:i + batch_size]

        try:
            # Prepare texts, metadatas, and IDs
            texts = [doc.page_content for doc in batch]
            # Sanitize metadata to ensure ChromaDB compatibility
            metadatas = [sanitize_metadata(doc.metadata) for doc in batch]
            ids = [
                f"case_{doc.metadata.get('case_number', 'unknown')}_{doc.metadata.get('chunk_index', i)}"
                for doc in batch
            ]

            # Add to ChromaDB
            retriever.add_texts(texts=texts, metadatas=metadatas, ids=ids)

            successful += len(batch)

        except Exception as e:
            logger.error(f"Batch ingestion failed: {e}")
            failed += len(batch)

    stats = {
        "total_chunks": len(documents),
        "successful": successful,
        "failed": failed,
        "success_rate": (successful / len(documents)) * 100 if documents else 0
    }

    logger.info(f"\nIngestion Summary:")
    logger.info(f"  Total chunks: {stats['total_chunks']}")
    logger.info(f"  Successful: {stats['successful']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info(f"  Success rate: {stats['success_rate']:.1f}%")

    return stats


def main():
    """Main ingestion pipeline."""
    logger.info("=" * 80)
    logger.info("Ghana Legal AI - Case Ingestion Pipeline")
    logger.info("=" * 80)

    start_time = datetime.now()

    # Step 1: Load PDFs
    data_dir = Path(__file__).resolve().parents[3] / "data" / "cases"
    documents = load_pdf_documents(data_dir)

    if not documents:
        logger.error("No documents loaded. Exiting.")
        return

    # Step 2: Split into chunks
    chunked_docs = split_documents(
        documents,
        chunk_size=settings.RAG_CHUNK_SIZE * 2,  # 512 tokens for cases
        chunk_overlap=100
    )

    # Step 3: Deduplicate
    logger.info("Deduplicating chunks...")
    unique_docs = deduplicate_documents(chunked_docs, threshold=0.85)
    removed = len(chunked_docs) - len(unique_docs)
    logger.info(f"Removed {removed} duplicate chunks ({removed/len(chunked_docs)*100:.1f}%)")

    # Step 4: Parse legal structure
    enriched_docs = parse_legal_structure(unique_docs)

    # Step 5: Ingest to ChromaDB
    stats = ingest_to_chromadb(enriched_docs)

    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("\n" + "=" * 80)
    logger.info("INGESTION COMPLETE!")
    logger.info("=" * 80)
    logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    logger.info(f"Documents processed: {len(documents)}")
    logger.info(f"Total chunks ingested: {stats['successful']}")
    logger.info(f"Average chunks per document: {stats['successful']/len(documents):.1f}")
    logger.info("=" * 80)

    logger.success("\n✓ Your RAG system is now enhanced with Ghana Supreme Court cases!")
    logger.info("\nNext steps:")
    logger.info("1. Restart your backend: make start-backend")
    logger.info("2. Test with a query: 'Tell me about the Adjei v Mckorley case'")
    logger.info("3. Verify retrieval: python scripts/verify_ingestion.py")


if __name__ == "__main__":
    main()

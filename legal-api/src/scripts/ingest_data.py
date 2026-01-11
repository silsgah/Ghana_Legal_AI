import os
import asyncio
import logging
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from pymongo import MongoClient
from dotenv import load_dotenv

# Load .env explicitly for Pydantic Settings
load_dotenv("legal-api/src/.env")

# Import settings
from ghana_legal.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
# Define all directories to ingest from
DATA_DIRS = [
    os.path.join(PROJECT_ROOT, "data/ghana_legal/constitution"),
    os.path.join(PROJECT_ROOT, "data/ghana_legal/cases")
]

def ingest_legal_docs():
    """Ingest legal PDFs (Constitution & Cases) into MongoDB Atlas Vector Store."""
    
    all_chunks = []
    
    # Iterate over all source directories
    for data_dir in DATA_DIRS:
        if not os.path.exists(data_dir):
            logger.warning(f"Directory not found, skipping: {data_dir}")
            continue
            
        pdf_files = [f for f in os.listdir(data_dir) if f.endswith(".pdf")]
        if not pdf_files:
            logger.info(f"No PDF files in {data_dir}")
            continue
            
        logger.info(f"Found {len(pdf_files)} PDF(s) in {data_dir}")
        
        for pdf in pdf_files:
            file_path = os.path.join(data_dir, pdf)
            logger.info(f"Processing: {pdf}")
            try:
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                
                # Split Text
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    separators=["\n\n", "\n", " ", ""]
                )
                chunks = splitter.split_documents(docs)
                
                # Add metadata to help retrieval/training know source type
                source_type = "constitution" if "constitution" in data_dir else "case_law"
                for chunk in chunks:
                    chunk.metadata["source_type"] = source_type
                    chunk.metadata["file_name"] = pdf
                    
                all_chunks.extend(chunks)
                logger.info(f"  -> Extracted {len(chunks)} chunks")
                
            except Exception as e:
                logger.error(f"Failed to process {pdf}: {e}")

    if not all_chunks:
        logger.warning("No chunks found to ingest across all directories.")
        return

    # 3. Create Embeddings
    logger.info("Initializing Embeddings (may take a moment)...")
    embeddings = HuggingFaceEmbeddings(model_name=settings.RAG_TEXT_EMBEDDING_MODEL_ID)

    # 4. Connect to MongoDB
    logger.info("Connecting to MongoDB Atlas...")
    client = MongoClient(settings.MONGO_URI)
    collection = client[settings.MONGO_DB_NAME][settings.MONGO_LONG_TERM_MEMORY_COLLECTION]
    
    # 5. Ingest
    logger.info(f"Ingesting {len(all_chunks)} vectors into MongoDB...")
    MongoDBAtlasVectorSearch.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        collection=collection,
        index_name="default"
    )
    
    logger.info("✅ Ingestion Complete!")

if __name__ == "__main__":
    # Create dirs if they don't exist
    for d in DATA_DIRS:
        os.makedirs(d, exist_ok=True)
        
    ingest_legal_docs()

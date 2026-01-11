from loguru import logger

from ghana_legal.application.long_term_memory import LongTermMemoryCreator
from ghana_legal.domain.legal_expert_factory import LegalExpertFactory
from ghana_legal.domain.legal_expert import LegalExpertExtract

def ingest_data():
    """Run the ingestion pipeline to populate the vector database."""
    logger.info("Starting ingestion...")
    
    # 1. Get all legal experts using factory static methods
    expert_ids = LegalExpertFactory.get_available_experts()
    # Create extracts for each expert to trigger their specific document loading
    # We don't need external URLs for now since we have the local loader
    expert_extracts = [
        LegalExpertExtract(id=expert_id, urls=[]) 
        for expert_id in expert_ids
    ]
    
    # 2. Build Memory Creator
    creator = LongTermMemoryCreator.build_from_settings()
    
    # 3. Run Ingestion
    creator(expert_extracts)
    
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    ingest_data()

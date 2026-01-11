import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

# Load .env explicitly for Pydantic Settings
load_dotenv("legal-api/src/.env")  # Adjusted path relative to project root

from motor.motor_asyncio import AsyncIOMotorClient
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

# Import settings from project config to ensure consistency
from ghana_legal.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class SyntheticDataGenerator:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.GROQ_LLM_MODEL
        self.llm = ChatGroq(
            model=self.model_name,
            api_key=settings.GROQ_API_KEY,
            temperature=0.7
        )
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.collection = self.db[settings.MONGO_LONG_TERM_MEMORY_COLLECTION]

    async def fetch_random_documents(self, sample_size: int = 50) -> List[str]:
        """Fetch random document chunks from MongoDB."""
        try:
            # Use aggregation for random sampling
            pipeline = [{"$sample": {"size": sample_size}}]
            cursor = self.collection.aggregate(pipeline)
            
            documents = []
            async for doc in cursor:
                # Assuming standard LangChain vector store structure: text is in 'text' or 'page_content' field
                text = doc.get("text") or doc.get("page_content")
                if text and len(text) > 200:  # Filter out tiny chunks
                    documents.append(text)
            
            logger.info(f"Fetched {len(documents)} document chunks from MongoDB.")
            return documents
        except Exception as e:
            logger.error(f"Error fetching documents: {e}")
            return []

    async def generate_qa_pairs(self, context_text: str) -> List[Dict[str, Any]]:
        """Generate Q&A pairs from a single document chunk."""
        
        system_prompt = """
        You are a Senior Judge of the Supreme Court of Ghana. 
        Your task is to generate high-quality training data for a junior legal AI.
        
        Read the provided legal text (Context). 
        Generate 3 distinct question-and-answer pairs based strictly on this text.
        
        The pairs should cover:
        1. Factual Recall (e.g., "What does Article X say?")
        2. Legal Reasoning (e.g., "Does a person have the right to...?")
        3. Exclusionary (e.g., "Is it constitutional to...?")

        Output purely a JSON list of objects with keys: "instruction" and "output".
        
        Example Output Format:
        [
            {{"instruction": "What is the capital?", "output": "Accra."}},
            {{"instruction": "Explain...?", "output": "Because..."}}
        ]
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", f"Context: {context_text}")
        ])
        
        chain = prompt | self.llm
        
        try:
            response = await chain.ainvoke({})
            content = response.content
            
            # Identify JSON block if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
                
            data = json.loads(content)
            
            # Ensure it's a list
            if isinstance(data, dict):
                data = [data]
                
            return data
            
        except Exception as e:
            logger.warning(f"Failed to generate QA pairs: {e}")
            return []

    async def build_dataset(self, num_chunks: int = 20, output_file: str = "ghana_legal_finetune.json"):
        """Main execution flow."""
        logger.info(f"Starting synthetic data generation (Chunks: {num_chunks})...")
        
        chunks = await self.fetch_random_documents(num_chunks)
        full_dataset = []

        total_pairs = 0
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
            pairs = await self.generate_qa_pairs(chunk)
            
            if pairs:
                # Convert to ShareGPT / Unsloth Format
                for pair in pairs:
                    sharegpt_entry = {
                        "conversations": [
                            {
                                "from": "human",
                                "value": pair.get("instruction", "")
                            },
                            {
                                "from": "gpt",
                                "value": pair.get("output", "")
                            }
                        ]
                    }
                    full_dataset.append(sharegpt_entry)
                
                total_pairs += len(pairs)
                # Sleep briefly to respect rate limits
                await asyncio.sleep(1) 

        # Save to file
        with open(output_file, "w") as f:
            json.dump(full_dataset, f, indent=2)
            
        logger.info(f"✅ Success! Saved {total_pairs} pairs to {output_file}")


if __name__ == "__main__":
    # Run the generator
    generator = SyntheticDataGenerator()
    asyncio.run(generator.build_dataset(num_chunks=50))

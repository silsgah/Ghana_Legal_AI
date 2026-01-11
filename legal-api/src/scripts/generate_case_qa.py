#!/usr/bin/env python3
"""
Ghana Legal Case Q&A Generator
Generates Q&A training pairs from Supreme Court case PDFs using Groq.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

# Load .env from the correct location
env_path = Path("/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/legal-api/src/.env")
load_dotenv(env_path)

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# Try pypdf first, fall back to PyPDF2
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
CASES_DIR = Path("/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/data/cases")
OUTPUT_FILE = Path("/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/ghana_legal_finetune_expanded.json")
EXISTING_DATA = Path("/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/ghana_legal_finetune.json")

# Groq settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Best for Q&A generation

class CaseQAGenerator:
    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in environment")
        
        self.llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0.7
        )
    
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from a PDF file."""
        try:
            reader = PdfReader(str(pdf_path))
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            logger.warning(f"Failed to extract text from {pdf_path.name}: {e}")
            return ""
    
    def chunk_text(self, text: str, chunk_size: int = 3000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                if last_period > chunk_size // 2:
                    chunk = chunk[:last_period + 1]
                    end = start + last_period + 1
            
            chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    async def generate_qa_pairs(self, context: str, case_name: str) -> List[Dict[str, Any]]:
        """Generate Q&A pairs from a text chunk."""
        
        system_prompt = """
        You are a Senior Judge of the Supreme Court of Ghana.
        Your task is to generate high-quality training data for a legal AI.
        
        Read the provided legal case text from a Supreme Court judgment.
        Generate 3-5 distinct question-and-answer pairs based strictly on this text.
        
        The pairs should cover:
        1. Factual Recall (e.g., "What was the ruling in this case?")
        2. Legal Reasoning (e.g., "Why did the court hold that...?")
        3. Constitutional Questions (e.g., "Is it constitutional to...?")
        4. Procedural Questions (e.g., "What procedural rule applies to...?")
        
        Make answers comprehensive but concise, citing specific articles/sections when available.
        
        Output ONLY a valid JSON list of objects with keys: "instruction" and "output".
        No markdown, no explanation, just the JSON array.
        
        Example:
        [
            {{"instruction": "What was the main issue?", "output": "The main issue was..."}},
            {{"instruction": "What article did the court apply?", "output": "Article 125..."}}
        ]
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", f"Case: {case_name}\n\nText:\n{context[:4000]}")  # Limit context size
        ])
        
        chain = prompt | self.llm
        
        try:
            response = await chain.ainvoke({})
            content = response.content.strip()
            
            # Clean up markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            if isinstance(data, dict):
                data = [data]
            
            return data
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error for {case_name}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to generate QA for {case_name}: {e}")
            return []
    
    async def process_all_cases(self, max_cases: int = 50) -> List[Dict]:
        """Process all case PDFs and generate Q&A pairs."""
        
        pdf_files = list(CASES_DIR.glob("*.pdf"))[:max_cases]
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        all_pairs = []
        
        for i, pdf_path in enumerate(pdf_files):
            logger.info(f"[{i+1}/{len(pdf_files)}] Processing: {pdf_path.name[:50]}...")
            
            # Extract text
            text = self.extract_text_from_pdf(pdf_path)
            if not text or len(text) < 500:
                logger.warning(f"  Skipping - insufficient text content")
                continue
            
            # Chunk the text
            chunks = self.chunk_text(text)
            logger.info(f"  Split into {len(chunks)} chunks")
            
            # Process first 2 chunks per case (to avoid too many similar questions)
            for chunk_idx, chunk in enumerate(chunks[:2]):
                pairs = await self.generate_qa_pairs(chunk, pdf_path.stem)
                
                # Convert to ShareGPT format
                for pair in pairs:
                    sharegpt_entry = {
                        "conversations": [
                            {"from": "human", "value": pair.get("instruction", "")},
                            {"from": "gpt", "value": pair.get("output", "")}
                        ]
                    }
                    all_pairs.append(sharegpt_entry)
                
                logger.info(f"  Chunk {chunk_idx+1}: Generated {len(pairs)} pairs")
                
                # Rate limiting
                await asyncio.sleep(1)
        
        return all_pairs
    
    def merge_with_existing(self, new_pairs: List[Dict]) -> List[Dict]:
        """Merge new pairs with existing training data."""
        existing = []
        
        if EXISTING_DATA.exists():
            with open(EXISTING_DATA) as f:
                existing = json.load(f)
            logger.info(f"Loaded {len(existing)} existing training pairs")
        
        combined = existing + new_pairs
        logger.info(f"Combined dataset: {len(combined)} total pairs")
        
        return combined


async def main():
    print("🇬🇭 Ghana Legal Case Q&A Generator")
    print("=" * 50)
    
    generator = CaseQAGenerator()
    
    # Generate new pairs from case PDFs
    new_pairs = await generator.process_all_cases(max_cases=50)
    print(f"\n✅ Generated {len(new_pairs)} new Q&A pairs from case PDFs")
    
    # Merge with existing data
    combined = generator.merge_with_existing(new_pairs)
    
    # Save expanded dataset
    with open(OUTPUT_FILE, "w") as f:
        json.dump(combined, f, indent=2)
    
    print(f"\n✅ Saved {len(combined)} total pairs to: {OUTPUT_FILE}")
    print(f"   - Existing pairs: {len(combined) - len(new_pairs)}")
    print(f"   - New from cases: {len(new_pairs)}")


if __name__ == "__main__":
    asyncio.run(main())

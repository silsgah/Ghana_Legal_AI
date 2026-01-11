#!/usr/bin/env python3
"""
Test script to verify LFM2 integration in legal-api
"""
import os
import sys

# Add src to path
sys.path.insert(0, "/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/legal-api/src")

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/legal-api/src/.env"))

# Force local LLM for testing
os.environ["USE_LOCAL_LLM"] = "true"

from ghana_legal.application.conversation_service.workflow.chains import get_chat_model
from ghana_legal.config import settings

def test_local_model():
    print("🇬🇭 Ghana Legal AI - LFM2 Integration Test")
    print("=" * 50)
    
    print(f"\nConfiguration:")
    print(f"  USE_LOCAL_LLM: {settings.USE_LOCAL_LLM}")
    print(f"  OLLAMA_MODEL: {settings.OLLAMA_MODEL}")
    print(f"  OLLAMA_BASE_URL: {settings.OLLAMA_BASE_URL}")
    
    print("\n📝 Getting chat model...")
    model = get_chat_model()
    print(f"  Model type: {type(model).__name__}")
    
    print("\n💬 Testing inference...")
    response = model.invoke("Is it constitutional to remove the President for misconduct?")
    print(f"\n📍 Response:\n{response.content}")
    
    print("\n✅ Integration test passed!")

if __name__ == "__main__":
    test_local_model()

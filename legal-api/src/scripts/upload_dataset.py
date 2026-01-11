#!/usr/bin/env python3
"""
Upload Ghana Legal Training Dataset to HuggingFace Hub
"""

import json
from pathlib import Path
from datasets import Dataset
from huggingface_hub import HfApi, login
import os

# Configuration
DATASET_PATH = Path("/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/ghana_legal_finetune_expanded.json")
REPO_NAME = "gahsilas/ghana-legal-qa"

def main():
    print("📤 Uploading Ghana Legal Dataset to HuggingFace Hub")
    print("=" * 50)
    
    # Load JSON data
    with open(DATASET_PATH) as f:
        data = json.load(f)
    
    print(f"✅ Loaded {len(data)} training examples")
    
    # Convert to flat format for HuggingFace datasets
    flat_data = {
        "instruction": [],
        "output": [],
        "conversations": []
    }
    
    for item in data:
        convos = item["conversations"]
        if len(convos) >= 2:
            flat_data["instruction"].append(convos[0]["value"])
            flat_data["output"].append(convos[1]["value"])
            flat_data["conversations"].append(convos)
    
    # Create HuggingFace Dataset
    dataset = Dataset.from_dict(flat_data)
    print(f"✅ Created dataset with {len(dataset)} rows")
    print(f"   Columns: {dataset.column_names}")
    
    # Push to Hub
    print(f"\n📤 Pushing to HuggingFace Hub: {REPO_NAME}")
    
    # Check for HF token
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if hf_token:
        login(token=hf_token)
    
    dataset.push_to_hub(
        REPO_NAME,
        private=False,
        commit_message="Add Ghana Legal Q&A training dataset (524 examples)"
    )
    
    print(f"\n✅ Dataset uploaded successfully!")
    print(f"   View at: https://huggingface.co/datasets/{REPO_NAME}")


if __name__ == "__main__":
    main()

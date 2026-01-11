# Production Grade Fine-Tuning Plan: Ghana Legal AI 🇬🇭⚖️

*From RAG-only to "Sovereign Legal Expert" using LFM2-2.6B and Synthetic Data Engineering.*

---

## 1. The Core Philosophy: "Distillation" 🧪
We do not need to scrape the entire web. We already possess the "Truth" in our MongoDB Vector Store (The 1992 Constitution).
Our strategy is **Knowledge Distillation**: We will use a smart "Teacher Model" (Llama-3-70B via Groq) to read our legal documents and "teach" the smaller student model (LFM2-2.6B) how to answer questions about them.

## 2. Data Engineering Pipeline (The "Silver Standard")

Creating high-quality training pairs is 80% of the work.

### Phase A: Data Extraction (Source: Internal)
We will leverage the documents you have already ingested into MongoDB.
*   **Source**: `legal_docs` collection (PDF Chunks of Constitution).
*   **Action**: Export unique text chunks.

### Phase B: Synthetic Data Generation (SDG)
We will use an automated pipeline to turn raw text into "Instruction Tuples".

**The "Teacher" Prompt (Groq/70B):**
> "You are a Senior Judge. Read the following text from the 1992 Constitution. Generate 3 complex questions a lawyer might ask about this section, and provide the exact answer based *only* on the text."

**Output Tuple:**
1.  **Simple Inst**: "What says Clause 1?" -> "Clause 1 says..."
2.  **Complex Reasoning**: "Does the President have power to...?" -> "Yes, under Article X, but limited by..."
3.  **Adversarial**: "Is it legal to...?" -> "No, strict liability applies..."

**Tools Needed**:
*   `LangChain`: To iterate over MongoDB documents.
*   `Groq API`: To generate the Q&A pairs rapidly (Teacher).
*   `Argilla / Distilabel`: (Optional) To manually review/clean constraints.

### Phase C: Formatting (ShareGPT)
Unsloth requires the data in a specific JSON format.
```json
[
  {
    "conversations": [
      { "from": "human", "value": "Can the President execute a treaty without Parliament?" },
      { "from": "gpt", "value": "No. According to Article 75, the President may execute a treaty, but it is subject to ratification by Parliament." }
    ]
  }
]
```

---

## 3. Fine-Tuning Execution Plan (Unsloth)

### Step 1: Supervised Fine-Tuning (SFT)
*   **Goal**: Syntax and Style.
*   **Dataset Size**: ~500 - 1,000 high-quality legal pairs.
*   **Compute**: Google Colab T4 (Free).
*   **Time**: ~45 minutes.
*   **Outcome**: The model speaks like a Ghanaian lawyer and stops using Americanisms (e.g., "District Attorney" -> "State Attorney").

### Step 2: Direct Preference Optimization (DPO) (Advanced)
*   **Goal**: Safety & Accuracy.
*   **Dataset**: Triplets (Prompt, Winner, Loser).
    *   *Winner*: "Article 20 requires prompt compensation."
    *   *Loser*: " The government can take land freely." (Hallucination)
*   **Outcome**: A model that refuses to lie.

---

## 4. Implementation Steps for You

1.  **Run the Generator**: I will write a script (`scripts/generate_training_data.py`) that:
    *   Connects to your `Mongo_URI`.
    *   Pulls 100 random document chunks.
    *   Calls Groq to generate 3 Q&A pairs per chunk.
    *   Saves `legal_finetune_data.json`.
2.  **Review**: You open the JSON file and spot-check 5-10 entries to ensure the Teacher didn't hallucinate.
3.  **Upload to Colab**: Drag-and-drop this JSON into the Unsloth notebook.

**Decision**: Do you want me to write the `generate_training_data.py` script now to start Phase B?

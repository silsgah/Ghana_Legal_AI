# Ghana Legal AI 🇬🇭⚖️

An AI-powered legal assistant for Ghana, capable of answering questions about the 1992 Constitution, Case Law, and Legal History. Built with Next.js, FastAPI, LangChain, and MongoDB Atlas Vector Search.

## Features
- **3 Legal Expert Personas**:
  - 📜 **Constitutional Expert**: Formal, precise interpretations of the 1992 Constitution.
  - ⚖️ **Case Law Analyst**: Logical, precedent-based analysis of Supreme Court rulings.
  - 🏛️ **Legal Historian**: Contextual narratives on the evolution of Ghanaian law.
- **RAG Pipeline**: Retrieves accurate legal context from a vector database (MongoDB Atlas).
- **Agentic Workflow**: Uses LangGraph for stateful conversation management.
- **Real-Time Evaluation**: Monitors response quality (Faithfulness, Relevancy) using DeepEval.
- **Observability**: Full tracing of LLM calls via Opik/Comet.

## Architecture
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Backend**: FastAPI, LangChain, LangGraph
- **Database**: MongoDB Atlas (Vector Search)
- **LLM**: Groq (Llama 3 70B) for inference, OpenAI for evaluation
- **Embeddings**: HuggingFace (`all-MiniLM-L6-v2`)

## Prerequisites
- Node.js 18+
- Python 3.10+
- MongoDB Atlas (Cluster with Vector Search enabled)
- API Keys: Groq, OpenAI (optional for eval), Comet/Opik (optional for tracing)

## Getting Started

### 1. Clone & Setup
```bash
git clone <repo-url>
cd ghana-legal-ai
```

### 2. Backend Setup
```bash
cd legal-api
pip install -r requirements.txt

# Create .env file based on .env.example
cp src/.env.example src/.env
# Edit src/.env with your API keys
```

### 3. Frontend Setup
```bash
cd ../legal-web
npm install
```

### 4. Data Ingestion
Populate the knowledge base with legal documents:
```bash
cd ../legal-api/src
# Ensure MONGO_URI is set in your environment or .env
python -m ghana_legal.application.data.ingest
```

### 5. Running Locally
**Backend:**
```bash
# In legal-api/src
python -m ghana_legal.infrastructure.api
# Server runs at http://localhost:8000
```

**Frontend:**
```bash
# In legal-web
npm run dev
# App runs at http://localhost:3000
```

## Testing & Evaluation
Run the DeepEval test suite to verify agent performance:
```bash
cd legal-api
deepeval test run tests/test_legal_ai_eval.py
```

## Deployment
See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

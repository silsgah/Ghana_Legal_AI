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


### Option B: Professional Docker Setup (Recommended)
This method runs the entire stack (Airflow, MongoDB, Postgres) in containers.

```bash
# 1. Create .env file for Docker
echo "AIRFLOW_UID=$(id -u)" > .env

# 2. Build and Start Services
docker-compose up -d --build

# 3. Access Airflow UI
# Open http://localhost:8080 (User: admin, Pass: admin)
# Trigger 'ghana_legal_pipeline' DAG to start ingestion.
```

### Option C: Manual Script Setup (Educational)
This runs the lightweight version on your host machine.


```bash
# 1. Install all dependencies (Backend & Frontend)
make install

# 2. Configure Environment
cp legal-api/src/.env.example legal-api/src/.env
# Edit legal-api/src/.env with your API keys (Groq, MongoDB, etc.)

# 3. Ingest Data (Populate Vector DB)
make ingest
```

### 3. Running Locally

You will need two terminal windows:

**Terminal 1 (Backend):**
```bash
make start-backend
# Runs at http://localhost:8000
```

### 4. Automated Data Factory (Airflow)
To run the automated ingestion pipeline (fetch -> index daily):
```bash
# 1. Initialize Airflow directory
export AIRFLOW_HOME=$(pwd)/airflow
airflow db init

# 2. Start Scheduler & Webserver
airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com
airflow webserver -p 8081 & airflow scheduler
# Access UI at http://localhost:8081
```

**Terminal 2 (Frontend):**
```bash
make start-frontend
# Runs at http://localhost:3000
```



## Testing & Evaluation
Run the DeepEval test suite to verify agent performance:
```bash
cd legal-api
deepeval test run tests/test_legal_ai_eval.py
```

## Deployment
See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

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
# Open http://localhost:8081 (User: admin, Pass: admin)
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



## Operations Guide

### Quick Start Commands

```bash
# Install dependencies
make install

# Ingest Ghana Supreme Court cases (one-time setup)
make ingest-cases

# Start backend (Terminal 1)
make start-backend

# Start frontend (Terminal 2)
make start-frontend
```

### Starting Services

**Backend (FastAPI + ChromaDB + MongoDB):**
```bash
# Start backend server
make start-backend
# Or manually:
cd legal-api/src && python -m ghana_legal.infrastructure.api
```

**Frontend (Next.js):**
```bash
# Start frontend dev server
make start-frontend
# Or manually:
cd legal-web && npm run dev
```

**MongoDB (Local):**
```bash
# Check if MongoDB is running
brew services list | grep mongodb

# Start MongoDB
brew services start mongodb-community

# Stop MongoDB
brew services stop mongodb-community
```

### Stopping Services

**Stop Backend:**
```bash
# Find and kill backend process
lsof -ti:8000 | xargs kill -9

# Or use Ctrl+C in the terminal running the backend
```

**Stop Frontend:**
```bash
# Find and kill frontend process
lsof -ti:3000 | xargs kill -9

# Or use Ctrl+C in the terminal running the frontend
```

**Stop All Services:**
```bash
# Kill all project-related processes
lsof -ti:8000,3000 | xargs kill -9
```

### Viewing Logs

**Real-time Backend Logs:**
```bash
# If running in background, check the task output file
# (Look for the task ID when you start the backend)

# If running in foreground, logs appear in terminal
# To save logs to file:
cd legal-api/src && python -m ghana_legal.infrastructure.api 2>&1 | tee server.log

# View existing backend log
tail -f legal-api/src/server.log

# View with filtering (retrieval, errors, etc.)
tail -f legal-api/src/server.log | grep -E "hybrid|rerank|ERROR|WARNING"
```

**Real-time Frontend Logs:**
```bash
# Frontend logs appear in the terminal or:
tail -f legal-web/.next/dev/logs/next-development.log
```

**MongoDB Logs:**
```bash
# View MongoDB logs (macOS Homebrew)
tail -f /opt/homebrew/var/log/mongodb/mongo.log

# Or check MongoDB status
brew services list | grep mongodb
```

**Application Health Check:**
```bash
# Check backend health
curl http://localhost:8000/docs

# Check frontend
curl http://localhost:3000
```

### Data Management

**Ingest Legal Documents:**
```bash
# Ingest Ghana Supreme Court cases to ChromaDB
make ingest-cases

# Or manually:
cd legal-api/src && python scripts/ingest_cases_to_chroma.py

# Verify ingestion
make verify-ingestion
# Or:
cd legal-api/src && python scripts/verify_ingestion.py
```

**View ChromaDB Stats:**
```bash
# Check ChromaDB collection size
du -sh legal-api/src/data/chroma_db/

# Verify ingested documents
cd legal-api/src && python scripts/verify_ingestion.py
```

**Reset/Clear Data:**
```bash
# Clear ChromaDB (vector database)
rm -rf legal-api/src/data/chroma_db/

# Clear MongoDB conversations (local)
mongosh ghana_legal --eval "db.dropDatabase()"

# Re-ingest after clearing
make ingest-cases
```

### Troubleshooting

**Backend won't start - Port already in use:**
```bash
# Find what's using port 8000
lsof -ti:8000

# Kill the process
lsof -ti:8000 | xargs kill -9

# Restart backend
make start-backend
```

**Frontend won't start - Port already in use:**
```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Frontend will auto-select next available port (3001, etc.)
make start-frontend
```

**MongoDB connection errors:**
```bash
# Switch to local MongoDB in .env
# Change: MONGO_MODE="atlas"
# To:     MONGO_MODE="local"

# Ensure MongoDB is running
brew services start mongodb-community

# Test connection
mongosh mongodb://localhost:27017/ghana_legal
```

**ChromaDB not found:**
```bash
# Reingest documents
make ingest-cases

# Check if ChromaDB directory exists
ls -la legal-api/src/data/chroma_db/
```

**Missing dependencies:**
```bash
# Reinstall backend dependencies
cd legal-api && pip install -r requirements.txt

# Reinstall frontend dependencies
cd legal-web && npm install
```

### Development Workflow

**Full development cycle:**
```bash
# 1. Start MongoDB (if not running)
brew services start mongodb-community

# 2. Start backend in one terminal
make start-backend

# 3. Start frontend in another terminal
make start-frontend

# 4. View logs in third terminal
tail -f legal-api/src/server.log | grep -E "hybrid|rerank|ERROR"

# 5. Make changes and test
# Backend: Auto-reloads on file changes
# Frontend: Hot-reloads automatically

# 6. Stop services when done
# Use Ctrl+C in each terminal or:
lsof -ti:8000,3000 | xargs kill -9
```

**Quick restart:**
```bash
# Stop and restart backend
lsof -ti:8000 | xargs kill -9 && make start-backend

# Stop and restart frontend
lsof -ti:3000 | xargs kill -9 && make start-frontend
```

### Monitoring & Observability

**Check System Status:**
```bash
# View all running services
lsof -i:8000,3000,27017

# Check process memory usage
ps aux | grep -E "python|node|mongod"

# Check disk usage
du -sh legal-api/src/data/chroma_db/
du -sh /opt/homebrew/var/mongodb/
```

**View Traces (Opik):**
- Visit: https://www.comet.com/opik/
- Project: `ghana_legal_course`
- View traces, metrics, and evaluation scores

**Performance Testing:**
```bash
# Test retrieval speed
time curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test query", "expert_id": "constitutional"}'

# Stress test (Apache Bench)
ab -n 100 -c 10 -p test.json -T application/json \
  http://localhost:8000/chat
```

## Testing & Evaluation
Run the DeepEval test suite to verify agent performance:
```bash
cd legal-api
deepeval test run tests/test_legal_ai_eval.py
```

## Deployment
See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

# Ghana Legal AI Makefile

.PHONY: help install start-backend start-frontend ingest test all

help:
	@echo "Ghana Legal AI Commands:"
	@echo "  make install        - Install backend and frontend dependencies"
	@echo "  make start-backend  - Start the FastAPI backend"
	@echo "  make start-frontend - Start the Next.js frontend"
	@echo "  make ingest         - Run the data ingestion script"
	@echo "  make test           - Run the DeepEval test suite"
	@echo "  make all            - Install and start everything (requires separate terminals)"

install:
	@echo "Installing Backend Dependencies..."
	cd legal-api && pip install -r requirements.txt
	@echo "Installing Frontend Dependencies..."
	cd legal-web && npm install

start-backend:
	@echo "Starting Backend..."
	@echo "Ensure you have the .env file in legal-api/src/"
	cd legal-api/src && python -m ghana_legal.infrastructure.api

start-frontend:
	@echo "Starting Frontend..."
	cd legal-web && npm run dev

ingest:
	@echo "Running Data Ingestion..."
	cd legal-api/src && python -m ghana_legal.application.data.ingest

test:
	@echo "Running Tests..."
	cd legal-api && deepeval test run tests/test_legal_ai_eval.py

FROM apache/airflow:2.8.1

USER root
# Install system dependencies if needed (e.g. for building python packages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
USER airflow

# Copy requirements relevant for ingestion
COPY legal-api/requirements.txt /requirements.txt

# Install python dependencies
# We filter out some heavy ML libs if they cause conflict, but broadly we need:
# beautifulsoup4, requests, pymongo, langchain, sentence-transformers
RUN pip install --no-cache-dir \
    beautifulsoup4 \
    requests \
    pymongo \
    langchain \
    langchain-community \
    langchain-openai \
    langchain-groq \
    sentence-transformers \
    loguru \
    python-dotenv \
    python-dotenv \
    pypdf \
    datasketch

# Ensure ghana_legal package is importable via python path in docker-compose

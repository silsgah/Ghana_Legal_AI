FROM apache/airflow:2.8.1-python3.11

USER root
# Install system dependencies for building python packages and lxml
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
USER airflow

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Pin numpy to avoid binary incompatibility with Airflow's bundled providers
RUN pip install --no-cache-dir "numpy<2"

# Install python dependencies for the ingestion pipeline
RUN pip install --no-cache-dir \
    beautifulsoup4 \
    requests \
    lxml \
    pypdf \
    langchain \
    langchain-community \
    langchain-huggingface \
    langchain-text-splitters \
    sentence-transformers \
    qdrant-client \
    loguru \
    python-dotenv \
    tqdm

"""Pytest fixtures and environment setup.

Loads dummy values for the required Settings fields so unit tests that import
modules touching ghana_legal.config can run without a real .env file.

Sets VECTOR_DB_MODE=qdrant + dummy QDRANT_URL so the chroma retriever path
(which eagerly loads a HuggingFace model on import) is bypassed during pure
unit tests that don't actually call retrieval.
"""

import os

# Set BEFORE any ghana_legal import resolves the settings singleton.
os.environ.setdefault("GROQ_API_KEY", "test-dummy")
os.environ.setdefault("OPENAI_API_KEY", "test-dummy")
os.environ.setdefault("VECTOR_DB_MODE", "qdrant")
os.environ.setdefault("QDRANT_URL", "http://test-dummy.invalid")
os.environ.setdefault("QDRANT_API_KEY", "test-dummy")

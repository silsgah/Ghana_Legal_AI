import contextvars
from typing import List

from langchain_core.tools import tool

from ghana_legal.application.rag.retrievers import get_retriever
from ghana_legal.application.conversation_service.workflow.retrieval_context import build_retrieval_context
from ghana_legal.config import settings

retriever = get_retriever(
    embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
    k=settings.RAG_TOP_K,
    device=settings.RAG_DEVICE,
)

# Context-safe storage for sources retrieved during a request
_retrieved_sources: contextvars.ContextVar[list] = contextvars.ContextVar(
    "retrieved_sources", default=[]
)
# Full per-doc payloads (case_id, paragraph_id, page_content, score, …) so the
# answer pass and validator can bind citations against actual retrieved content,
# not just the user-facing source summary.
_retrieved_docs: contextvars.ContextVar[list] = contextvars.ContextVar(
    "retrieved_docs", default=[]
)


def get_retrieved_sources() -> list:
    """Get the sources captured during the last retrieval."""
    return _retrieved_sources.get([])


def get_retrieved_docs() -> list:
    """Get the full retrieved payloads captured during the last retrieval."""
    return _retrieved_docs.get([])


def clear_retrieved_sources():
    """Reset sources for a new request."""
    _retrieved_sources.set([])
    _retrieved_docs.set([])


@tool
def retrieve_legal_context(query: str) -> str:
    """Search Ghana legal documents. Use this tool when the user asks about:
    - Constitutional articles or provisions
    - Court cases and legal precedents
    - Legal rights and procedures in Ghana
    - Historical legal developments"""

    docs = retriever.retrieve(query)

    sources, full_docs, context = build_retrieval_context(docs)

    _retrieved_sources.set(sources)
    _retrieved_docs.set(full_docs)

    return context or "No relevant documents found."


tools = [retrieve_legal_context]

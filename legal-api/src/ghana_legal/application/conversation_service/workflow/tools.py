import contextvars
from typing import List

from langchain_core.tools import tool

from ghana_legal.application.rag.retrievers import get_retriever
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


def get_retrieved_sources() -> list:
    """Get the sources captured during the last retrieval."""
    return _retrieved_sources.get([])


def clear_retrieved_sources():
    """Reset sources for a new request."""
    _retrieved_sources.set([])


@tool
def retrieve_legal_context(query: str) -> str:
    """Search Ghana legal documents. Use this tool when the user asks about:
    - Constitutional articles or provisions
    - Court cases and legal precedents
    - Legal rights and procedures in Ghana
    - Historical legal developments"""

    docs = retriever.retrieve(query)

    sources: List[dict] = []
    formatted_parts: List[str] = []

    for i, doc in enumerate(docs, 1):
        meta = doc.metadata

        # Build structured source info
        title = (
            meta.get("parties")
            or meta.get("filename", "").replace(".pdf", "").replace("_", " ")
        ).strip()
        source_info = {
            "title": title,
            "court": meta.get("court", ""),
            "year": str(meta.get("year", "")),
            "document_type": meta.get("document_type", ""),
            "case_id": meta.get("case_id", ""),
            "paragraph_id": meta.get("paragraph_id", ""),
        }
        sources.append(source_info)

        # Format header for LLM visibility
        header_parts = [p for p in [title, source_info["court"], source_info["year"]] if p]
        header = " | ".join(header_parts) if header_parts else f"Source {i}"

        # Use parent_content (full section) if available, otherwise chunk text
        content = meta.get("parent_content", doc.page_content)

        formatted_parts.append(f"[Source {i}: {header}]\n{content}")

    _retrieved_sources.set(sources)

    return "\n\n---\n\n".join(formatted_parts)


tools = [retrieve_legal_context]

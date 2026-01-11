from langchain_core.tools import create_retriever_tool

from ghana_legal.application.rag.retrievers import get_retriever
from ghana_legal.config import settings

retriever = get_retriever(
    embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
    k=settings.RAG_TOP_K,
    device=settings.RAG_DEVICE)

retriever_tool = create_retriever_tool(
    retriever,
    "retrieve_legal_context",
    "Search Ghana legal documents. Use this tool when the user asks about:\n"
    "    - Constitutional articles or provisions\n"
    "    - Court cases and legal precedents\n"
    "    - Legal rights and procedures in Ghana\n"
    "    - Historical legal developments",
)

tools = [retriever_tool]
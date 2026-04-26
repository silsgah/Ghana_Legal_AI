from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from ghana_legal.application.conversation_service.workflow.tools import tools
from ghana_legal.config import settings
from ghana_legal.domain.legal_answer import LegalAnswer
from ghana_legal.domain.prompts import (
    CONTEXT_SUMMARY_PROMPT,
    EXTEND_SUMMARY_PROMPT,
    LEGAL_EXPERT_CHARACTER_CARD,
    LEGAL_EXPERT_STRUCTURE_PROMPT,
    SUMMARY_PROMPT,
)


# Tags propagate via .with_config() through LangChain → LangGraph callbacks
# into stream_mode="messages" metadata. generate_response.py filters AIMessageChunks
# by these tags so only prose tokens reach the user — JSON tokens from the
# structuring pass and tool-call wrappers from the router pass are dropped.
TAG_TEXT_ANSWER = "legal_expert_text_answer"
TAG_STRUCTURE = "legal_expert_structure"
TAG_ROUTER = "legal_expert_router"


def get_chat_model(temperature: float = 0.7, model_name: str = None):
    """Get the appropriate chat model based on configuration.
    
    If USE_LOCAL_LLM is True, uses local Ollama with fine-tuned LFM2.
    Otherwise, uses Groq cloud API.
    """
    if settings.USE_LOCAL_LLM:
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            temperature=temperature,
        )
    else:
        return ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=model_name or settings.GROQ_LLM_MODEL,
            temperature=temperature,
        )


def get_groq_model(temperature: float = 0.7, model_name: str = None) -> ChatGroq:
    """Always get Groq model (for summarization tasks)."""
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=model_name or settings.GROQ_LLM_MODEL_CONTEXT_SUMMARY,
        temperature=temperature,
    )


def get_legal_expert_response_chain():
    """Router-pass chain: free-text reply with retrieval tool bound.

    Used on the first turn (no ToolMessage yet) so the model can decide whether
    to call the retrieval tool. Output is free-text — answer extraction happens
    downstream via the text + structure chains below.
    """
    model = get_chat_model()
    # Only bind tools if using Groq (Ollama may not support all tools)
    if not settings.USE_LOCAL_LLM:
        model = model.bind_tools(tools)
    system_message = LEGAL_EXPERT_CHARACTER_CARD

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message.prompt),
            MessagesPlaceholder(variable_name="messages"),
        ],
        template_format="jinja2",
    )

    return (prompt | model).with_config(tags=[TAG_ROUTER])


def get_legal_expert_text_answer_chain():
    """Free-text answer-pass chain — streams prose tokens natively (PR 6).

    Replaces the previous get_legal_expert_answer_chain's structured-output
    path. Used after retrieval. Token streaming works because the model is
    not wrapped in with_structured_output; the structuring happens in a
    separate downstream chain that runs on the produced text.

    Tagged so generate_response.py can selectively forward only these chunks
    to the SSE stream — chunks from the router and structure chains are
    dropped server-side.
    """
    model = get_chat_model()
    # NOT bind_tools — retrieval already happened, the model just answers.
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", LEGAL_EXPERT_CHARACTER_CARD.prompt),
            MessagesPlaceholder(variable_name="messages"),
        ],
        template_format="jinja2",
    )
    return (prompt | model).with_config(tags=[TAG_TEXT_ANSWER])


def get_legal_expert_structure_chain():
    """Extract structured LegalAnswer envelope from a streamed prose answer (PR 6).

    Runs after the text chain produces the user-visible answer. Receives the
    full prose plus the retrieved sources and emits a LegalAnswer envelope for
    the validator. Uses the smaller llama-3.1-8b model so the post-stream wait
    stays under ~1 second.

    Returns None on the local Ollama path so the caller can fall through to a
    minimal synthetic envelope; production always runs Groq.
    """
    if settings.USE_LOCAL_LLM:
        return None

    model = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.GROQ_LLM_MODEL_CONTEXT_SUMMARY,  # llama-3.1-8b-instant
        temperature=0,
    )
    structured = model.with_structured_output(LegalAnswer, method="json_schema")

    prompt = ChatPromptTemplate.from_messages(
        [("system", LEGAL_EXPERT_STRUCTURE_PROMPT.prompt)],
        template_format="jinja2",
    )

    return (prompt | structured).with_config(tags=[TAG_STRUCTURE])


def get_conversation_summary_chain(summary: str = ""):
    # Always use Groq for summarization (better quality)
    model = get_groq_model(model_name=settings.GROQ_LLM_MODEL_CONTEXT_SUMMARY)

    summary_message = EXTEND_SUMMARY_PROMPT if summary else SUMMARY_PROMPT

    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="messages"),
            ("human", summary_message.prompt),
        ],
        template_format="jinja2",
    )

    return prompt | model


def get_context_summary_chain():
    # Always use Groq for context summarization
    model = get_groq_model(model_name=settings.GROQ_LLM_MODEL_CONTEXT_SUMMARY)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("human", CONTEXT_SUMMARY_PROMPT.prompt),
        ],
        template_format="jinja2",
    )

    return prompt | model
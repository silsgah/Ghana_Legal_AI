from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from ghana_legal.application.conversation_service.workflow.tools import tools
from ghana_legal.config import settings
from ghana_legal.domain.legal_answer import LegalAnswer
from ghana_legal.domain.prompts import (
    CONTEXT_SUMMARY_PROMPT,
    EXTEND_SUMMARY_PROMPT,
    LEGAL_EXPERT_ANSWER_PROMPT,
    LEGAL_EXPERT_CHARACTER_CARD,
    SUMMARY_PROMPT,
)


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
    to call the retrieval tool. Output is free-text — the answer-pass chain
    below converts the post-retrieval response into a structured LegalAnswer
    envelope.
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

    return prompt | model


def get_legal_expert_answer_chain():
    """Answer-pass chain: emits a typed LegalAnswer envelope.

    Invoked after retrieval has populated state["retrieved"]. Uses Groq's
    json_schema response_format via LangChain's with_structured_output so the
    model is forced to produce a parseable LegalAnswer (no free-text drift).
    Tool-binding is intentionally NOT applied here — the LLM has already
    decided to retrieve, and structured-output mode is incompatible with
    parallel tool calls on Groq.

    On the local Ollama dev path, structured-output isn't reliably supported,
    so we fall back to the free-text router chain. Production runs Groq
    (USE_LOCAL_LLM=False), where the structured path is the canonical one.
    """
    if settings.USE_LOCAL_LLM:
        return get_legal_expert_response_chain()

    model = get_chat_model()
    structured = model.with_structured_output(LegalAnswer, method="json_schema")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", LEGAL_EXPERT_CHARACTER_CARD.prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("system", LEGAL_EXPERT_ANSWER_PROMPT.prompt),
        ],
        template_format="jinja2",
    )

    return prompt | structured


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
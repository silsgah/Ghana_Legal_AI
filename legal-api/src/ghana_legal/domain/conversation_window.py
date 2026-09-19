"""Bound persisted conversations before sending them to an LLM provider."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_CHARS_PER_MESSAGE = 1_500
MAX_HISTORY_TOTAL_CHARS = 8_000


def messages_for_model(messages: list[BaseMessage], is_post_retrieval: bool) -> list[BaseMessage]:
    """Drop stale retrieval payloads while preserving the current tool pair."""
    protected_start = len(messages)
    if is_post_retrieval and messages and isinstance(messages[-1], ToolMessage):
        protected_start = max(0, len(messages) - 2)

    history: list[BaseMessage] = []
    for message in messages[:protected_start]:
        if isinstance(message, ToolMessage):
            continue
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str) and len(content) > MAX_HISTORY_CHARS_PER_MESSAGE:
            message = message.model_copy(
                update={
                    "content": (
                        f"{content[:MAX_HISTORY_CHARS_PER_MESSAGE].rstrip()}\n"
                        "[Earlier message truncated for conversation context]"
                    )
                }
            )
        history.append(message)

    window = history[-MAX_HISTORY_MESSAGES:]
    while sum(
        len(message.content) for message in window if isinstance(message.content, str)
    ) > MAX_HISTORY_TOTAL_CHARS and len(window) > 1:
        window.pop(0)
    if protected_start < len(messages):
        window.extend(messages[protected_start:])
    return window


def is_context_length_error(error: Exception) -> bool:
    """Return whether a provider rejected a request for its message size."""
    message = str(error).lower()
    return (
        "reduce the length of the messages" in message
        or "context length" in message
        or ("messages" in message and "completion" in message and "400" in message)
    )


def minimal_retry_messages(messages: list[BaseMessage], is_post_retrieval: bool) -> list[BaseMessage]:
    """Keep only the current exchange for a context-length retry."""
    if is_post_retrieval:
        # Current sequence is HumanMessage → AI tool call → ToolMessage. The
        # provider requires the tool-call/result pair to stay together.
        return messages[-3:]

    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return [message]
    return messages[-1:]

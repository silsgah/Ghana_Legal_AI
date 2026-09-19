"""Bound persisted conversations before sending them to an LLM provider."""

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_CHARS_PER_MESSAGE = 4_000


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
    if protected_start < len(messages):
        window.extend(messages[protected_start:])
    return window

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ghana_legal.domain.conversation_window import (
    is_context_length_error,
    messages_for_answer_after_retrieval,
    messages_for_model,
    minimal_retry_messages,
)


def test_conversation_window_drops_historical_retrieval_payloads():
    old_tool_call = AIMessage(
        content="",
        tool_calls=[{"name": "retrieve_legal_context", "args": {"query": "old"}, "id": "old-call"}],
    )
    old_tool_result = ToolMessage(content="x" * 100_000, tool_call_id="old-call")
    messages = [HumanMessage(content="Old question"), old_tool_call, old_tool_result, AIMessage(content="Old answer"), HumanMessage(content="New question")]

    result = messages_for_model(messages, is_post_retrieval=False)

    assert [message.content for message in result] == ["Old question", "Old answer", "New question"]


def test_conversation_window_keeps_current_tool_pair():
    call = AIMessage(
        content="",
        tool_calls=[{"name": "retrieve_legal_context", "args": {"query": "current"}, "id": "new-call"}],
    )
    result = messages_for_model(
        [HumanMessage(content="Question"), call, ToolMessage(content="current sources", tool_call_id="new-call")],
        is_post_retrieval=True,
    )

    assert result[-2] is call
    assert isinstance(result[-1], ToolMessage)


def test_conversation_window_has_a_total_history_budget():
    messages = [HumanMessage(content=str(index) * 1_500) for index in range(8)]

    result = messages_for_model(messages, is_post_retrieval=False)

    assert sum(len(message.content) for message in result) <= 8_000


def test_context_length_retry_retains_only_current_tool_exchange():
    current_call = AIMessage(
        content="",
        tool_calls=[{"name": "retrieve_legal_context", "args": {}, "id": "current"}],
    )
    messages = [
        HumanMessage(content="Old question"),
        AIMessage(content="Old answer"),
        HumanMessage(content="Current question"),
        current_call,
        ToolMessage(content="Current sources", tool_call_id="current"),
    ]

    result = minimal_retry_messages(messages, is_post_retrieval=True)

    assert result == messages[-3:]
    assert is_context_length_error(Exception("400: Please reduce the length of the messages or completion."))


def test_answer_history_replaces_tool_pair_with_plain_retrieved_context():
    call = AIMessage(
        content="",
        tool_calls=[{"name": "retrieve_legal_context", "args": {}, "id": "current"}],
    )
    result = messages_for_answer_after_retrieval([
        HumanMessage(content="What was decided?"),
        call,
        ToolMessage(content="[Source 1]\nThe holding", tool_call_id="current"),
    ])

    assert len(result) == 2
    assert result[0].content == "What was decided?"
    assert "do not call any tool" in result[-1].content
    assert "The holding" in result[-1].content

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ghana_legal.domain.conversation_window import messages_for_model


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

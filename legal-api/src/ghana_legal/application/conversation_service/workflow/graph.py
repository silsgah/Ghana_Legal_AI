from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition

from ghana_legal.application.conversation_service.workflow.edges import (
    should_summarize_conversation,
)
from ghana_legal.application.conversation_service.workflow.nodes import (
    conversation_node,
    summarize_conversation_node,
    retriever_node,
    connector_node,
    validate_answer_node,
)
from ghana_legal.application.conversation_service.workflow.state import LegalExpertState


@lru_cache(maxsize=1)
def create_workflow_graph():
    graph_builder = StateGraph(LegalExpertState)

    # Add all nodes
    graph_builder.add_node("conversation_node", conversation_node)
    graph_builder.add_node("retrieve_legal_context", retriever_node)
    graph_builder.add_node("validate_answer_node", validate_answer_node)
    graph_builder.add_node("summarize_conversation_node", summarize_conversation_node)
    graph_builder.add_node("connector_node", connector_node)

    # Define the flow
    graph_builder.add_edge(START, "conversation_node")
    graph_builder.add_conditional_edges(
        "conversation_node",
        tools_condition,
        {
            "tools": "retrieve_legal_context",
            # PR 3: route through the citation validator before the connector.
            # The validator is a no-op when no envelope is present (no-retrieval
            # branch), so the topology stays unconditional.
            END: "validate_answer_node",
        }
    )
    # Retrieved context goes directly to conversation_node (no summarization)
    # so the LLM sees full source metadata for proper citations
    graph_builder.add_edge("retrieve_legal_context", "conversation_node")
    graph_builder.add_edge("validate_answer_node", "connector_node")
    graph_builder.add_conditional_edges("connector_node", should_summarize_conversation)
    graph_builder.add_edge("summarize_conversation_node", END)

    return graph_builder

# Compiled without a checkpointer. Used for LangGraph Studio
graph = create_workflow_graph().compile()

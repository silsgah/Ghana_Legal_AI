from langchain_core.messages import RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from ghana_legal.application.conversation_service.workflow.chains import (
    get_context_summary_chain,
    get_conversation_summary_chain,
    get_legal_expert_response_chain,
)
from ghana_legal.application.conversation_service.workflow.state import LegalExpertState
from ghana_legal.application.conversation_service.workflow.tools import tools
from ghana_legal.config import settings

retriever_node = ToolNode(tools)


async def conversation_node(state: LegalExpertState, config: RunnableConfig):
    summary = state.get("summary", "")
    conversation_chain = get_legal_expert_response_chain()

    response = await conversation_chain.ainvoke(
        {
            "messages": state["messages"],
            "legal_context": state.get("legal_context", ""),
            "expert_name": state["expert_name"],
            "expertise": state["expertise"],
            "style": state["style"],
            "summary": summary,
        },
        config,
    )
    
    return {"messages": response}


async def summarize_conversation_node(state: LegalExpertState):
    summary = state.get("summary", "")
    summary_chain = get_conversation_summary_chain(summary)

    response = await summary_chain.ainvoke(
        {
            "messages": state["messages"],
            "expert_name": state["expert_name"],
            "summary": summary,
        }
    )

    delete_messages = [
        RemoveMessage(id=m.id)
        for m in state["messages"][: -settings.TOTAL_MESSAGES_AFTER_SUMMARY]
    ]
    return {"summary": response.content, "messages": delete_messages}


async def summarize_context_node(state: LegalExpertState):
    context_summary_chain = get_context_summary_chain()

    response = await context_summary_chain.ainvoke(
        {
            "context": state["messages"][-1].content,
        }
    )
    state["messages"][-1].content = response.content

    return {}


async def connector_node(state: LegalExpertState):
    return {}
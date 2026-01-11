import asyncio
import uuid
from typing import Any, AsyncGenerator, Union

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.mongodb import MongoDBSaver
from loguru import logger
from opik.integrations.langchain import OpikTracer

from ghana_legal.application.conversation_service.workflow.graph import (
    create_workflow_graph,
)
from ghana_legal.application.conversation_service.workflow.state import LegalExpertState
from ghana_legal.config import settings


async def get_response(
    messages: str | list[str] | list[dict[str, Any]],
    expert_id: str,
    expert_name: str,
    expertise: str,
    style: str,
    legal_context: str,
    new_thread: bool = False,
) -> tuple[str, LegalExpertState]:
    """Run a conversation through the workflow graph.

    Args:
        message: Initial message to start the conversation.
        expert_id: Unique identifier for the legal expert.
        expert_name: Name of the legal expert.
        expertise: Expert's area of legal focus.
        style: Style of conversation.
        legal_context: Additional context about the legal topic.

    Returns:
        tuple[str, LegalExpertState]: A tuple containing:
            - The content of the last message in the conversation.
            - The final state after running the workflow.

    Raises:
        RuntimeError: If there's an error running the conversation workflow.
    """

    graph_builder = create_workflow_graph()

    try:
        with MongoDBSaver.from_conn_string(
            conn_string=settings.MONGO_URI,
            db_name=settings.MONGO_DB_NAME,
            checkpoint_collection_name=settings.MONGO_STATE_CHECKPOINT_COLLECTION,
            writes_collection_name=settings.MONGO_STATE_WRITES_COLLECTION,
        ) as checkpointer:
            graph = graph_builder.compile(checkpointer=checkpointer)
            opik_tracer = OpikTracer(graph=graph.get_graph(xray=True))

            thread_id = (
                expert_id if not new_thread else f"{expert_id}-{uuid.uuid4()}"
            )
            config = {
                "configurable": {"thread_id": thread_id},
                "callbacks": [opik_tracer],
            }
            output_state = await graph.ainvoke(
                input={
                    "messages": __format_messages(messages=messages),
                    "expert_name": expert_name,
                    "expertise": expertise,
                    "style": style,
                    "legal_context": legal_context,
                },
                config=config,
            )
        last_message = output_state["messages"][-1]
        response_text = last_message.content
        
        # Trigger async evaluation (non-blocking)
        try:
            from ghana_legal.application.evaluation.evaluation_service import get_evaluator
            evaluator = get_evaluator()
            asyncio.create_task(
                evaluator.evaluate_and_log(
                    query=messages if isinstance(messages, str) else str(messages),
                    response=response_text,
                    context=[legal_context] if legal_context else [],
                    expert_id=expert_id,
                )
            )
        except Exception as eval_error:
            logger.warning(f"Failed to start evaluation: {eval_error}")
        
        return response_text, LegalExpertState(**output_state)
    except Exception as e:
        raise RuntimeError(f"Error running conversation workflow: {str(e)}") from e


async def get_streaming_response(
    messages: str | list[str] | list[dict[str, Any]],
    expert_id: str,
    expert_name: str,
    expertise: str,
    style: str,
    legal_context: str,
    new_thread: bool = False,
) -> AsyncGenerator[str, None]:
    """Run a conversation through the workflow graph with streaming response.

    Args:
        messages: Initial message to start the conversation.
        expert_id: Unique identifier for the legal expert.
        expert_name: Name of the legal expert.
        expertise: Expert's area of legal focus.
        style: Style of conversation.
        legal_context: Additional context about the legal topic.
        new_thread: Whether to create a new conversation thread.

    Yields:
        Chunks of the response as they become available.

    Raises:
        RuntimeError: If there's an error running the conversation workflow.
    """
    graph_builder = create_workflow_graph()

    try:
        with MongoDBSaver.from_conn_string(
            conn_string=settings.MONGO_URI,
            db_name=settings.MONGO_DB_NAME,
            checkpoint_collection_name=settings.MONGO_STATE_CHECKPOINT_COLLECTION,
            writes_collection_name=settings.MONGO_STATE_WRITES_COLLECTION,
        ) as checkpointer:
            graph = graph_builder.compile(checkpointer=checkpointer)
            opik_tracer = OpikTracer(graph=graph.get_graph(xray=True))

            thread_id = (
                expert_id if not new_thread else f"{expert_id}-{uuid.uuid4()}"
            )
            config = {
                "configurable": {"thread_id": thread_id},
                "callbacks": [opik_tracer],
            }

            full_response = ""
            async for chunk in graph.astream(
                input={
                    "messages": __format_messages(messages=messages),
                    "expert_name": expert_name,
                    "expertise": expertise,
                    "style": style,
                    "legal_context": legal_context,
                },
                config=config,
                stream_mode="messages",
            ):
                if chunk[1]["langgraph_node"] == "conversation_node" and isinstance(
                    chunk[0], AIMessageChunk
                ):
                    content = chunk[0].content
                    full_response += content
                    yield content

            # Trigger async evaluation
            try:
                from ghana_legal.application.evaluation.evaluation_service import get_evaluator
                evaluator = get_evaluator()
                asyncio.create_task(
                    evaluator.evaluate_and_log(
                        query=messages if isinstance(messages, str) else str(messages),
                        response=full_response,
                        context=[legal_context] if legal_context else [],
                        expert_id=expert_id,
                    )
                )
            except Exception as eval_error:
                logger.warning(f"Failed to start streaming evaluation: {eval_error}")
    
    except Exception as e:
        raise RuntimeError(
            f"Error running streaming conversation workflow: {str(e)}"
        ) from e


def __format_messages(
    messages: Union[str, list[dict[str, Any]]],
) -> list[Union[HumanMessage, AIMessage]]:
    """Convert various message formats to a list of LangChain message objects.

    Args:
        messages: Can be one of:
            - A single string message
            - A list of string messages
            - A list of dictionaries with 'role' and 'content' keys

    Returns:
        List[Union[HumanMessage, AIMessage]]: A list of LangChain message objects
    """

    if isinstance(messages, str):
        return [HumanMessage(content=messages)]

    if isinstance(messages, list):
        if not messages:
            return []

        if (
            isinstance(messages[0], dict)
            and "role" in messages[0]
            and "content" in messages[0]
        ):
            result = []
            for msg in messages:
                if msg["role"] == "user":
                    result.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    result.append(AIMessage(content=msg["content"]))
            return result

        return [HumanMessage(content=message) for message in messages]

    return []

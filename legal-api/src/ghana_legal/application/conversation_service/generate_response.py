import asyncio
import json
import uuid
import certifi
from typing import Any, AsyncGenerator, Union

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from loguru import logger
from opik.integrations.langchain import OpikTracer

from ghana_legal.application.conversation_service.workflow.graph import (
    create_workflow_graph,
)
from ghana_legal.application.conversation_service.workflow.state import LegalExpertState
from ghana_legal.application.conversation_service.workflow.tools import (
    clear_retrieved_sources,
    get_retrieved_sources,
)
from ghana_legal.config import settings


async def get_response(
    messages: str | list[str] | list[dict[str, Any]],
    expert_id: str,
    expert_name: str,
    expertise: str,
    style: str,
    legal_context: str,
    new_thread: bool = False,
    clerk_id: str = "",
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
        db_uri = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
        if "pooler.supabase.com" in db_uri and ":5432" in db_uri:
            db_uri = db_uri.replace(":5432", ":6543")
        
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        
        async with AsyncConnectionPool(conninfo=db_uri, kwargs={"prepare_threshold": None}) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            graph = graph_builder.compile(checkpointer=checkpointer)
            opik_tracer = OpikTracer(graph=graph.get_graph(xray=True))

            base_thread = f"{clerk_id}_{expert_id}" if clerk_id else expert_id
            thread_id = (
                base_thread if not new_thread else f"{base_thread}-{uuid.uuid4()}"
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
                    # Reset turn-scoped state so a prior turn's envelope or
                    # retrieved docs cannot leak into this turn's validator
                    # via the PostgresSaver checkpoint.
                    "legal_answer": None,
                    "retrieved": [],
                    "repair_attempts": 0,
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
    clerk_id: str = "",
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
    clear_retrieved_sources()
    graph_builder = create_workflow_graph()

    try:
        db_uri = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
        if "pooler.supabase.com" in db_uri and ":5432" in db_uri:
            db_uri = db_uri.replace(":5432", ":6543")

        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        
        async with AsyncConnectionPool(conninfo=db_uri, kwargs={"prepare_threshold": None}) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            graph = graph_builder.compile(checkpointer=checkpointer)
            opik_tracer = OpikTracer(graph=graph.get_graph(xray=True))

            base_thread = f"{clerk_id}_{expert_id}" if clerk_id else expert_id
            thread_id = (
                base_thread if not new_thread else f"{base_thread}-{uuid.uuid4()}"
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
                    # Reset turn-scoped state — see get_response above.
                    "legal_answer": None,
                    "retrieved": [],
                    "repair_attempts": 0,
                },
                config=config,
                stream_mode="messages",
            ):
                msg, meta = chunk
                if not isinstance(msg, AIMessageChunk):
                    continue
                # PR 6: only forward AIMessageChunks tagged as the text-answer
                # pass. The router pass usually emits empty/tool-call chunks,
                # and the structuring pass emits raw JSON tokens that should
                # never reach the client. Tags are propagated through
                # .with_config(tags=[...]) on the chains.
                tags = meta.get("tags") or []
                if "legal_expert_text_answer" not in tags:
                    continue
                content = msg.content or ""
                if not content:
                    continue
                full_response += content
                yield content

            # Pull final state to recover the structured LegalAnswer envelope.
            # The structured-output answer pass does not yield AIMessageChunks,
            # so full_response will be empty when retrieval ran successfully —
            # we synthesize visible text from envelope.human_text below.
            envelope = None
            try:
                snapshot = await graph.aget_state(config)
                envelope = (snapshot.values or {}).get("legal_answer") if snapshot else None
            except Exception as state_error:
                logger.warning(f"Could not fetch final state for envelope: {state_error}")

            # PR 4: refusal decision lives here (NOT in api.py) so streaming
            # can flush chunks live instead of buffering an entire turn server-side
            # to retroactively swap in a refusal — the buffering broke the SSE
            # streaming experience entirely.
            confidence = (envelope or {}).get("confidence")
            refuse = confidence == "insufficient" or (
                settings.REFUSE_BELOW == "low" and confidence == "low"
            )

            if refuse:
                refusal_text = (
                    "I don't have enough grounded retrieved material to answer "
                    "this confidently. Please rephrase or ask about a different "
                    "Ghana legal topic."
                )
                envelope = {
                    "claims": [],
                    "holding": None,
                    "principle": None,
                    "human_text": refusal_text,
                    "retrieval_used": bool(get_retrieved_sources()),
                    "confidence": "insufficient",
                }
                if not full_response:
                    full_response = refusal_text
                    yield refusal_text
            elif envelope and not full_response:
                human_text = envelope.get("human_text", "") or ""
                if human_text:
                    full_response = human_text
                    yield human_text

            # Yield sources captured during retrieval
            sources = get_retrieved_sources()
            if sources:
                yield json.dumps({"__sources__": sources})

            # Yield the structured envelope marker (PR 2 dual-write).
            if envelope:
                yield json.dumps({"__envelope__": envelope})

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

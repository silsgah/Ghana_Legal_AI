import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from opik.integrations.langchain import OpikTracer
from pydantic import BaseModel

from ghana_legal.application.conversation_service.generate_response import (
    get_response,
    get_streaming_response,
)
from ghana_legal.application.conversation_service.reset_conversation import (
    reset_conversation_state,
)
from ghana_legal.infrastructure.auth import get_optional_user, get_current_user
from ghana_legal.infrastructure.database import init_db, close_db, seed_pipeline_cases
from ghana_legal.infrastructure.usage import check_quota
from ghana_legal.domain.legal_expert_factory import LegalExpertFactory
from ghana_legal.infrastructure.cache import get_cache
from ghana_legal.config import settings
from ghana_legal.infrastructure.webhooks import router as webhooks_router
from ghana_legal.infrastructure.admin import router as admin_router

from .opik_utils import configure

configure()

# Initialize Sentry for error tracking & performance monitoring
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=0.3,  # 30% of requests get performance tracing
        profiles_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "development"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for the API."""
    # Startup: Initialize retriever and load models
    try:
        from ghana_legal.application.rag.retrievers import get_retriever
        from ghana_legal.config import settings
        from loguru import logger

        logger.info("Initializing retriever during startup...")
        # Pre-load the retriever and its models during startup
        get_retriever(
            embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
            k=settings.RAG_TOP_K,
            device=settings.RAG_DEVICE,
        )
        logger.info("Retriever initialized successfully at startup")
    except Exception as e:
        from loguru import logger
        logger.error(f"Failed to initialize retriever at startup: {e}")
        logger.warning("API will start but retrieval may fail on first request")

    # Initialize PostgreSQL models
    try:
        await init_db()
        await seed_pipeline_cases()
    except Exception as e:
        from loguru import logger
        logger.error(f"Failed to initialize PostgreSQL: {e}")

    yield

    # Shutdown code
    opik_tracer = OpikTracer()
    opik_tracer.flush()
    await close_db()


app = FastAPI(lifespan=lifespan)

# Register routes
app.include_router(webhooks_router)
app.include_router(admin_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://ghana-legal-ai.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/usage", tags=["billing"])
async def get_usage_quota(user: dict = Depends(get_current_user)):
    """Get the current user's usage quota and plan tier."""
    clerk_id = user["sub"]
    quota = await check_quota(clerk_id)
    return quota


@app.get("/api/pricing", tags=["billing"])
async def get_pricing():
    """Public endpoint: returns live plan pricing and free-tier quota.

    No auth required — used by the landing page and upgrade modal.
    """
    from ghana_legal.infrastructure.usage import get_platform_config
    cfg = await get_platform_config()
    return {
        "free_tier_daily_limit": cfg["free_tier_daily_limit"],
        "pro_monthly_price_ghs": cfg["pro_monthly_price_ghs"],
        "enterprise_monthly_price_ghs": cfg["enterprise_monthly_price_ghs"],
    }


@app.get("/api/public/stats", tags=["public"])
async def get_public_stats():
    """Public endpoint: returns aggregated pipeline statistics for the landing page."""
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import PipelineCase
    from sqlalchemy import select, func

    try:
        async with get_session() as session:
            # Total cases
            total_result = await session.execute(
                select(func.count(PipelineCase.case_id))
            )
            total = total_result.scalar() or 0

            # By court
            court_result = await session.execute(
                select(PipelineCase.court_id, func.count(PipelineCase.case_id))
                .group_by(PipelineCase.court_id)
            )
            by_court = {row[0]: row[1] for row in court_result.all()}

        return {
            "total_cases": total,
            "by_court": by_court
        }
    except Exception as e:
        from loguru import logger
        logger.error(f"Failed to load public stats: {e}")
        return {"total_cases": 0, "by_court": {}}


class ChatMessage(BaseModel):
    message: str
    expert_id: str


@app.post("/chat")
async def chat(chat_message: ChatMessage):
    try:
        # Check cache first
        cache = get_cache()
        cached_response = cache.get(chat_message.message, chat_message.expert_id)
        if cached_response:
            return {"response": cached_response}

        expert_factory = LegalExpertFactory()
        expert = expert_factory.get_legal_expert(chat_message.expert_id)

        response, _ = await get_response(
            messages=chat_message.message,
            expert_id=chat_message.expert_id,
            expert_name=expert.name,
            expertise=expert.expertise,
            style=expert.style,
            legal_context="",
        )

        # Cache the response (only cache responses longer than 50 chars to avoid caching errors)
        if len(response) > 50:
            cache.set(chat_message.message, chat_message.expert_id, response, ttl=7200)  # 2 hours for legal responses

        return {"response": response}
    except Exception as e:
        opik_tracer = OpikTracer()
        opik_tracer.flush()

        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: str = None):
    await websocket.accept()

    # Verify Clerk token manually for WebSocket
    if not token:
        await websocket.send_json({"error": "Missing authentication token"})
        await websocket.close()
        return
        
    try:
        import jwt
        import os
        from ghana_legal.infrastructure.auth import get_jwks_client
        
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        clerk_issuer = os.getenv("CLERK_ISSUER_URL", "")
        
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=clerk_issuer,
            options={"verify_aud": False},
        )
        clerk_id = payload.get("sub")
    except Exception as e:
        await websocket.send_json({"error": f"Authentication failed: {str(e)}"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()

            if "message" not in data or "expert_id" not in data:
                await websocket.send_json(
                    {
                        "error": "Invalid message format. Required fields: 'message' and 'expert_id'"
                    }
                )
                continue

            try:
                # Signal immediately so frontend shows typing indicator
                await websocket.send_json({"streaming": True})

                # 1. Quota Check
                from ghana_legal.infrastructure.usage import check_quota, log_usage
                quota = await check_quota(clerk_id)

                if not quota["allowed"]:
                    await websocket.send_json({
                        "error": f"Daily limit reached. You have used {quota['used_today']}/{quota['daily_limit']} free queries today. Please upgrade to Pro for unlimited access.",
                        "quota_exceeded": True
                    })
                    continue

                # 2. Check cache for non-streaming response first
                cache = get_cache()
                cached_response = cache.get(data["message"], data["expert_id"])
                if cached_response:
                    await websocket.send_json({"response": cached_response, "streaming": False})
                    continue

                expert_factory = LegalExpertFactory()
                expert = expert_factory.get_legal_expert(
                    data["expert_id"]
                )

                # Use streaming response
                response_stream = get_streaming_response(
                    messages=data["message"],
                    expert_id=data["expert_id"],
                    expert_name=expert.name,
                    expertise=expert.expertise,
                    style=expert.style,
                    legal_context="",
                    clerk_id=clerk_id,
                )

                # Stream each chunk of the response
                full_response = ""
                sources = []
                async for chunk in response_stream:
                    # Check for sources marker (yielded after streaming ends)
                    if chunk.startswith('{"__sources__"'):
                        try:
                            import json
                            sources = json.loads(chunk)["__sources__"]
                        except Exception:
                            pass
                    else:
                        full_response += chunk
                        await websocket.send_json({"chunk": chunk})

                # Cache the full response for future non-streaming requests
                if len(full_response) > 50:
                    cache.set(data["message"], data["expert_id"], full_response, ttl=7200)

                await websocket.send_json(
                    {"response": full_response, "streaming": False, "sources": sources}
                )

                # 4. Log usage after successful generation
                await log_usage(clerk_id, data["message"], data["expert_id"])

            except Exception as e:
                opik_tracer = OpikTracer()
                opik_tracer.flush()

                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        pass


class StreamChatMessage(BaseModel):
    message: str
    expert_id: str


@app.post("/chat/stream", tags=["chat"])
async def stream_chat(body: StreamChatMessage, user: dict = Depends(get_current_user)):
    """SSE streaming chat endpoint — replaces WebSocket for LLM token streaming.

    Accepts a chat message and returns a Server-Sent Events stream.
    Event types:
      - data: {"chunk": "..."} — partial token
      - data: {"sources": [...]} — cited legal sources
      - data: {"envelope": {...}} — structured LegalAnswer (PR 2; UI may ignore)
      - data: {"error": "..."} — error message
      - data: {"done": true} — stream complete
    """
    import json
    from fastapi.responses import StreamingResponse
    from ghana_legal.infrastructure.usage import check_quota, log_usage

    clerk_id = user["sub"]

    # 1. Quota check
    quota = await check_quota(clerk_id)
    if not quota["allowed"]:
        used = quota["used_today"]
        limit = quota["daily_limit"]
        async def quota_error():
            msg = f"Daily limit reached. You have used {used}/{limit} free queries today. Please upgrade to Pro for unlimited access."
            yield f"data: {json.dumps({'error': msg, 'quota_exceeded': True})}\n\n"
        return StreamingResponse(quota_error(), media_type="text/event-stream")

    # 2. Cache check
    cache = get_cache()
    cached_response = cache.get(body.message, body.expert_id)
    if cached_response:
        async def cached_stream():
            yield f"data: {json.dumps({'chunk': cached_response})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # 3. Stream LLM response
    async def event_stream():
        try:
            expert_factory = LegalExpertFactory()
            expert = expert_factory.get_legal_expert(body.expert_id)

            response_stream = get_streaming_response(
                messages=body.message,
                expert_id=body.expert_id,
                expert_name=expert.name,
                expertise=expert.expertise,
                style=expert.style,
                legal_context="",
                clerk_id=clerk_id,
            )

            full_response = ""
            sources = []
            envelope = None
            streamed_chunks: list[str] = []
            async for chunk in response_stream:
                if chunk.startswith('{"__sources__"'):
                    try:
                        sources = json.loads(chunk)["__sources__"]
                    except Exception:
                        pass
                elif chunk.startswith('{"__envelope__"'):
                    try:
                        envelope = json.loads(chunk)["__envelope__"]
                    except Exception:
                        pass
                else:
                    full_response += chunk
                    streamed_chunks.append(chunk)

            # PR 4: if the validator flagged the answer as insufficient, swap in
            # a refusal envelope BEFORE streaming any content to the user.
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
                    "retrieval_used": bool(sources),
                    "confidence": "insufficient",
                }
                yield f"data: {json.dumps({'chunk': refusal_text})}\n\n"
                full_response = refusal_text
            else:
                for c in streamed_chunks:
                    yield f"data: {json.dumps({'chunk': c})}\n\n"

            # Send sources if any
            if sources:
                yield f"data: {json.dumps({'sources': sources})}\n\n"

            # Send the structured envelope (PR 2 dual-write, PR 4 confidence-tagged).
            if envelope:
                yield f"data: {json.dumps({'envelope': envelope})}\n\n"

            # Cache the response — but skip low/insufficient so a bad answer
            # isn't served from cache for 2 hours.
            if len(full_response) > 50 and confidence not in ("low", "insufficient"):
                cache.set(body.message, body.expert_id, full_response, ttl=7200)

            # Log usage
            await log_usage(clerk_id, body.message, body.expert_id)

            # Signal completion
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            opik_tracer = OpikTracer()
            opik_tracer.flush()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/reset-memory")
async def reset_conversation():
    """Resets the conversation state. It deletes the two collections needed for keeping LangGraph state in MongoDB.

    Raises:
        HTTPException: If there is an error resetting the conversation state.
    Returns:
        dict: A dictionary containing the result of the reset operation.
    """
    try:
        result = await reset_conversation_state()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/{expert_id}", tags=["chat"])
async def get_chat_history(expert_id: str, user: dict = Depends(get_current_user)):
    """Fetch conversation history for a user + expert from MongoDB checkpoints."""
    from langchain_core.messages import HumanMessage, AIMessage
    from langgraph.checkpoint.postgres import PostgresSaver
    from ghana_legal.config import settings

    clerk_id = user["sub"]
    thread_id = f"{clerk_id}_{expert_id}"

    try:
        db_uri = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
        if "pooler.supabase.com" in db_uri and ":5432" in db_uri:
            db_uri = db_uri.replace(":5432", ":6543")

        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        
        async with AsyncConnectionPool(conninfo=db_uri, kwargs={"prepare_threshold": None}) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint = await checkpointer.aget(config)

            if not checkpoint or "channel_values" not in checkpoint:
                return {"messages": []}

            messages = checkpoint["channel_values"].get("messages", [])

            history = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    history.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage) and msg.content:
                    # Skip tool_call messages (empty content)
                    history.append({"role": "assistant", "content": msg.content})

            return {"messages": history}

    except Exception as e:
        from loguru import logger
        logger.warning(f"Failed to load history for {thread_id}: {e}")
        return {"messages": []}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

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
from ghana_legal.infrastructure.database import init_db, close_db
from ghana_legal.infrastructure.usage import check_quota
from ghana_legal.domain.legal_expert_factory import LegalExpertFactory
from ghana_legal.infrastructure.cache import get_cache
from ghana_legal.infrastructure.webhooks import router as webhooks_router

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
    except Exception as e:
        from loguru import logger
        logger.error(f"Failed to initialize PostgreSQL: {e}")

    yield

    # Shutdown code
    opik_tracer = OpikTracer()
    opik_tracer.flush()
    await close_db()


app = FastAPI(lifespan=lifespan)

# Register webhook routes
app.include_router(webhooks_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

                # Use streaming response instead of get_response
                response_stream = get_streaming_response(
                    messages=data["message"],
                    expert_id=data["expert_id"],
                    expert_name=expert.name,
                    expertise=expert.expertise,
                    style=expert.style,
                    legal_context="",
                )

                # Send initial message to indicate streaming has started
                await websocket.send_json({"streaming": True})

                # Stream each chunk of the response
                full_response = ""
                async for chunk in response_stream:
                    full_response += chunk
                    await websocket.send_json({"chunk": chunk})

                # Cache the full response for future non-streaming requests
                if len(full_response) > 50:
                    cache.set(data["message"], data["expert_id"], full_response, ttl=7200)

                await websocket.send_json(
                    {"response": full_response, "streaming": False}
                )

                # 4. Log usage after successful generation
                await log_usage(clerk_id, data["message"], data["expert_id"])

            except Exception as e:
                opik_tracer = OpikTracer()
                opik_tracer.flush()

                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        pass


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

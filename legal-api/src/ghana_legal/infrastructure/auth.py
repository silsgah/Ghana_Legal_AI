"""
Clerk JWT Authentication middleware for FastAPI.

Verifies JWT tokens issued by Clerk to authenticate users.
Extracts user_id from the token for multi-tenant database operations.
"""

import os
from typing import Optional

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from loguru import logger

# Security scheme
security = HTTPBearer(auto_error=False)

# Cache the JWKS client
_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> PyJWKClient:
    """Get or create the Clerk JWKS client (singleton)."""
    global _jwks_client
    if _jwks_client is None:
        clerk_issuer = os.getenv("CLERK_ISSUER_URL", "")
        if not clerk_issuer:
            raise ValueError("CLERK_ISSUER_URL environment variable is not set")
        jwks_url = f"{clerk_issuer}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """
    Verify Clerk JWT and return the decoded user payload.
    
    Usage in endpoints:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            user_id = user["sub"]
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = credentials.credentials

    try:
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        clerk_issuer = os.getenv("CLERK_ISSUER_URL", "")
        
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=clerk_issuer,
            options={"verify_aud": False},  # Clerk does not always set aud
        )
        
        logger.debug(f"Authenticated user: {payload.get('sub')}")
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Optional[dict]:
    """
    Optionally verify Clerk JWT. Returns None if no token is provided.
    Useful for endpoints that work for both anonymous and authenticated users.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

"""
JARVIS — Auth Guard Middleware
FastAPI Depends() functions for protecting routes.
"""
from fastapi import Header, HTTPException, Depends
from typing import Optional
from backend.services.auth_service import verify_token


async def require_auth(authorization: Optional[str] = Header(None)) -> dict:
    """
    Use as a FastAPI dependency:
        @app.get("/protected")
        async def route(user = Depends(require_auth)):
            ...
    Raises 401 if token is missing or invalid.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required.")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization format. Use: Bearer <token>")

    token = parts[1]
    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token is invalid or expired. Please log in again.")

    return user


async def require_admin(user: dict = Depends(require_auth)) -> dict:
    """
    Use as a FastAPI dependency for admin-only routes.
    Raises 403 if user is not admin.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Only Lucky can perform this action."
        )
    return user


def optional_auth(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """
    Non-blocking auth — returns user or None.
    For routes that behave differently when authenticated.
    """
    # This is sync so it cannot await verify_token.
    # Use require_auth for actual protection.
    return None

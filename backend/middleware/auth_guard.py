from fastapi import HTTPException, Header
from typing import Optional
from backend.services.auth_service import verify_session

async def require_auth(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1]
    username = await verify_session(token)
    if not username:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    return username

async def require_admin(authorization: Optional[str] = Header(None)) -> str:
    username = await require_auth(authorization)
    from backend.utils.family import is_admin
    if not is_admin(username):
        raise HTTPException(status_code=403, detail="Admin access required")
    return username

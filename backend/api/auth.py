"""
JARVIS — Auth API Routes
POST /auth/login
POST /auth/register
POST /auth/verify
GET  /auth/status  (admin only)
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from backend.models.auth import LoginRequest, RegisterRequest, VerifyRequest
from backend.services import auth_service
from backend.middleware.auth_guard import require_admin
from backend.middleware.rate_limiter import check_login_rate, check_register_rate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    check_login_rate(request)
    result = await auth_service.login(body.username, body.password, body.device_id)
    return result


@router.post("/register")
async def register(body: RegisterRequest, request: Request):
    check_register_rate(request)
    result = await auth_service.register_guest(
        body.username,
        body.password,
        body.display_name,
        body.relation,
        body.knows_member,
    )
    return result


@router.post("/verify")
async def verify(body: VerifyRequest):
    user = await auth_service.verify_token(body.token, body.device_id)
    return {"valid": user is not None, "user": user}


@router.get("/status")
async def auth_status(admin=Depends(require_admin)):
    """Admin-only: list all users and their approval status."""
    users = await auth_service.list_all_users()
    return {"users": users}

"""
JARVIS — Birthdays API Routes
"""
from fastapi import APIRouter, Depends
from backend.middleware.auth_guard import require_auth
from backend.services import memory_service

router = APIRouter(prefix="/birthdays", tags=["birthdays"])


@router.get("")
async def get_birthdays(user=Depends(require_auth)):
    upcoming = await memory_service.get_upcoming_birthdays(30)
    all_bdays = await memory_service.get_upcoming_birthdays(365)
    return {"upcoming": upcoming, "all": all_bdays}

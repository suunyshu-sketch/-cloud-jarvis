"""
JARVIS — Reminders API Routes
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from backend.middleware.auth_guard import require_auth
from backend.services import memory_service

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreate(BaseModel):
    text:      str = Field(..., min_length=1, max_length=500)
    remind_at: str = Field(...)    # ISO datetime string
    device_id: str = Field(..., max_length=100)


@router.get("/{device_id}")
async def get_reminders(device_id: str, user=Depends(require_auth)):
    reminders = await memory_service.get_reminders(device_id)
    return {"reminders": reminders}


@router.post("")
async def add_reminder(body: ReminderCreate, user=Depends(require_auth)):
    try:
        remind_dt = datetime.fromisoformat(body.remind_at.replace("Z", "+00:00"))
    except ValueError:
        return {"success": False, "error": "Invalid datetime format. Use ISO 8601."}

    rid = await memory_service.save_reminder(
        user.get("family_member", ""),
        body.device_id,
        body.text,
        remind_dt,
    )
    return {"id": rid, "status": "set"}

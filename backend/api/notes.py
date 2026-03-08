"""
JARVIS — Notes API Routes
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from backend.middleware.auth_guard import require_auth
from backend.services import memory_service

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteCreate(BaseModel):
    title:     str = Field(default="", max_length=120)
    content:   str = Field(..., min_length=1, max_length=5000)
    device_id: str = Field(..., max_length=100)


@router.get("/{device_id}")
async def get_notes(device_id: str, user=Depends(require_auth)):
    notes = await memory_service.get_notes(device_id)
    return {"notes": notes}


@router.post("")
async def add_note(body: NoteCreate, user=Depends(require_auth)):
    title = body.title or (body.content[:30] + "..." if len(body.content) > 30 else body.content)
    note_id = await memory_service.save_note(
        user.get("family_member", ""),
        body.device_id,
        title,
        body.content,
    )
    return {"id": note_id, "status": "saved"}


@router.delete("/{note_id}")
async def delete_note(note_id: int, user=Depends(require_auth)):
    await memory_service.delete_note(note_id)
    return {"status": "deleted"}

"""
backend/api/productivity.py
────────────────────────────
Todos, Notes, Reminders, Birthdays — REST endpoints.
All protected by require_auth.
"""
from fastapi import APIRouter, Depends

from backend.middleware.auth_guard import require_auth
from backend.services.productivity import (
    get_todos, toggle_todo, delete_todo,
    get_notes, delete_note,
    get_reminders,
    get_upcoming_birthdays,
)

router = APIRouter(tags=["productivity"])


# ── Todos ──────────────────────────────────────────────────

@router.get("/todos/{device_id}")
async def todos(device_id: str, user: dict = Depends(require_auth)):
    return {"todos": await get_todos(device_id)}


@router.post("/todo/toggle/{todo_id}")
async def toggle(todo_id: int, user: dict = Depends(require_auth)):
    await toggle_todo(todo_id)
    return {"status": "toggled"}


@router.delete("/todo/{todo_id}")
async def delete(todo_id: int, user: dict = Depends(require_auth)):
    await delete_todo(todo_id)
    return {"status": "deleted"}


# ── Notes ──────────────────────────────────────────────────

@router.get("/notes/{device_id}")
async def notes(device_id: str, user: dict = Depends(require_auth)):
    return {"notes": await get_notes(device_id)}


@router.delete("/note/{note_id}")
async def delete_note_route(note_id: int, user: dict = Depends(require_auth)):
    await delete_note(note_id)
    return {"status": "deleted"}


# ── Reminders ──────────────────────────────────────────────

@router.get("/reminders/{device_id}")
async def reminders(device_id: str, user: dict = Depends(require_auth)):
    return {"reminders": await get_reminders(device_id)}


# ── Birthdays ──────────────────────────────────────────────

@router.get("/birthdays")
async def birthdays(user: dict = Depends(require_auth)):
    return {"upcoming": await get_upcoming_birthdays(30)}

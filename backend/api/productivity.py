from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.middleware.auth_guard import require_auth
from backend.services import memory_service

# ── Todos ──
todos_router = APIRouter(prefix="/todos", tags=["todos"])

class TodoCreate(BaseModel):
    text: str
    category: str = "general"
    device_id: str = ""

@todos_router.get("/")
async def get_todos(device_id: str = "", username: str = Depends(require_auth)):
    return await memory_service.get_todos(device_id or username, username)

@todos_router.post("/")
async def create_todo(req: TodoCreate, username: str = Depends(require_auth)):
    id_ = await memory_service.save_todo(username, req.device_id or username, req.text, req.category)
    return {"id": id_, "text": req.text}

@todos_router.patch("/{todo_id}/toggle")
async def toggle_todo(todo_id: int, username: str = Depends(require_auth)):
    await memory_service.toggle_todo(todo_id)
    return {"success": True}

@todos_router.delete("/{todo_id}")
async def delete_todo(todo_id: int, username: str = Depends(require_auth)):
    await memory_service.delete_todo(todo_id)
    return {"success": True}


# ── Notes ──
notes_router = APIRouter(prefix="/notes", tags=["notes"])

class NoteCreate(BaseModel):
    title: str
    content: str
    device_id: str = ""

@notes_router.get("/")
async def get_notes(device_id: str = "", username: str = Depends(require_auth)):
    return await memory_service.get_notes(device_id or username)

@notes_router.post("/")
async def create_note(req: NoteCreate, username: str = Depends(require_auth)):
    id_ = await memory_service.save_note(username, req.device_id or username, req.title, req.content)
    return {"id": id_, "title": req.title}

@notes_router.delete("/{note_id}")
async def delete_note(note_id: int, username: str = Depends(require_auth)):
    await memory_service.delete_note(note_id)
    return {"success": True}


# ── Reminders ──
reminders_router = APIRouter(prefix="/reminders", tags=["reminders"])

class ReminderCreate(BaseModel):
    text: str
    remind_at: str
    device_id: str = ""

@reminders_router.get("/")
async def get_reminders(device_id: str = "", username: str = Depends(require_auth)):
    return await memory_service.get_reminders(device_id or username)

@reminders_router.post("/")
async def create_reminder(req: ReminderCreate, username: str = Depends(require_auth)):
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(req.remind_at.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid datetime format")
    id_ = await memory_service.save_reminder(username, req.device_id or username, req.text, dt)
    return {"id": id_}

@reminders_router.patch("/{reminder_id}/done")
async def mark_done(reminder_id: int, username: str = Depends(require_auth)):
    await memory_service.mark_reminder_done(reminder_id)
    return {"success": True}


# ── Birthdays ──
birthdays_router = APIRouter(prefix="/birthdays", tags=["birthdays"])

class BirthdayCreate(BaseModel):
    name: str
    dob: str
    relation: str = ""

@birthdays_router.get("/")
async def get_birthdays(username: str = Depends(require_auth)):
    return await memory_service.get_upcoming_birthdays(days_ahead=365)

@birthdays_router.post("/")
async def create_birthday(req: BirthdayCreate, username: str = Depends(require_auth)):
    await memory_service.save_birthday(username, req.name, req.dob, req.relation)
    return {"success": True}


# ── Music ──
music_router = APIRouter(prefix="/music", tags=["music"])

@music_router.get("/search")
async def search_music(q: str, username: str = Depends(require_auth)):
    import httpx
    try:
        url = f"https://itunes.apple.com/search?term={q}&media=music&limit=10"
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
            data = r.json()
            results = data.get("results", [])
            tracks = [{
                "trackName": t.get("trackName",""),
                "artistName": t.get("artistName",""),
                "previewUrl": t.get("previewUrl",""),
                "artworkUrl": t.get("artworkUrl60",""),
                "genre": t.get("primaryGenreName",""),
            } for t in results]
            return {"tracks": tracks}
    except Exception as e:
        return {"tracks": [], "error": str(e)}

@music_router.get("/genre/{genre}")
async def genre_music(genre: str, username: str = Depends(require_auth)):
    return await search_music(f"{genre} music", username)

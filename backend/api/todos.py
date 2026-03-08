"""
JARVIS — Todos API Routes
All routes require authentication.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from backend.middleware.auth_guard import require_auth
from backend.services import memory_service

router = APIRouter(prefix="/todos", tags=["todos"])


class TodoCreate(BaseModel):
    text:      str = Field(..., min_length=1, max_length=500)
    device_id: str = Field(..., max_length=100)
    category:  str = Field(default="general", max_length=30)


@router.get("/{device_id}")
async def get_todos(device_id: str, user=Depends(require_auth)):
    todos = await memory_service.get_todos(device_id, user.get("family_member", ""))
    return {"todos": todos}


@router.post("")
async def add_todo(body: TodoCreate, user=Depends(require_auth)):
    todo_id = await memory_service.save_todo(
        user.get("family_member", ""),
        body.device_id,
        body.text,
        body.category,
    )
    return {"id": todo_id, "status": "added"}


@router.post("/toggle/{todo_id}")
async def toggle_todo(todo_id: int, user=Depends(require_auth)):
    await memory_service.toggle_todo(todo_id)
    return {"status": "toggled"}


@router.delete("/{todo_id}")
async def delete_todo(todo_id: int, user=Depends(require_auth)):
    await memory_service.delete_todo(todo_id)
    return {"status": "deleted"}

"""
backend/services/productivity.py
──────────────────────────────────
Todos, Notes, Reminders, and Birthdays — all async DB operations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.db.connection import get_pool


# ── Todos ──────────────────────────────────────────────────

async def save_todo(person: str, device_id: str, text: str, category: str = "general") -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO todos (person, device_id, text, category)
               VALUES ($1,$2,$3,$4) RETURNING id""",
            person, device_id, text[:500], category,
        )
    return row["id"]


async def get_todos(device_id: str, person: str = "") -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, text, done, category, created_at FROM todos WHERE device_id=$1 ORDER BY id DESC",
            device_id,
        )
    return [
        {
            "id":       r["id"],
            "text":     r["text"],
            "done":     r["done"],
            "category": r["category"],
            "created":  r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def toggle_todo(todo_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE todos SET done = NOT done WHERE id=$1", todo_id)


async def delete_todo(todo_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM todos WHERE id=$1", todo_id)


# ── Notes ──────────────────────────────────────────────────

async def save_note(person: str, device_id: str, title: str, content: str) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO notes (person, device_id, title, content) VALUES ($1,$2,$3,$4) RETURNING id",
            person, device_id, title[:100], content[:5000],
        )
    return row["id"]


async def get_notes(device_id: str) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, content, created_at FROM notes WHERE device_id=$1 ORDER BY id DESC",
            device_id,
        )
    return [
        {
            "id":      r["id"],
            "title":   r["title"],
            "content": r["content"],
            "date":    r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def delete_note(note_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM notes WHERE id=$1", note_id)


# ── Reminders ──────────────────────────────────────────────

async def save_reminder(person: str, device_id: str, text: str, remind_at: datetime) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO reminders (person, device_id, text, remind_at) VALUES ($1,$2,$3,$4)",
            person, device_id, text[:500], remind_at,
        )


async def get_reminders(device_id: str, include_done: bool = False) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        if include_done:
            rows = await conn.fetch(
                "SELECT id, text, remind_at, done FROM reminders WHERE device_id=$1 ORDER BY remind_at",
                device_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT id, text, remind_at, done FROM reminders WHERE device_id=$1 AND done=FALSE ORDER BY remind_at",
                device_id,
            )
    return [
        {
            "id":   r["id"],
            "text": r["text"],
            "time": r["remind_at"].isoformat() if r["remind_at"] else None,
            "done": r["done"],
        }
        for r in rows
    ]


async def get_due_reminders(device_id: str) -> list[dict]:
    """Get reminders that are due now and mark them done."""
    pool = get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, text, remind_at FROM reminders WHERE device_id=$1 AND done=FALSE AND remind_at <= $2",
            device_id, now,
        )
        if rows:
            ids = [r["id"] for r in rows]
            await conn.execute("UPDATE reminders SET done=TRUE WHERE id=ANY($1)", ids)
    return [{"id": r["id"], "text": r["text"], "time": r["remind_at"].isoformat()} for r in rows]


# ── Birthdays ──────────────────────────────────────────────

async def save_birthday(person: str, name: str, dob: str, relation: str = "") -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO birthdays (person, name, dob, relation) VALUES ($1,$2,$3,$4)
               ON CONFLICT DO NOTHING""",
            person, name, dob, relation,
        )


async def get_upcoming_birthdays(days_ahead: int = 30) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT name, dob, relation FROM birthdays
               WHERE EXTRACT(MONTH FROM dob::date) = EXTRACT(MONTH FROM NOW())
                  OR EXTRACT(MONTH FROM dob::date) = EXTRACT(MONTH FROM NOW() + INTERVAL '30 days')
               ORDER BY EXTRACT(DAY FROM dob::date)"""
        )
    return [
        {"name": r["name"], "dob": str(r["dob"]) if r["dob"] else None, "relation": r["relation"]}
        for r in rows
    ]

import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from backend.db.connection import get_pool
from backend.config import config

# ── In-process caches (Phase 9 performance) ──
_hot_cache: dict = {}   # device_id -> list of recent messages
_facts_cache: dict = {} # person -> list of facts
_facts_dirty = True

def _invalidate_facts_cache():
    global _facts_dirty
    _facts_dirty = True

def score_importance(role: str, content: str) -> float:
    if role == "system":
        return 0.0
    lower = content.lower()
    score = 0.3

    fact_triggers = ["my name is","i am","i live","i work","i like","i love",
                     "call me","i'm from","nenu","i have","i hate","i prefer",
                     "my favourite","my favorite","i study","i play"]
    if any(t in lower for t in fact_triggers):
        score += 0.5

    cmd_triggers = ["remind me","todo","note:","remember","birthday","set a reminder"]
    if any(t in lower for t in cmd_triggers):
        score += 0.4

    emotion_words = ["sad","crying","stressed","anxious","excited","happy","angry",
                     "worried","scared","depressed","frustrated","grateful","love"]
    if any(w in lower for w in emotion_words):
        score += 0.3

    if len(content) > 200:
        score += 0.2

    greetings = ["hi","hello","hey","ok","okay","sure","thanks","bye","haha","lol","hmm"]
    if lower.strip() in greetings or (len(content) < 15 and any(g in lower for g in greetings)):
        score = max(0.1, score - 0.4)

    return min(1.0, score)

async def save_message(role: str, content: str, device_id: str, person: str = "", private: bool = False) -> None:
    try:
        if private:
            return
        importance = score_importance(role, content)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO memories (device_id, person, role, content, importance) VALUES ($1,$2,$3,$4,$5)",
                device_id, person, role, content, importance
            )
        # Update hot cache
        if device_id not in _hot_cache:
            _hot_cache[device_id] = []
        _hot_cache[device_id].append({"role": role, "content": content})
        if len(_hot_cache[device_id]) > config.HOT_MEMORY_LIMIT:
            _hot_cache[device_id].pop(0)
    except Exception as e:
        print(f"save_message error: {e}")

async def get_history(device_id: str, limit: int = 15) -> list:
    # Try hot cache first
    if device_id in _hot_cache and len(_hot_cache[device_id]) >= min(limit, 5):
        return _hot_cache[device_id][-limit:]
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content FROM memories
                   WHERE device_id=$1 AND archived=FALSE
                   ORDER BY created_at DESC LIMIT $2""",
                device_id, limit
            )
            msgs = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
            _hot_cache[device_id] = msgs
            return msgs
    except Exception as e:
        print(f"get_history error: {e}")
        return []

async def get_message_count(device_id: str) -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM memories WHERE device_id=$1", device_id) or 0
    except Exception:
        return 0

async def get_warm_memory(person: str, limit: int = 3) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT summary, period_start, period_end FROM memory_archive WHERE person=$1 ORDER BY created_at DESC LIMIT $2",
                person, limit
            )
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"get_warm_memory error: {e}")
        return []

async def save_warm_summary(person: str, device_id: str, summary: str, period_start, period_end, count: int) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memory_archive (person, device_id, summary, period_start, period_end, message_count)
                   VALUES ($1,$2,$3,$4,$5,$6)""",
                person, device_id, summary, period_start, period_end, count
            )
    except Exception as e:
        print(f"save_warm_summary error: {e}")

async def save_fact(key: str, value: str, person: str = "family", importance: float = 0.7) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO facts (key, value, person, importance)
                   VALUES ($1,$2,$3,$4)
                   ON CONFLICT DO NOTHING""",
                key, value, person, importance
            )
        _invalidate_facts_cache()
    except Exception as e:
        print(f"save_fact error: {e}")

async def get_all_facts() -> dict:
    global _facts_dirty
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT key, value, person FROM facts ORDER BY importance DESC, last_accessed DESC LIMIT 100"
            )
            _facts_dirty = False
            return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print(f"get_all_facts error: {e}")
        return {}

async def get_person_facts(person: str, limit: int = 10) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT key, value FROM facts WHERE person=$1 OR person='family' ORDER BY importance DESC LIMIT $2",
                person, limit
            )
            return [f"{r['key']}: {r['value']}" for r in rows]
    except Exception as e:
        print(f"get_person_facts error: {e}")
        return []

async def get_lang_preference(device_id: str) -> str:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT lang_preference FROM persons WHERE name=$1", device_id)
            return val or "english"
    except Exception:
        return "english"

async def save_lang_preference(device_id: str, lang: str) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO persons (name, lang_preference) VALUES ($1,$2) ON CONFLICT (name) DO UPDATE SET lang_preference=$2",
                device_id, lang
            )
    except Exception as e:
        print(f"save_lang_preference error: {e}")

async def save_device(device_id: str, person: str, user_agent: str = "") -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO devices (device_id, person, user_agent, last_seen)
                   VALUES ($1,$2,$3,NOW())
                   ON CONFLICT (device_id) DO UPDATE SET last_seen=NOW(), person=$2""",
                device_id, person, user_agent
            )
    except Exception as e:
        print(f"save_device error: {e}")

async def get_all_devices() -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT device_id, person, last_seen FROM devices ORDER BY last_seen DESC")
            return [dict(r) for r in rows]
    except Exception:
        return []

async def save_todo(person: str, device_id: str, text: str, category: str = "general") -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO todos (person, device_id, text, category) VALUES ($1,$2,$3,$4) RETURNING id",
                person, device_id, text, category
            )
            return row["id"]
    except Exception as e:
        print(f"save_todo error: {e}")
        return -1

async def get_todos(device_id: str, person: str = "") -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, text, category, done, created_at FROM todos WHERE device_id=$1 OR person=$2 ORDER BY created_at DESC LIMIT 50",
                device_id, person
            )
            return [dict(r) for r in rows]
    except Exception:
        return []

async def toggle_todo(todo_id: int) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE todos SET done=NOT done WHERE id=$1", todo_id)
    except Exception as e:
        print(f"toggle_todo error: {e}")

async def delete_todo(todo_id: int) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM todos WHERE id=$1", todo_id)
    except Exception as e:
        print(f"delete_todo error: {e}")

async def save_note(person: str, device_id: str, title: str, content: str) -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO notes (person, device_id, title, content) VALUES ($1,$2,$3,$4) RETURNING id",
                person, device_id, title, content
            )
            return row["id"]
    except Exception as e:
        print(f"save_note error: {e}")
        return -1

async def get_notes(device_id: str) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, title, content, created_at FROM notes WHERE device_id=$1 ORDER BY created_at DESC LIMIT 50",
                device_id
            )
            return [dict(r) for r in rows]
    except Exception:
        return []

async def delete_note(note_id: int) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM notes WHERE id=$1", note_id)
    except Exception as e:
        print(f"delete_note error: {e}")

async def save_reminder(person: str, device_id: str, text: str, remind_at) -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO reminders (person, device_id, text, remind_at) VALUES ($1,$2,$3,$4) RETURNING id",
                person, device_id, text, remind_at
            )
            return row["id"]
    except Exception as e:
        print(f"save_reminder error: {e}")
        return -1

async def get_due_reminders(device_id: str) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, text, remind_at FROM reminders WHERE device_id=$1 AND done=FALSE AND remind_at <= NOW()",
                device_id
            )
            return [dict(r) for r in rows]
    except Exception:
        return []

async def get_reminders(device_id: str, include_done: bool = False) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            q = "SELECT id, text, remind_at, done FROM reminders WHERE device_id=$1"
            if not include_done:
                q += " AND done=FALSE"
            q += " ORDER BY remind_at ASC LIMIT 20"
            rows = await conn.fetch(q, device_id)
            return [dict(r) for r in rows]
    except Exception:
        return []

async def mark_reminder_done(reminder_id: int) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE reminders SET done=TRUE WHERE id=$1", reminder_id)
    except Exception as e:
        print(f"mark_reminder_done error: {e}")

async def save_birthday(person: str, name: str, dob: str, relation: str = "") -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO birthdays (person, name, dob, relation) VALUES ($1,$2,$3,$4)",
                person, name, dob, relation
            )
    except Exception as e:
        print(f"save_birthday error: {e}")

async def get_upcoming_birthdays(days_ahead: int = 7) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, dob, person, relation FROM birthdays")
            from datetime import date
            today = date.today()
            upcoming = []
            for r in rows:
                try:
                    parts = r["dob"].split("-")
                    if len(parts) >= 2:
                        bday = date(today.year, int(parts[1]), int(parts[2] if len(parts) > 2 else 1))
                        if bday < today:
                            bday = date(today.year + 1, bday.month, bday.day)
                        diff = (bday - today).days
                        if diff <= days_ahead:
                            upcoming.append({"name": r["name"], "dob": r["dob"], "days_until": diff})
                except Exception:
                    pass
            return upcoming
    except Exception:
        return []

async def save_announcement(title: str, content: str, from_person: str) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO announcements (title, content, from_person) VALUES ($1,$2,$3)",
                title, content, from_person
            )
    except Exception as e:
        print(f"save_announcement error: {e}")

async def get_announcements(active_only: bool = True) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            q = "SELECT title, content, from_person, created_at FROM announcements"
            if active_only:
                q += " WHERE active=TRUE"
            q += " ORDER BY created_at DESC LIMIT 5"
            rows = await conn.fetch(q)
            return [dict(r) for r in rows]
    except Exception:
        return []

async def save_feedback(person: str, user_msg: str, jarvis_msg: str, feedback: str, source: str = "user") -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO rl_feedback (person, user_msg, jarvis_msg, feedback, source) VALUES ($1,$2,$3,$4,$5)",
                person, user_msg[:500], jarvis_msg[:500], feedback, source
            )
    except Exception as e:
        print(f"save_feedback error: {e}")

async def get_rl_patterns(person: str) -> tuple:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            pos = await conn.fetch(
                "SELECT jarvis_msg FROM rl_feedback WHERE person=$1 AND feedback='positive' ORDER BY created_at DESC LIMIT 5",
                person
            )
            neg = await conn.fetch(
                "SELECT jarvis_msg FROM rl_feedback WHERE person=$1 AND feedback='negative' ORDER BY created_at DESC LIMIT 5",
                person
            )
            return (
                [r["jarvis_msg"][:100] for r in pos],
                [r["jarvis_msg"][:100] for r in neg]
            )
    except Exception:
        return ([], [])

async def log_error(error_type: str, message: str, context: str = "", person: str = "") -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO error_logs (error_type, message, context, person) VALUES ($1,$2,$3,$4)",
                error_type, message[:500], context[:500], person
            )
    except Exception:
        pass

async def get_memory_stats() -> dict:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            total_msgs = await conn.fetchval("SELECT COUNT(*) FROM memories") or 0
            total_facts = await conn.fetchval("SELECT COUNT(*) FROM facts") or 0
            total_archive = await conn.fetchval("SELECT COUNT(*) FROM memory_archive") or 0
            total_feedback = await conn.fetchval("SELECT COUNT(*) FROM rl_feedback") or 0
            return {
                "total_messages": total_msgs,
                "total_facts": total_facts,
                "archive_entries": total_archive,
                "total_feedback": total_feedback,
            }
    except Exception:
        return {}

async def wipe_chats() -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM memories")
            await conn.execute("DELETE FROM memory_archive")
        _hot_cache.clear()
    except Exception as e:
        print(f"wipe_chats error: {e}")

async def wipe_all() -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            for tbl in ["memories","memory_archive","facts","rl_feedback",
                        "personality_profiles","emotional_history","conversation_insights"]:
                await conn.execute(f"DELETE FROM {tbl}")
        _hot_cache.clear()
        _facts_cache.clear()
    except Exception as e:
        print(f"wipe_all error: {e}")

"""
JARVIS — Memory Service (Async, Tiered)
Handles: messages, facts, devices, compression, cross-tier search.
All DB calls are truly async via asyncpg.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from backend.db.connection import get_pool
from backend import config


# ══════════════════════════════════════════════════════════
#  MESSAGES
# ══════════════════════════════════════════════════════════

async def save_message(role: str, content: str, device_id: str, private: bool = False) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memories (role, content, timestamp, device_id, private)
                   VALUES ($1, $2, NOW(), $3, $4)""",
                role, content[:4000], device_id, private
            )
    except Exception as e:
        print(f"save_message error: {e}")


async def get_history(device_id: str, limit: int = 12) -> list:
    """Get recent conversation history for a device — used in AI prompt."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content FROM memories
                   WHERE device_id=$1 AND private=FALSE
                   ORDER BY id DESC LIMIT $2""",
                device_id, limit
            )
        # Reverse so oldest first (correct for LLM message history)
        result = []
        for r in reversed(rows):
            llm_role = "assistant" if r["role"] in ("assistant","jarvis") else "user"
            result.append({"role": llm_role, "content": r["content"]})
        return result
    except Exception as e:
        print(f"get_history error: {e}")
        return []


async def get_message_count(device_id: str) -> int:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM memories WHERE device_id=$1", device_id
            ) or 0
    except:
        return 0


# ══════════════════════════════════════════════════════════
#  FACTS
# ══════════════════════════════════════════════════════════

async def save_fact(key: str, value: str, person: str = "family") -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO facts (key, value, updated, person)
                   VALUES ($1, $2, NOW(), $3)
                   ON CONFLICT (key) DO UPDATE SET value=$2, updated=NOW()""",
                key, str(value)[:500], person
            )
    except Exception as e:
        print(f"save_fact error: {e}")


async def get_fact(key: str) -> Optional[str]:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT value FROM facts WHERE key=$1", key
            )
    except:
        return None


async def get_all_facts() -> dict:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM facts")
        return {r["key"]: r["value"] for r in rows}
    except:
        return {}


async def get_lang_preference(device_id: str) -> str:
    val = await get_fact(f"langpref_{device_id}")
    return val or "english"


async def save_lang_preference(device_id: str, lang: str) -> None:
    await save_fact(f"langpref_{device_id}", lang, "device")


# ══════════════════════════════════════════════════════════
#  DEVICES
# ══════════════════════════════════════════════════════════

async def save_device(
    device_id: str, device_name: str, owner: str, user_agent: str = ""
) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO devices
                   (device_id, device_name, owner, last_seen, first_seen, user_agent, message_count)
                   VALUES ($1, $2, $3, NOW(), NOW(), $4, 1)
                   ON CONFLICT (device_id) DO UPDATE
                     SET device_name=$2, owner=$3, last_seen=NOW(),
                         message_count=devices.message_count+1,
                         user_agent=CASE WHEN $4!='' THEN $4 ELSE devices.user_agent END""",
                device_id, device_name, owner, user_agent
            )
    except Exception as e:
        print(f"save_device error: {e}")


async def touch_device(device_id: str) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE devices SET last_seen=NOW() WHERE device_id=$1", device_id
            )
    except Exception as e:
        print(f"touch_device error: {e}")


async def get_all_devices() -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT device_id, device_name, owner, last_seen, message_count FROM devices"
            )
        return [
            {
                "device_id": r["device_id"],
                "name": r["device_name"],
                "owner": r["owner"],
                "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
                "message_count": r["message_count"] or 0,
            }
            for r in rows
        ]
    except:
        return []


# ══════════════════════════════════════════════════════════
#  TODOS
# ══════════════════════════════════════════════════════════

async def save_todo(person: str, device_id: str, text: str, category: str = "general") -> int:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO todos (person, device_id, text, done, category, created_at)
                   VALUES ($1, $2, $3, FALSE, $4, NOW()) RETURNING id""",
                person, device_id, text[:500], category
            )
    except Exception as e:
        print(f"save_todo error: {e}")
        return -1


async def get_todos(device_id: str, person: str = "") -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, text, done, category, created_at FROM todos
                   WHERE device_id=$1 ORDER BY id DESC LIMIT 50""",
                device_id
            )
        return [{"id": r["id"], "text": r["text"], "done": r["done"],
                 "category": r["category"]} for r in rows]
    except:
        return []


async def toggle_todo(todo_id: int) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE todos SET done = NOT done WHERE id=$1", todo_id
            )
    except Exception as e:
        print(f"toggle_todo error: {e}")


async def delete_todo(todo_id: int) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM todos WHERE id=$1", todo_id)
    except Exception as e:
        print(f"delete_todo error: {e}")


# ══════════════════════════════════════════════════════════
#  NOTES
# ══════════════════════════════════════════════════════════

async def save_note(person: str, device_id: str, title: str, content: str) -> int:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO notes (person, device_id, title, content, created_at)
                   VALUES ($1, $2, $3, $4, NOW()) RETURNING id""",
                person, device_id, title[:120], content[:5000]
            )
    except Exception as e:
        print(f"save_note error: {e}")
        return -1


async def get_notes(device_id: str) -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, title, content, created_at FROM notes
                   WHERE device_id=$1 ORDER BY id DESC LIMIT 30""",
                device_id
            )
        return [{"id": r["id"], "title": r["title"], "content": r["content"],
                 "date": r["created_at"].isoformat() if r["created_at"] else ""} for r in rows]
    except:
        return []


async def delete_note(note_id: int) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM notes WHERE id=$1", note_id)
    except Exception as e:
        print(f"delete_note error: {e}")


# ══════════════════════════════════════════════════════════
#  REMINDERS
# ══════════════════════════════════════════════════════════

async def save_reminder(person: str, device_id: str, text: str, remind_at: datetime) -> int:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO reminders (person, device_id, text, remind_at, done, created_at)
                   VALUES ($1, $2, $3, $4, FALSE, NOW()) RETURNING id""",
                person, device_id, text[:500], remind_at
            )
    except Exception as e:
        print(f"save_reminder error: {e}")
        return -1


async def get_due_reminders(device_id: str) -> list:
    """Fetch and mark as done all reminders that are due now."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, text, remind_at FROM reminders
                   WHERE device_id=$1 AND done=FALSE AND remind_at<=NOW()""",
                device_id
            )
            if rows:
                ids = [r["id"] for r in rows]
                await conn.execute(
                    "UPDATE reminders SET done=TRUE WHERE id=ANY($1::bigint[])", ids
                )
        return [{"id": r["id"], "text": r["text"]} for r in rows]
    except Exception as e:
        print(f"get_due_reminders error: {e}")
        return []


async def get_reminders(device_id: str, include_done: bool = False) -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            if include_done:
                rows = await conn.fetch(
                    "SELECT id, text, remind_at, done FROM reminders WHERE device_id=$1 ORDER BY remind_at",
                    device_id
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, text, remind_at, done FROM reminders WHERE device_id=$1 AND done=FALSE ORDER BY remind_at",
                    device_id
                )
        return [{"id": r["id"], "text": r["text"],
                 "time": r["remind_at"].isoformat() if r["remind_at"] else "",
                 "done": r["done"]} for r in rows]
    except:
        return []


# ══════════════════════════════════════════════════════════
#  BIRTHDAYS
# ══════════════════════════════════════════════════════════

async def save_birthday(person: str, name: str, dob: str, relation: str = "") -> None:
    try:
        from datetime import date
        dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO birthdays (person, name, dob, relation)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT DO NOTHING""",
                person, name, dob_date, relation
            )
    except Exception as e:
        print(f"save_birthday error: {e}")


async def get_upcoming_birthdays(days_ahead: int = 30) -> list:
    try:
        pool = get_pool()
        today = datetime.now(timezone.utc).date()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, dob, relation, person FROM birthdays")
        upcoming = []
        for r in rows:
            dob = r["dob"]
            # Next birthday this year or next
            try:
                next_bday = dob.replace(year=today.year)
                if next_bday < today:
                    next_bday = dob.replace(year=today.year + 1)
                delta = (next_bday - today).days
                if 0 <= delta <= days_ahead:
                    upcoming.append({
                        "name": r["name"],
                        "dob": str(r["dob"]),
                        "relation": r["relation"],
                        "days_until": delta,
                        "next_birthday": str(next_bday),
                    })
            except Exception:
                pass
        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming
    except Exception as e:
        print(f"get_upcoming_birthdays error: {e}")
        return []


# ══════════════════════════════════════════════════════════
#  ANNOUNCEMENTS
# ══════════════════════════════════════════════════════════

async def save_announcement(title: str, content: str, from_person: str) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO announcements (title, content, from_person, created_at, active)
                   VALUES ($1, $2, $3, NOW(), TRUE)""",
                title, content, from_person
            )
    except Exception as e:
        print(f"save_announcement error: {e}")


async def get_announcements(active_only: bool = True) -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            if active_only:
                rows = await conn.fetch(
                    "SELECT id, title, content, from_person, created_at FROM announcements WHERE active=TRUE ORDER BY created_at DESC LIMIT 5"
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, title, content, from_person, created_at FROM announcements ORDER BY created_at DESC LIMIT 20"
                )
        return [{"id": r["id"], "title": r["title"], "content": r["content"],
                 "from": r["from_person"],
                 "date": r["created_at"].isoformat() if r["created_at"] else ""} for r in rows]
    except:
        return []


# ══════════════════════════════════════════════════════════
#  RL FEEDBACK
# ══════════════════════════════════════════════════════════

async def save_feedback(
    person: str, device_id: str,
    user_msg: str, jarvis_response: str,
    feedback: str, topic: str = "general"
) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO rl_feedback
                   (person, device_id, user_msg, jarvis_response, feedback, topic, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, NOW())""",
                person, device_id,
                user_msg[:1000], jarvis_response[:1000],
                feedback, topic
            )
    except Exception as e:
        print(f"save_feedback error: {e}")


async def get_rl_patterns(person: str) -> tuple[list, list]:
    """Returns (positive_patterns, negative_patterns) for the AI prompt."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT jarvis_response, feedback FROM rl_feedback
                   WHERE person=$1 ORDER BY id DESC LIMIT 20""",
                person
            )
        pos = [r["jarvis_response"][:100] for r in rows if r["feedback"] == "positive"][:3]
        neg = [r["jarvis_response"][:100] for r in rows if r["feedback"] == "negative"][:3]
        return pos, neg
    except:
        return [], []


# ══════════════════════════════════════════════════════════
#  TIERED MEMORY COMPRESSION
# ══════════════════════════════════════════════════════════

async def compress_old_messages() -> None:
    """
    Compress messages older than 6 months into a warm-archive summary.
    Uses the fast LLM model to avoid burning tokens.
    """
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        pool = get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, role, content, timestamp, device_id
                   FROM memories
                   WHERE timestamp < NOW() - INTERVAL '180 days'
                   ORDER BY timestamp ASC LIMIT 200"""
            )

        if not rows or len(rows) < 10:
            return

        convo = "\n".join([f"{r['role'].upper()}: {r['content']}" for r in rows])
        resp = client.chat.completions.create(
            model=config.MODEL_FAST,
            messages=[
                {"role": "system", "content": "Compress these JARVIS conversations into a detailed summary. Preserve ALL names, facts, preferences, events, and personal details. Be thorough."},
                {"role": "user", "content": convo[:5000]}
            ],
            max_tokens=600
        )
        summary = resp.choices[0].message.content.strip()

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memory_archive
                   (tier, period_start, period_end, summary, created_at)
                   VALUES (2, $1, $2, $3, NOW())""",
                rows[0]["timestamp"], rows[-1]["timestamp"], summary
            )
            ids = [r["id"] for r in rows]
            await conn.execute(
                "DELETE FROM memories WHERE id=ANY($1::bigint[])", ids
            )

        print(f"🗜️  Compressed {len(rows)} messages → 1 warm-archive summary")

    except Exception as e:
        print(f"compress_old_messages error: {e}")


async def search_all_tiers(query: str, device_id: str = "") -> str:
    """Cross-tier full-text search. Returns best match as a string."""
    results = []
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Hot tier
            if device_id:
                rows = await conn.fetch(
                    """SELECT role, content FROM memories
                       WHERE device_id=$1 AND content ILIKE $2
                       ORDER BY id DESC LIMIT 5""",
                    device_id, f"%{query}%"
                )
            else:
                rows = await conn.fetch(
                    """SELECT role, content FROM memories
                       WHERE content ILIKE $1 ORDER BY id DESC LIMIT 5""",
                    f"%{query}%"
                )
            if rows:
                results.append("[RECENT]\n" + "\n".join(f"{r['role']}: {r['content']}" for r in rows))

            # Warm/cold archive
            if not results:
                arch_rows = await conn.fetch(
                    """SELECT tier, summary FROM memory_archive
                       WHERE summary ILIKE $1 ORDER BY tier LIMIT 3""",
                    f"%{query}%"
                )
                labels = {2: "WARM", 3: "COLD", 4: "ARCHIVE"}
                for a in arch_rows:
                    results.append(f"[{labels.get(a['tier'], 'ARCHIVE')} MEMORY]\n{a['summary']}")

    except Exception as e:
        print(f"search_all_tiers error: {e}")

    return "\n\n".join(results) if results else ""


async def get_memory_stats() -> dict:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            hot    = await conn.fetchval("SELECT COUNT(*) FROM memories") or 0
            arch   = await conn.fetchval("SELECT COUNT(*) FROM memory_archive") or 0
            devs   = await conn.fetchval("SELECT COUNT(*) FROM devices") or 0
            facts  = await conn.fetchval("SELECT COUNT(*) FROM facts") or 0
        return {"hot": hot, "archived": arch, "devices": devs, "facts": facts}
    except:
        return {"hot": 0, "archived": 0, "devices": 0, "facts": 0}


async def wipe_chats() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM memories")
        await conn.execute("DELETE FROM memory_archive")


async def wipe_all() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        for t in ["memories", "memory_archive", "reminders", "todos",
                  "notes", "rl_feedback", "announcements"]:
            await conn.execute(f"DELETE FROM {t}")


# ══════════════════════════════════════════════════════════
#  BACKGROUND SCHEDULER
# ══════════════════════════════════════════════════════════

async def compression_scheduler() -> None:
    """Runs weekly compression and daily session cleanup in the background."""
    while True:
        await asyncio.sleep(7 * 24 * 60 * 60)   # 7 days
        print("⏰  Running weekly memory compression...")
        await compress_old_messages()
        # Also clean expired sessions
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM sessions WHERE expires_at < NOW()"
                )
        except:
            pass

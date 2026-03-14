"""
JARVIS v3 Background Jobs
Runs daily and weekly maintenance tasks via APScheduler.
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler = None

def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    return _scheduler

def start_scheduler():
    s = get_scheduler()
    if s.running:
        return

    # Daily 2:00 AM IST
    s.add_job(job_memory_compression,  CronTrigger(hour=2,  minute=0),  id="memory_compression",  replace_existing=True)
    s.add_job(job_feedback_analysis,   CronTrigger(hour=2,  minute=30), id="feedback_analysis",   replace_existing=True)
    s.add_job(job_reminder_check,      CronTrigger(minute="*/5"),       id="reminder_check",      replace_existing=True)
    s.add_job(job_keep_alive,          CronTrigger(minute="*/14"),      id="keep_alive",          replace_existing=True)

    # Weekly Sunday 3:00 AM IST
    s.add_job(job_insight_extraction,  CronTrigger(day_of_week="sun", hour=3, minute=0),  id="insight_extraction",  replace_existing=True)
    s.add_job(job_db_cleanup,          CronTrigger(day_of_week="sun", hour=3, minute=30), id="db_cleanup",          replace_existing=True)
    s.add_job(job_birthday_check,      CronTrigger(hour=8, minute=0),                     id="birthday_check",      replace_existing=True)
    s.add_job(job_personality_update,  CronTrigger(day_of_week="sun", hour=4, minute=0),  id="personality_update",  replace_existing=True)

    s.start()
    print("✅  APScheduler started — background jobs active")

def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


# ── DAILY JOBS ──────────────────────────────────

async def job_memory_compression():
    """Compress old messages into warm memory summaries."""
    try:
        from backend.db.connection import get_pool
        from backend.services.memory_service import save_warm_summary
        from backend.config import config
        from groq import Groq

        groq = Groq(api_key=config.GROQ_API_KEY)
        pool = await get_pool()
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.MESSAGE_RETENTION_DAYS)

        async with pool.acquire() as conn:
            # Get all persons with old unarchived messages
            persons = await conn.fetch(
                """SELECT DISTINCT person FROM memories
                   WHERE archived=FALSE AND created_at < $1 AND person != ''""",
                cutoff
            )

            for p_row in persons:
                person = p_row["person"]
                # Get old messages for this person
                rows = await conn.fetch(
                    """SELECT role, content, device_id, created_at FROM memories
                       WHERE person=$1 AND archived=FALSE AND created_at < $2
                       ORDER BY created_at ASC LIMIT 100""",
                    person, cutoff
                )
                if len(rows) < 5:
                    continue

                device_id = rows[0]["device_id"]
                period_start = rows[0]["created_at"]
                period_end = rows[-1]["created_at"]

                # Build conversation text
                convo = "\n".join([f"{r['role'].upper()}: {r['content'][:200]}" for r in rows])

                # Summarize via Groq
                resp = groq.chat.completions.create(
                    model=config.MODEL_ANALYSIS,
                    messages=[{
                        "role": "user",
                        "content": f"Summarize this conversation with {person} in 3-4 key points. Focus on important facts, emotions, decisions made:\n\n{convo[:3000]}"
                    }],
                    max_tokens=300,
                    temperature=0.3,
                )
                summary = resp.choices[0].message.content.strip()

                # Save summary
                await save_warm_summary(person, device_id, summary, period_start, period_end, len(rows))

                # Mark messages as archived
                ids = [r for r in rows]
                await conn.execute(
                    """UPDATE memories SET archived=TRUE
                       WHERE person=$1 AND archived=FALSE AND created_at < $2""",
                    person, cutoff
                )

        print(f"✅  memory_compression job done — {datetime.now(timezone.utc).isoformat()}")

    except Exception as e:
        print(f"memory_compression error: {e}")
        from backend.services.memory_service import log_error
        await log_error("job_error", str(e), "memory_compression")


async def job_feedback_analysis():
    """Analyze RL feedback and update personality prompt additions."""
    try:
        from backend.db.connection import get_pool
        from backend.services.personality import update_personality_profile
        from backend.config import config
        from groq import Groq

        groq = Groq(api_key=config.GROQ_API_KEY)
        pool = await get_pool()

        async with pool.acquire() as conn:
            persons = await conn.fetch(
                "SELECT DISTINCT person FROM rl_feedback WHERE processed=FALSE"
            )

            for p_row in persons:
                person = p_row["person"]

                pos = await conn.fetch(
                    "SELECT jarvis_msg FROM rl_feedback WHERE person=$1 AND feedback='positive' AND processed=FALSE LIMIT 10",
                    person
                )
                neg = await conn.fetch(
                    "SELECT jarvis_msg FROM rl_feedback WHERE person=$1 AND feedback='negative' AND processed=FALSE LIMIT 10",
                    person
                )

                if not pos and not neg:
                    continue

                pos_samples = "\n".join([r["jarvis_msg"][:150] for r in pos])
                neg_samples = "\n".join([r["jarvis_msg"][:150] for r in neg])

                prompt = f"""Analyze these JARVIS responses for user {person}.

LIKED responses:
{pos_samples or 'none'}

DISLIKED responses:
{neg_samples or 'none'}

Write 1-2 sentences of instructions for JARVIS on how to better respond to {person}.
Be specific: mention tone, length, style. Start with "{person} prefers..."."""

                resp = groq.chat.completions.create(
                    model=config.MODEL_ANALYSIS,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    temperature=0.3,
                )
                prompt_addition = resp.choices[0].message.content.strip()

                await update_personality_profile(person, {
                    "feedback_analyzed": datetime.now(timezone.utc).isoformat()
                }, prompt_addition)

                # Mark as processed
                await conn.execute(
                    "UPDATE rl_feedback SET processed=TRUE WHERE person=$1", person
                )

        print(f"✅  feedback_analysis job done")

    except Exception as e:
        print(f"feedback_analysis error: {e}")
        from backend.services.memory_service import log_error
        await log_error("job_error", str(e), "feedback_analysis")


async def job_reminder_check():
    """Check due reminders and push to active WebSocket connections."""
    try:
        from backend.db.connection import get_pool
        from backend.api.websocket import get_active_connections

        pool = await get_pool()
        connections = get_active_connections()

        async with pool.acquire() as conn:
            for device_id, ws in list(connections.items()):
                try:
                    rows = await conn.fetch(
                        "SELECT id, text, remind_at FROM reminders WHERE device_id=$1 AND done=FALSE AND remind_at <= NOW()",
                        device_id
                    )
                    for row in rows:
                        import json as _json
                        await ws.send_text(_json.dumps({
                            "type": "reminder",
                            "text": f"⏰ Reminder: {row['text']}"
                        }))
                        await conn.execute("UPDATE reminders SET done=TRUE WHERE id=$1", row["id"])
                except Exception:
                    pass

    except Exception as e:
        print(f"reminder_check error: {e}")


async def job_keep_alive():
    """Ping self to prevent Render free tier sleep."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.get("https://cloud-jarvis-p6zu.onrender.com/health")
    except Exception:
        pass


# ── WEEKLY JOBS ─────────────────────────────────

async def job_insight_extraction():
    """Extract weekly insights per person using Groq."""
    try:
        from backend.db.connection import get_pool
        from backend.services.personality import save_insight
        from backend.config import config
        from groq import Groq

        groq = Groq(api_key=config.GROQ_API_KEY)
        pool = await get_pool()
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        async with pool.acquire() as conn:
            persons = await conn.fetch(
                "SELECT DISTINCT person FROM memories WHERE created_at > $1 AND person != ''",
                week_ago
            )
            for p_row in persons:
                person = p_row["person"]
                rows = await conn.fetch(
                    """SELECT role, content FROM memories
                       WHERE person=$1 AND created_at > $2 AND role='user'
                       ORDER BY created_at DESC LIMIT 30""",
                    person, week_ago
                )
                if len(rows) < 3:
                    continue

                msgs = "\n".join([r["content"][:100] for r in rows])
                resp = groq.chat.completions.create(
                    model=config.MODEL_ANALYSIS,
                    messages=[{
                        "role": "user",
                        "content": f"In one sentence, what is the most important thing {person} shared this week?\n\n{msgs}"
                    }],
                    max_tokens=80,
                    temperature=0.3,
                )
                insight = resp.choices[0].message.content.strip()
                await save_insight(person, insight)

        print(f"✅  insight_extraction job done")

    except Exception as e:
        print(f"insight_extraction error: {e}")


async def job_db_cleanup():
    """Delete archived messages older than retention period."""
    try:
        from backend.db.connection import get_pool
        from backend.config import config

        pool = await get_pool()
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.MESSAGE_RETENTION_DAYS + 7)

        async with pool.acquire() as conn:
            deleted = await conn.fetchval(
                "DELETE FROM memories WHERE archived=TRUE AND created_at < $1 RETURNING COUNT(*)",
                cutoff
            )
            # Clean old error logs
            await conn.execute(
                "DELETE FROM error_logs WHERE created_at < NOW() - INTERVAL '30 days'"
            )
            # Clean old processed feedback
            await conn.execute(
                "DELETE FROM rl_feedback WHERE processed=TRUE AND created_at < NOW() - INTERVAL '60 days'"
            )

        print(f"✅  db_cleanup job done")

    except Exception as e:
        print(f"db_cleanup error: {e}")


async def job_birthday_check():
    """Send birthday alerts for upcoming birthdays."""
    try:
        from backend.services.memory_service import get_upcoming_birthdays
        from backend.api.websocket import get_active_connections
        import json as _json

        upcoming = await get_upcoming_birthdays(days_ahead=3)
        if not upcoming:
            return

        connections = get_active_connections()
        for device_id, ws in list(connections.items()):
            try:
                for b in upcoming:
                    days = b["days_until"]
                    msg = f"🎂 {b['name']}'s birthday is {'today!' if days == 0 else f'in {days} day(s)!'}"
                    await ws.send_text(_json.dumps({
                        "type": "response",
                        "text": msg
                    }))
            except Exception:
                pass

    except Exception as e:
        print(f"birthday_check error: {e}")


async def job_personality_update():
    """Deep personality analysis for all active users."""
    try:
        from backend.db.connection import get_pool
        from backend.services.personality import analyze_and_update_personality

        pool = await get_pool()
        async with pool.acquire() as conn:
            persons = await conn.fetch(
                "SELECT DISTINCT person FROM memories WHERE created_at > NOW() - INTERVAL '7 days' AND person != ''"
            )
        for p_row in persons:
            await analyze_and_update_personality(p_row["person"], "")

        print(f"✅  personality_update job done")

    except Exception as e:
        print(f"personality_update error: {e}")

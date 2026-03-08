"""
J.A.R.V.I.S Cloud Edition v2 — Modular Production Build
Owner: Battini Lakshmi Narayana Goud (Lucky)
Architecture: FastAPI + asyncpg + Groq LLM + Supabase PostgreSQL
"""
import asyncio
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend import config
from backend.db.connection import init_pool, close_pool
from backend.api import auth, admin, todos, notes, reminders, birthdays, websocket, music

# ── Validate config before anything else ──────────────────
config.validate()

app = FastAPI(
    title="J.A.R.V.I.S",
    description="Battini Family Private AI Assistant",
    version="2.0.0",
    docs_url="/docs" if not config.IS_PRODUCTION else None,
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(todos.router)
app.include_router(notes.router)
app.include_router(reminders.router)
app.include_router(birthdays.router)
app.include_router(music.router)
app.include_router(websocket.router)

# ── Static Files ──────────────────────────────────────────
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")


# ── Health Check ──────────────────────────────────────────
@app.get("/health")
async def health():
    """Render uses this for uptime checks and zero-downtime deploys."""
    try:
        from backend.db.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status":      "ok" if db_status == "ok" else "degraded",
        "service":     "JARVIS",
        "version":     "2.0.0",
        "environment": config.ENVIRONMENT,
        "database":    db_status,
    }


# ── Serve Frontend ────────────────────────────────────────
@app.get("/")
async def serve_ui():
    index_path = os.path.join(_frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "J.A.R.V.I.S API is running. Frontend not found."}


# ── Startup / Shutdown ────────────────────────────────────
@app.on_event("startup")
async def startup():
    print("🚀  JARVIS starting up...")
    await init_pool()

    # Run migrations automatically
    try:
        from backend.db.connection import get_pool
        migrations_dir = os.path.join(os.path.dirname(__file__), "db", "migrations")
        pool = get_pool()
        for fname in sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql")):
            sql = open(os.path.join(migrations_dir, fname)).read()
            async with pool.acquire() as conn:
                await conn.execute(sql)
        print("✅  Migrations applied")
    except Exception as e:
        print(f"⚠️   Migration warning: {e}")

    # Auto-seed family users if table is empty
    try:
        from backend.db.seed import seed_users, seed_facts
        from backend.db.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE approved=TRUE")
        if count == 0:
            print("🌱  Seeding family users (first deploy)...")
            await seed_users()
            await seed_facts()
    except Exception as e:
        print(f"⚠️   Seed warning: {e}")

    # Background tasks
    asyncio.create_task(_keep_alive())
    asyncio.create_task(_compression_scheduler())
    print("✅  JARVIS is ready!")


@app.on_event("shutdown")
async def shutdown():
    await close_pool()
    print("👋  JARVIS shut down cleanly.")


# ── Background Tasks ──────────────────────────────────────
async def _keep_alive():
    """Ping self every 10 minutes to prevent Render free-tier cold starts."""
    await asyncio.sleep(60)
    url = config.RENDER_URL
    if not url:
        print("⚠️   RENDER_EXTERNAL_URL not set — keep-alive disabled.")
        return
    print(f"💓  Keep-alive started → {url}")
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as cl:
                await cl.get(url + "/health")
            print("💓  keep-alive ping OK")
        except Exception as e:
            print(f"💓  keep-alive ping failed: {e}")
        await asyncio.sleep(10 * 60)


async def _compression_scheduler():
    """Weekly memory compression."""
    while True:
        await asyncio.sleep(7 * 24 * 60 * 60)
        from backend.services.memory_service import compress_old_messages
        await compress_old_messages()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

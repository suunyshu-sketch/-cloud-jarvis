"""
JARVIS v3 — FastAPI Application Entry Point
"""
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router
from backend.api.admin import router as admin_router
from backend.api.websocket import router as ws_router
from backend.api.productivity import (
    todos_router, notes_router, reminders_router,
    birthdays_router, music_router
)
from backend.db.connection import get_pool, close_pool
from backend.jobs.scheduler import start_scheduler, stop_scheduler

app = FastAPI(
    title="JARVIS v3",
    description="Just A Rather Very Intelligent System — Battini Family AI Assistant",
    version="3.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from backend.services.memory_service import log_error
    try:
        await log_error("unhandled_exception", str(exc), str(request.url))
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."}
    )

# Routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(ws_router)
app.include_router(todos_router)
app.include_router(notes_router)
app.include_router(reminders_router)
app.include_router(birthdays_router)
app.include_router(music_router)

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "service": "jarvis-v3"}

# Startup
@app.on_event("startup")
async def startup():
    await get_pool()
    start_scheduler()
    print("✅  JARVIS v3 started")

# Shutdown
@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()
    await close_pool()

# Serve frontend static files
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")

    @app.get("/")
    async def serve_frontend():
        index = os.path.join(_frontend_dir, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return JSONResponse({"status": "JARVIS v3 API running"})

    @app.get("/{path:path}")
    async def catch_all(path: str):
        index = os.path.join(_frontend_dir, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return JSONResponse({"error": "Not found"}, status_code=404)

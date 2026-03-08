"""
backend/api/memory.py
──────────────────────
Memory management endpoints — all admin-guarded.
"""
from fastapi import APIRouter, Depends
from groq import Groq

from backend.config import GROQ_API_KEY
from backend.middleware.auth_guard import require_admin, require_auth
from backend.services.memory_service import (
    get_all_facts, get_all_devices, get_memory_stats,
    compress_old_messages, wipe_chats, wipe_all,
)

router = APIRouter(tags=["memory"])
_groq  = Groq(api_key=GROQ_API_KEY)


@router.get("/memory")
async def memory(user: dict = Depends(require_admin)):
    stats   = await get_memory_stats()
    facts   = await get_all_facts()
    devices = await get_all_devices()
    return {"facts": facts, "devices": devices, "stats": stats}


@router.post("/compress")
async def force_compress(user: dict = Depends(require_admin)):
    count = await compress_old_messages(_groq)
    return {"status": "done", "compressed": count}


@router.delete("/memory/chats")
async def wipe_chats_route(user: dict = Depends(require_admin)):
    await wipe_chats()
    return {"status": "Chats wiped. Facts and devices preserved."}


@router.delete("/memory/all")
async def wipe_all_route(user: dict = Depends(require_admin)):
    await wipe_all()
    return {"status": "Full reset done. Family facts and devices preserved."}

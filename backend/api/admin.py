"""
JARVIS — Admin API Routes
All routes protected by require_admin.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.middleware.auth_guard import require_admin
from backend.services import auth_service, memory_service

router = APIRouter(prefix="/admin", tags=["admin"])


class ApproveBody(BaseModel):
    username: str


class ChangePasswordBody(BaseModel):
    username: str
    new_password: str


class AnnouncementBody(BaseModel):
    title: str = "Family Announcement"
    content: str


@router.get("/pending")
async def pending_users(admin=Depends(require_admin)):
    return {"pending": await auth_service.list_pending()}


@router.post("/approve")
async def approve_user(body: ApproveBody, admin=Depends(require_admin)):
    ok = await auth_service.approve_user(body.username)
    return {"success": ok}


@router.post("/change-password")
async def change_password(body: ChangePasswordBody, admin=Depends(require_admin)):
    if len(body.new_password) < 6:
        return {"success": False, "error": "Password too short (min 6 characters)"}
    ok = await auth_service.change_password(body.username, body.new_password)
    return {"success": ok}


@router.post("/announcement")
async def post_announcement(body: AnnouncementBody, admin=Depends(require_admin)):
    await memory_service.save_announcement(
        body.title, body.content, admin.get("display_name", "Lucky")
    )
    return {"success": True}


@router.get("/memory")
async def memory_overview(admin=Depends(require_admin)):
    stats   = await memory_service.get_memory_stats()
    facts   = await memory_service.get_all_facts()
    devices = await memory_service.get_all_devices()
    return {"stats": stats, "facts": facts, "devices": devices}


@router.post("/memory/compress")
async def compress(admin=Depends(require_admin)):
    await memory_service.compress_old_messages()
    return {"status": "Compression complete."}


@router.delete("/memory/chats")
async def wipe_chats(admin=Depends(require_admin)):
    await memory_service.wipe_chats()
    return {"status": "Chat history wiped. Facts and family data preserved."}


@router.delete("/memory/all")
async def wipe_all(admin=Depends(require_admin)):
    await memory_service.wipe_all()
    return {"status": "Full reset done. Family facts and devices preserved."}


@router.get("/users")
async def all_users(admin=Depends(require_admin)):
    return {"users": await auth_service.list_all_users()}


@router.get("/announcements")
async def get_announcements(admin=Depends(require_admin)):
    return {"announcements": await memory_service.get_announcements(active_only=False)}

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.middleware.auth_guard import require_admin
from backend.services import auth_service, memory_service

router = APIRouter(prefix="/admin", tags=["admin"])

class BroadcastRequest(BaseModel):
    message: str

class ApproveRequest(BaseModel):
    username: str

class PasswordRequest(BaseModel):
    username: str
    new_password: str

@router.get("/users")
async def list_users(admin: str = Depends(require_admin)):
    return await auth_service.list_all_users()

@router.post("/approve")
async def approve_user(req: ApproveRequest, admin: str = Depends(require_admin)):
    ok = await auth_service.approve_user(req.username)
    return {"success": ok}

@router.post("/broadcast")
async def broadcast(req: BroadcastRequest, admin: str = Depends(require_admin)):
    await memory_service.save_announcement("Family Broadcast", req.message, admin)
    return {"message": "Broadcast sent"}

@router.get("/stats")
async def get_stats(admin: str = Depends(require_admin)):
    return await memory_service.get_memory_stats()

@router.get("/facts")
async def get_facts(admin: str = Depends(require_admin)):
    return await memory_service.get_all_facts()

@router.get("/devices")
async def get_devices(admin: str = Depends(require_admin)):
    return await memory_service.get_all_devices()

@router.post("/change-password")
async def admin_change_password(req: PasswordRequest, admin: str = Depends(require_admin)):
    ok = await auth_service.change_password(req.username, req.new_password)
    return {"success": ok}

@router.post("/wipe-chats")
async def wipe_chats(admin: str = Depends(require_admin)):
    await memory_service.wipe_chats()
    return {"message": "Chat history wiped"}

@router.post("/wipe-all")
async def wipe_all(admin: str = Depends(require_admin)):
    await memory_service.wipe_all()
    return {"message": "All data wiped"}

@router.get("/pending")
async def get_pending(admin: str = Depends(require_admin)):
    from backend.db.connection import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT username, display_name, created_at FROM j_users WHERE approved=FALSE")
        return [dict(r) for r in rows]

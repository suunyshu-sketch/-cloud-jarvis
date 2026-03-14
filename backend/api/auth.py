from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.services import auth_service
from backend.middleware.auth_guard import require_auth

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: str = ""

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""

class ChangePasswordRequest(BaseModel):
    new_password: str

@router.post("/login")
async def login(req: LoginRequest):
    token = await auth_service.login(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if req.device_id:
        await auth_service.save_session(token, req.username, req.device_id)
    from backend.services.memory_service import save_device
    await save_device(req.device_id or req.username, req.username)
    return {"token": token, "username": req.username}

@router.post("/register")
async def register(req: RegisterRequest):
    ok = await auth_service.register(req.username, req.password, req.display_name)
    if not ok:
        raise HTTPException(status_code=400, detail="Username already taken")
    return {"message": "Registration successful. Waiting for admin approval."}

@router.get("/verify")
async def verify(username: str = Depends(require_auth)):
    return {"username": username, "valid": True}

@router.post("/logout")
async def logout(authorization: str = "", username: str = Depends(require_auth)):
    from fastapi import Header
    return {"message": "Logged out"}

@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, username: str = Depends(require_auth)):
    ok = await auth_service.change_password(username, req.new_password)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to change password")
    return {"message": "Password changed successfully"}

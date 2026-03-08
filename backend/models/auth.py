"""
JARVIS — Pydantic Models for Auth
"""
from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    username:   str = Field(..., min_length=1, max_length=50)
    password:   str = Field(..., min_length=1, max_length=128)
    device_id:  str = Field(default="unknown", max_length=100)
    user_agent: str = Field(default="", max_length=300)


class RegisterRequest(BaseModel):
    username:     str = Field(..., min_length=2, max_length=50)
    password:     str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=80)
    relation:     str = Field(default="guest", max_length=30)
    knows_member: str = Field(default="", max_length=80)


class VerifyRequest(BaseModel):
    token:     str = Field(..., min_length=1)
    device_id: str = Field(default="unknown")


class TokenResponse(BaseModel):
    success:      bool
    token:        Optional[str] = None
    username:     Optional[str] = None
    display_name: Optional[str] = None
    role:         Optional[str] = None
    family_member: Optional[str] = None
    error:        Optional[str] = None


class VerifyResponse(BaseModel):
    valid: bool
    user:  Optional[dict] = None

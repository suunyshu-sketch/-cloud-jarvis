"""
JARVIS — Pydantic Models for Messages & Data
"""
from pydantic import BaseModel, Field
from typing import Optional


class WSMessage(BaseModel):
    type:         str = "message"
    text:         str = ""
    device_id:    str = "unknown"
    device_name:  str = "Unknown"
    device_owner: str = ""
    user_agent:   str = ""
    image:        Optional[str] = None   # base64
    private:      bool = False
    # Feedback fields
    user_msg:        str = ""
    jarvis_response: str = ""
    feedback:        str = "positive"
    topic:           str = "general"


class TodoCreate(BaseModel):
    text:      str = Field(..., min_length=1, max_length=500)
    device_id: str = Field(..., max_length=100)
    person:    str = Field(default="", max_length=80)
    category:  str = Field(default="general", max_length=30)


class NoteCreate(BaseModel):
    title:     str = Field(..., max_length=120)
    content:   str = Field(..., min_length=1, max_length=5000)
    device_id: str = Field(..., max_length=100)
    person:    str = Field(default="", max_length=80)


class ReminderCreate(BaseModel):
    text:      str = Field(..., min_length=1, max_length=500)
    remind_at: str = Field(...)    # ISO datetime string
    device_id: str = Field(..., max_length=100)
    person:    str = Field(default="", max_length=80)


class AnnouncementCreate(BaseModel):
    title:   str = Field(..., max_length=120)
    content: str = Field(..., min_length=1, max_length=2000)

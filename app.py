"""
J.A.R.V.I.S  —  app.py
FastAPI entry point. Only routes live here.
DB logic  → db.py
AI logic  → ai.py
Config    → config.py
Frontend  → index.html
"""

import os, json, asyncio, base64, httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="JARVIS")

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    from db import init_db, seed_family
    try:
        init_db()
        seed_family()
    except Exception as e:
        print(f"⚠️ DB startup error: {e}")
    asyncio.create_task(_keep_alive())
    print("✅ JARVIS online")

async def _keep_alive():
    """Ping self every 10 min — prevents Render free tier cold start"""
    await asyncio.sleep(60)
    url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not url:
        return
    print(f"💓 Keep-alive → {url}")
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as cl:
                await cl.get(url)
        except: pass
        await asyncio.sleep(600)

# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/")
async def serve_ui():
    return FileResponse("index.html")

# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/auth/login")
async def login(request: Request):
    try:
        from db import auth_login
        d = await request.json()
        return auth_login(d.get("username",""), d.get("password",""), d.get("device_id","unknown"))
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/auth/register")
async def register(request: Request):
    try:
        from db import auth_register_guest
        d = await request.json()
        return auth_register_guest(d.get("username",""), d.get("password",""),
                                    d.get("display_name",""), d.get("relation","guest"),
                                    d.get("knows_member",""))
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/auth/verify")
async def verify(request: Request):
    try:
        from db import auth_verify
        d = await request.json()
        user = auth_verify(d.get("token",""))
        return {"valid": user is not None, "user": user}
    except:
        return {"valid": False, "user": None}

@app.get("/auth/status")
async def auth_status():
    try:
        from db import get_all_users
        return {"users": get_all_users()}
    except Exception as e:
        return {"error": str(e)}

# ── Admin endpoints ───────────────────────────────────────────────────────────
@app.get("/admin/pending")
async def pending():
    from db import admin_pending
    return {"pending": admin_pending()}

@app.post("/admin/approve")
async def approve(request: Request):
    from db import admin_approve
    d = await request.json()
    return {"success": admin_approve(d.get("username",""))}

@app.get("/admin/users")
async def all_users():
    from db import get_all_users, get_all_devices, get_facts
    return {"users": get_all_users(), "devices": get_all_devices(), "facts": get_facts(50)}

@app.post("/admin/wipe")
async def wipe(request: Request):
    from db import wipe_chat
    d = await request.json()
    wipe_chat(d.get("device_id"))
    return {"success": True}

@app.post("/admin/broadcast")
async def broadcast(request: Request):
    from db import save_announcement
    d = await request.json()
    save_announcement(d.get("title","Announcement"), d.get("content",""), "Lucky")
    return {"success": True}

# ── Feedback ──────────────────────────────────────────────────────────────────
@app.post("/feedback")
async def feedback(request: Request):
    from db import save_feedback
    d = await request.json()
    save_feedback(d.get("person","unknown"), d.get("device_id","unknown"),
                  d.get("user_msg",""), d.get("jarvis_msg",""), d.get("feedback",""))
    return {"success": True}

# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_handler(ws: WebSocket):
    await ws.accept()
    device_id = "unknown"
    person = "Unknown"
    family_data = None
    is_admin = False
    last_user_msg = ""
    last_jarvis_msg = ""

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "message")

            # ── Ping ──────────────────────────────────────────────────────────
            if msg_type == "ping":
                from db import touch_device
                if device_id != "unknown": touch_device(device_id)
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            # ── Identify ──────────────────────────────────────────────────────
            if msg_type == "identify":
                device_id   = data.get("device_id", "unknown")
                device_name = data.get("device_name", "Unknown Device")
                owner       = data.get("owner", "Unknown")
                from db import save_device, get_due_reminders
                from ai import resolve_person
                save_device(device_id, device_name, owner)
                person, family_data = resolve_person(owner)
                is_admin = (family_data or {}).get("role") == "admin"
                # Check due reminders
                due = get_due_reminders(device_id)
                for r in due:
                    await ws.send_text(json.dumps({"type": "reminder", "text": r["text"]}))
                continue

            # ── Feedback ──────────────────────────────────────────────────────
            if msg_type == "feedback":
                from db import save_feedback
                save_feedback(person, device_id, last_user_msg, last_jarvis_msg, data.get("feedback",""))
                await ws.send_text(json.dumps({"type": "feedback_ack"}))
                continue

            # ── Message ───────────────────────────────────────────────────────
            if msg_type == "message":
                text     = data.get("text", "").strip()
                image_b64 = data.get("image")
                if not text and not image_b64:
                    continue

                last_user_msg = text

                # Handle built-in commands
                cmd_reply = _handle_command(text, person, is_admin, device_id)
                if cmd_reply is not None:
                    await ws.send_text(json.dumps({"type": "chunk", "text": cmd_reply}))
                    await ws.send_text(json.dumps({"type": "stream_end"}))
                    last_jarvis_msg = cmd_reply
                    continue

                # Save user message
                from db import save_message
                private = data.get("private", False)
                save_message("user", text or "image", device_id, private)

                # AI response (streaming)
                from ai import jarvis_respond
                reply = await jarvis_respond(
                    user_text=text, device_id=device_id, person=person,
                    family_data=family_data, is_admin=is_admin,
                    image_b64=image_b64, ws=ws
                )
                last_jarvis_msg = reply
                save_message("assistant", reply, device_id, private)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS error: {e}")
        try:
            await ws.send_text(json.dumps({"type": "chunk", "text": f"System error: {e}"}))
            await ws.send_text(json.dumps({"type": "stream_end"}))
        except: pass

# ── Built-in commands ─────────────────────────────────────────────────────────
def _handle_command(text: str, person: str, is_admin: bool, device_id: str) -> str | None:
    """Returns reply string if command matched, else None. Add commands here."""
    lower = text.lower().strip()

    # Reminders
    if lower.startswith("remind me") or "set a reminder" in lower:
        from db import save_reminder
        import re
        m = re.search(r"remind me (?:to )?(.+?) (?:at|in) (.+)", lower)
        if m:
            what, when = m.group(1), m.group(2)
            # Simple time parser
            from datetime import datetime, timedelta
            remind_at = (datetime.now() + timedelta(hours=1)).isoformat()
            if "hour" in when:
                hrs = int(re.search(r"\d+", when).group() or 1)
                remind_at = (datetime.now() + timedelta(hours=hrs)).isoformat()
            elif "minute" in when or "min" in when:
                mins = int(re.search(r"\d+", when).group() or 30)
                remind_at = (datetime.now() + timedelta(minutes=mins)).isoformat()
            save_reminder(person, device_id, what, remind_at)
            return f"✅ Reminder set: '{what}' at {when}."

    # Todos
    if lower.startswith("add todo") or lower.startswith("todo:"):
        from db import save_todo
        todo_text = text.replace("add todo", "").replace("todo:", "").strip()
        if todo_text:
            save_todo(person, device_id, todo_text)
            return f"✅ Added to your list: '{todo_text}'"

    # Private mode toggle
    if lower in ["private mode on", "go private", "private"]:
        return "🔒 Private mode ON. This conversation won't be saved."
    if lower in ["private mode off", "exit private", "public"]:
        return "🔓 Private mode OFF. Saving conversations normally."

    return None

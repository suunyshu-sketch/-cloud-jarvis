"""
JARVIS — WebSocket Handler (/ws)
Thin layer — all logic delegated to services.
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services import memory_service, ai_engine
from backend.utils.text import detect_device_name

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    connected_device_id = None

    try:
        while True:
            raw  = await ws.receive_text()
            data = json.loads(raw)

            msg_type     = data.get("type", "message")
            text         = (data.get("text") or "").strip()
            device_id    = data.get("device_id", "unknown")
            device_name  = data.get("device_name", "Unknown")
            device_owner = data.get("device_owner", "")
            user_agent   = data.get("user_agent", "")
            image_b64    = data.get("image")
            private      = data.get("private", False)

            # Auto-detect device name from user agent if not provided
            if device_name == "Unknown" and user_agent:
                device_name = detect_device_name(user_agent)

            # Track first connection
            if connected_device_id is None and device_id != "unknown":
                connected_device_id = device_id
                await memory_service.touch_device(device_id)

            # ── Ping/Pong ──
            if msg_type == "ping":
                if device_id != "unknown":
                    await memory_service.touch_device(device_id)
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            # ── Feedback ──
            if msg_type == "feedback":
                await memory_service.save_feedback(
                    device_owner or "unknown", device_id,
                    data.get("user_msg", ""), data.get("jarvis_response", ""),
                    data.get("feedback", "positive"), data.get("topic", "general")
                )
                await ws.send_text(json.dumps({"type": "feedback_ack"}))
                continue

            # Skip empty messages
            if not text and not image_b64:
                continue

            # Register device
            if device_id != "unknown":
                await memory_service.save_device(device_id, device_name, device_owner, user_agent)

            # Check due reminders
            due_reminders = await memory_service.get_due_reminders(device_id)
            for r in due_reminders:
                await ws.send_text(json.dumps({"type": "reminder", "text": r["text"]}))

            # Save user message
            if text:
                await memory_service.save_message("user", text, device_id, private)

            # Generate and stream response
            try:
                reply = await ai_engine.jarvis_respond(
                    user_text=text,
                    device_id=device_id,
                    image_b64=image_b64,
                    ws=ws,
                    device_owner=device_owner,
                    private=private,
                )
            except Exception as e:
                reply = f"System error: {type(e).__name__}. Please try again."
                await ws.send_text(json.dumps({"type": "response", "text": reply}))

            # Save JARVIS reply
            await memory_service.save_message("assistant", reply, device_id, private)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")

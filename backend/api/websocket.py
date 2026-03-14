import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services import auth_service, memory_service
from backend.services.ai_engine import handle_message

router = APIRouter(tags=["websocket"])

# Active connections: device_id -> WebSocket
_active: dict = {}

def get_active_connections() -> dict:
    return _active

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await websocket.accept()

    username = await auth_service.verify_session(token)
    if not username:
        await websocket.send_text(json.dumps({"type": "error", "text": "Unauthorized"}))
        await websocket.close()
        return

    device_id = f"{username}_{id(websocket)}"
    _active[device_id] = websocket

    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "username": username,
            "device_id": device_id
        }))

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                continue

            msg_type = msg.get("type", "message")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if msg_type == "feedback":
                await memory_service.save_feedback(
                    username,
                    msg.get("user_msg", ""),
                    msg.get("jarvis_msg", ""),
                    msg.get("feedback", "positive"),
                    "user"
                )
                continue

            if msg_type == "message":
                user_text  = msg.get("text", "").strip()
                image_b64  = msg.get("image")
                private    = msg.get("private", False)

                if not user_text and not image_b64:
                    continue

                await handle_message(
                    user_text=user_text,
                    device_id=device_id,
                    device_owner=username,
                    ws=websocket,
                    image_b64=image_b64,
                    private=private,
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"websocket error: {e}")
    finally:
        _active.pop(device_id, None)

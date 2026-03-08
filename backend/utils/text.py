"""
JARVIS — Text Utility Functions
Pure helpers: escaping, formatting, time display.
"""
import html
import re
from datetime import datetime, timezone


def esc_html(text: str) -> str:
    return html.escape(str(text))


def clean_text(text: str) -> str:
    """Strip extra whitespace and control characters."""
    return re.sub(r'\s+', ' ', text.strip())


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def time_since(ts) -> str:
    """Human-readable relative time: '5m ago', '2h ago', etc."""
    if not ts:
        return "never"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return "unknown"
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    diff = int((now - ts).total_seconds())
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def get_device_icon(name: str) -> str:
    n = (name or "").lower()
    if any(x in n for x in ["samsung", "android", "pixel"]):
        return "📱"
    if any(x in n for x in ["iphone", "ios"]):
        return "📱"
    if any(x in n for x in ["ipad", "tablet"]):
        return "📟"
    if any(x in n for x in ["windows", "pc", "laptop"]):
        return "💻"
    if "mac" in n:
        return "💻"
    return "📡"


def detect_device_name(user_agent: str = "") -> str:
    ua = user_agent.lower()
    if "samsung" in ua:
        return "Samsung Phone"
    if "iphone" in ua:
        return "iPhone"
    if "android" in ua:
        return "Android Phone"
    if "windows" in ua:
        return "Windows PC"
    if "mac" in ua:
        return "Mac"
    if "ipad" in ua:
        return "iPad"
    return "Browser"

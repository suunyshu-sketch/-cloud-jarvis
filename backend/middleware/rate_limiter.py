"""
JARVIS — Sliding Window Rate Limiter
In-memory rate limiter (no Redis needed for this scale).
Limits login attempts per IP to prevent brute force.
"""
import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from backend import config


class SlidingWindowLimiter:
    """
    Tracks requests per key in a sliding time window.
    Thread-safe for single-process async use.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests    = max_requests
        self.window_seconds  = window_seconds
        self._timestamps: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        dq = self._timestamps[key]

        # Remove timestamps outside the window
        while dq and dq[0] < window_start:
            dq.popleft()

        if len(dq) >= self.max_requests:
            return False

        dq.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        dq = self._timestamps[key]
        while dq and dq[0] < window_start:
            dq.popleft()
        return max(0, self.max_requests - len(dq))

    def reset(self, key: str) -> None:
        self._timestamps.pop(key, None)


# ── Shared limiter instances ──────────────────────────────
login_limiter = SlidingWindowLimiter(
    max_requests=config.MAX_LOGIN_ATTEMPTS,
    window_seconds=config.RATE_LIMIT_WINDOW
)

register_limiter = SlidingWindowLimiter(
    max_requests=5,
    window_seconds=300   # 5 registrations per 5 minutes per IP
)

ws_limiter = SlidingWindowLimiter(
    max_requests=120,
    window_seconds=60    # 120 WS messages per minute per device
)


def get_client_ip(request: Request) -> str:
    """Extract real IP — handles Render/Cloudflare proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_login_rate(request: Request) -> None:
    """Call at the start of the login endpoint. Raises 429 if exceeded."""
    ip = get_client_ip(request)
    if not login_limiter.is_allowed(ip):
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please wait {config.RATE_LIMIT_WINDOW} seconds."
        )


def check_register_rate(request: Request) -> None:
    ip = get_client_ip(request)
    if not register_limiter.is_allowed(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many registration requests. Please wait 5 minutes."
        )

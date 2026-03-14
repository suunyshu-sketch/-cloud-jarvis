from collections import defaultdict
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from backend.config import config

_request_counts: dict = defaultdict(list)

async def rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).timestamp()
    window = 60

    _request_counts[client_ip] = [t for t in _request_counts[client_ip] if now - t < window]
    _request_counts[client_ip].append(now)

    if len(_request_counts[client_ip]) > config.MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

import asyncpg
import ssl
import os
from urllib.parse import urlparse
from backend.config import config

_pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await _create_pool()
    return _pool

async def _create_pool() -> asyncpg.Pool:
    url = config.DATABASE_URL
    if not url:
        raise ValueError("DATABASE_URL not set")

    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 6543
    database = parsed.path.lstrip("/").split("?")[0]
    user = parsed.username
    password = parsed.password

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    pool = await asyncpg.create_pool(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        ssl=ssl_ctx,
        min_size=3,
        max_size=10,
        command_timeout=30,
        statement_cache_size=0,
        server_settings={"application_name": "jarvis-v3"},
    )
    return pool

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

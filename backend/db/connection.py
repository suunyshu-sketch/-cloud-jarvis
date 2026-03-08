"""
JARVIS — Async Database Connection Pool (asyncpg)
Single shared pool. Never create per-request connections.
"""
import asyncpg
import re
import ssl
from typing import Optional
from backend import config

_pool: Optional[asyncpg.Pool] = None


def _parse_db_url(url: str) -> dict:
    """
    Robust DATABASE_URL parser.
    Handles Supabase direct + pooler URLs, auto-converts direct → pooler
    for Render free tier (which blocks port 5432).
    """
    url = url.strip()
    for scheme in ("postgresql://", "postgres://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break

    at = url.rfind("@")
    credentials = url[:at]
    rest = url[at + 1:]

    colon = credentials.find(":")
    user = credentials[:colon]
    password = credentials[colon + 1:]

    slash = rest.find("/")
    hostport = rest[:slash]
    dbname = rest[slash + 1:].split("?")[0]

    if ":" in hostport:
        host, port_str = hostport.rsplit(":", 1)
        port = int(port_str)
    else:
        host, port = hostport, 5432

    # Auto-convert Supabase direct URL → pooler URL (required on Render free tier)
    if ".supabase.co" in host and "pooler" not in host:
        m = re.search(r"(?:db\.)?([a-z0-9]+)\.supabase\.co", host)
        if m:
            ref = m.group(1)
            host = "aws-0-ap-south-1.pooler.supabase.com"
            if "." not in user:
                user = f"postgres.{ref}"
            port = 6543
            print(f"⚡  Auto-converted to Supabase pooler: {host}:{port}")

    if "pooler.supabase.com" in host and port == 5432:
        port = 6543

    return dict(host=host, port=port, database=dbname, user=user, password=password)


async def init_pool() -> None:
    """Create the connection pool. Called once during app startup."""
    global _pool
    params = _parse_db_url(config.DATABASE_URL)

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    _pool = await asyncpg.create_pool(
        host=params["host"],
        port=params["port"],
        database=params["database"],
        user=params["user"],
        password=params["password"],
        ssl=ssl_ctx,
        min_size=2,
        max_size=10,
        command_timeout=30,
        statement_cache_size=0,
        server_settings={"application_name": "jarvis"},
    )
    print(f"✅  DB pool ready — {params['host']}:{params['port']} db={params['database']}")


async def close_pool() -> None:
    """Gracefully close the pool during shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        print("🔌  DB pool closed")


def get_pool() -> asyncpg.Pool:
    """Return the active pool — raises if not initialised."""
    if _pool is None:
        raise RuntimeError("DB pool not initialised. Call init_pool() first.")
    return _pool

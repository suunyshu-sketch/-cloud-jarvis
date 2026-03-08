"""
JARVIS — Authentication Service
bcrypt password hashing, JWT token issue/verify, session management.
"""
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt

from backend import config
from backend.db.connection import get_pool


# ── Password Hashing ──────────────────────────────────────

def hash_password(password: str) -> str:
    """bcrypt hash with cost factor 12."""
    return bcrypt.hashpw(password.strip().encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.strip().encode(), hashed.encode())
    except Exception:
        return False


# ── JWT Tokens ───────────────────────────────────────────

def issue_token(username: str, device_id: str = "unknown") -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=config.JWT_EXPIRE_DAYS)
    payload = {
        "sub": username,
        "did": device_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Returns payload dict or None if invalid/expired."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── Login ────────────────────────────────────────────────

async def login(username: str, password: str, device_id: str) -> dict:
    """
    Verify credentials. Returns success dict or error dict.
    Never exposes which field was wrong to prevent enumeration.
    """
    try:
        pool = get_pool()
        uname = username.strip().lower()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT username, password_hash, display_name, role, "
                "family_member, approved, login_count "
                "FROM users WHERE username=$1",
                uname
            )

        if not row:
            return {"success": False, "error": "Invalid username or password."}

        if not verify_password(password, row["password_hash"]):
            return {"success": False, "error": "Invalid username or password."}

        if not row["approved"]:
            return {
                "success": False,
                "error": "Your account is pending approval from Lucky. Please wait."
            }

        # Issue token & update stats
        token = issue_token(uname, device_id)
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login=$1, login_count=$2 WHERE username=$3",
                now, (row["login_count"] or 0) + 1, uname
            )
            await conn.execute(
                """INSERT INTO sessions (token, username, device_id, created_at, expires_at, last_seen)
                   VALUES ($1, $2, $3, $4, $5, $4)
                   ON CONFLICT (token) DO NOTHING""",
                token, uname, device_id, now,
                now + timedelta(days=config.JWT_EXPIRE_DAYS)
            )

        return {
            "success":       True,
            "token":         token,
            "username":      row["username"],
            "display_name":  row["display_name"],
            "role":          row["role"],
            "family_member": row["family_member"],
        }

    except Exception as e:
        print(f"❌  auth login error: {e}")
        return {"success": False, "error": "Server error. Please try again."}


# ── Registration ─────────────────────────────────────────

async def register_guest(
    username: str, password: str, display_name: str,
    relation: str = "guest", knows_member: str = ""
) -> dict:
    """Register a new pending user."""
    try:
        pool = get_pool()
        uname = username.strip().lower()

        if len(password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters."}
        if not re.match(r'^[a-z0-9_]{2,50}$', uname):
            return {"success": False, "error": "Username may only contain letters, numbers, underscores (2-50 chars)."}

        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT username FROM users WHERE username=$1", uname
            )
            if existing:
                return {"success": False, "error": "Username already taken. Choose another."}

            await conn.execute(
                """INSERT INTO users
                   (username, password_hash, display_name, role, approved,
                    relation, knows_member, created_at)
                   VALUES ($1,$2,$3,'guest',FALSE,$4,$5,$6)""",
                uname, hash_password(password), display_name.strip(),
                relation, knows_member.strip(),
                datetime.now(timezone.utc)
            )

        return {
            "success": True,
            "message": f"Request sent! Lucky will review and approve your access soon."
        }

    except Exception as e:
        print(f"❌  register error: {e}")
        return {"success": False, "error": "Server error. Please try again."}


# ── Verify Token ─────────────────────────────────────────

async def verify_token(token: str, device_id: str = "unknown") -> Optional[dict]:
    """
    Validates JWT + checks session still exists.
    Returns user dict or None.
    """
    payload = decode_token(token)
    if not payload:
        return None

    username = payload.get("sub")
    if not username:
        return None

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Check session is still valid
            session = await conn.fetchrow(
                "SELECT token FROM sessions WHERE token=$1 AND expires_at > NOW()",
                token
            )
            if not session:
                return None

            user = await conn.fetchrow(
                "SELECT username, display_name, role, family_member, approved "
                "FROM users WHERE username=$1 AND approved=TRUE",
                username
            )
            if not user:
                return None

            # Touch session last_seen
            await conn.execute(
                "UPDATE sessions SET last_seen=NOW() WHERE token=$1", token
            )

        return {
            "username":      user["username"],
            "display_name":  user["display_name"],
            "role":          user["role"],
            "family_member": user["family_member"],
        }

    except Exception as e:
        print(f"❌  verify_token error: {e}")
        return None


# ── Admin Helpers ────────────────────────────────────────

async def list_pending() -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT username, display_name, role, relation, knows_member, created_at "
                "FROM users WHERE approved=FALSE ORDER BY created_at"
            )
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"list_pending error: {e}")
        return []


async def approve_user(username: str) -> bool:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET approved=TRUE WHERE username=$1",
                username.strip().lower()
            )
        return True
    except Exception as e:
        print(f"approve_user error: {e}")
        return False


async def change_password(username: str, new_password: str) -> bool:
    if len(new_password) < 6:
        return False
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET password_hash=$1 WHERE username=$2",
                hash_password(new_password), username.strip().lower()
            )
        return True
    except Exception as e:
        print(f"change_password error: {e}")
        return False


async def list_all_users() -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT username, display_name, role, approved, last_login, login_count "
                "FROM users ORDER BY username"
            )
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"list_all_users error: {e}")
        return []


# ── Import fix ────────────────────────────────────────────
import re

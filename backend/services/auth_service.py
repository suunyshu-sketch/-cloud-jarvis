import bcrypt
import jwt
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from backend.config import config
from backend.db.connection import get_pool

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=config.JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def login(username: str, password: str) -> Optional[str]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT username, password_hash, approved FROM j_users WHERE username=$1", username
            )
            if not row:
                return None
            if not row["approved"]:
                return None
            if not verify_password(password, row["password_hash"]):
                return None
            await conn.execute(
                "UPDATE j_users SET last_login=NOW(), login_count=login_count+1 WHERE username=$1", username
            )
            return create_token(username)
    except Exception as e:
        print(f"login error: {e}")
        return None

async def register(username: str, password: str, display_name: str = "") -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT username FROM j_users WHERE username=$1", username)
            if exists:
                return False
            hashed = hash_password(password)
            await conn.execute(
                "INSERT INTO j_users (username, password_hash, display_name, role, approved) VALUES ($1,$2,$3,'guest',FALSE)",
                username, hashed, display_name or username
            )
            return True
    except Exception as e:
        print(f"register error: {e}")
        return False

async def save_session(token: str, username: str, device_id: str = "") -> None:
    try:
        pool = await get_pool()
        exp = datetime.now(timezone.utc) + timedelta(days=config.JWT_EXPIRE_DAYS)
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO j_sessions (token, username, device_id, expires_at, last_seen)
                   VALUES ($1,$2,$3,$4,NOW())
                   ON CONFLICT (token) DO UPDATE SET last_seen=NOW()""",
                token, username, device_id, exp
            )
    except Exception as e:
        print(f"save_session error: {e}")

async def verify_session(token: str) -> Optional[str]:
    try:
        username = decode_token(token)
        if not username:
            return None
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT token FROM j_sessions WHERE token=$1 AND expires_at > NOW()", token
            )
            if not row:
                return None
            await conn.execute("UPDATE j_sessions SET last_seen=NOW() WHERE token=$1", token)
            approved = await conn.fetchval(
                "SELECT approved FROM j_users WHERE username=$1 AND approved=TRUE", username
            )
            return username if approved else None
    except Exception as e:
        print(f"verify_session error: {e}")
        return None

async def logout(token: str) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM j_sessions WHERE token=$1", token)
    except Exception as e:
        print(f"logout error: {e}")

async def list_all_users() -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT username, display_name, role, approved, login_count, last_login FROM j_users ORDER BY username"
            )
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"list_all_users error: {e}")
        return []

async def approve_user(username: str) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE j_users SET approved=TRUE WHERE username=$1", username)
            return True
    except Exception as e:
        print(f"approve_user error: {e}")
        return False

async def change_password(username: str, new_password: str) -> bool:
    try:
        pool = await get_pool()
        hashed = hash_password(new_password)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE j_users SET password_hash=$1 WHERE username=$2", hashed, username)
            return True
    except Exception as e:
        print(f"change_password error: {e}")
        return False

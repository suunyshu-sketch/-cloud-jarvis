"""
J.A.R.V.I.S  —  db.py
Database connection + all DB operations.
To add a new table: add CREATE TABLE to init_db() and write helper functions below.
"""

import os, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse
import pg8000.dbapi as pg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Connection ────────────────────────────────────────────────────────────────
_db_params = {}

def _resolve_params():
    if _db_params:
        return _db_params
    import socket, re
    url = DATABASE_URL.strip()
    for s in ("postgresql://", "postgres://"):
        if url.startswith(s):
            url = url[len(s):]
    at = url.rfind("@")
    creds, rest = url[:at], url[at+1:]
    colon = creds.find(":")
    user, password = creds[:colon], creds[colon+1:]
    slash = rest.find("/")
    hostport = rest[:slash]
    dbname = rest[slash+1:].split("?")[0]
    host, port = (hostport.rsplit(":", 1)[0], int(hostport.rsplit(":", 1)[1])) if ":" in hostport else (hostport, 5432)
    # Auto-convert Supabase direct URL → pooler (Render blocks port 5432)
    if ".supabase.co" in host:
        m = re.search(r"(?:db\.)?([a-z0-9]+)\.supabase\.co", host)
        if m:
            ref = m.group(1)
            host = "aws-1-ap-south-1.pooler.supabase.com"
            if "." not in user:
                user = f"postgres.{ref}"
        port = 6543
    try:
        host = socket.gethostbyname(host)
    except Exception as e:
        print(f"DNS warning: {e}")
    _db_params.update({"host": host, "database": dbname, "user": user, "password": password, "port": port})
    print(f"✅ DB params resolved: port={port} db={dbname}")
    return _db_params

def get_conn():
    p = _resolve_params()
    return pg.connect(host=p["host"], database=p["database"],
                      user=p["user"], password=p["password"],
                      port=p["port"], ssl_context=True)

# ── Init all tables ───────────────────────────────────────────────────────────
def init_db():
    conn = get_conn(); cur = conn.cursor()
    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
            display_name TEXT, role TEXT DEFAULT 'guest', family_member TEXT,
            approved BOOLEAN DEFAULT FALSE, created_at TEXT, last_login TEXT,
            login_count INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY, username TEXT, device_id TEXT,
            created_at TEXT, last_seen TEXT)""",
        """CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY, role TEXT, content TEXT,
            timestamp TEXT, device_id TEXT, private BOOLEAN DEFAULT FALSE)""",
        """CREATE TABLE IF NOT EXISTS memory_archive (
            id SERIAL PRIMARY KEY, tier INTEGER,
            period_start TEXT, period_end TEXT, summary TEXT,
            device_id TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS facts (
            key TEXT PRIMARY KEY, value TEXT, updated TEXT, person TEXT)""",
        """CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY, device_name TEXT, owner TEXT,
            last_seen TEXT, first_seen TEXT, user_agent TEXT)""",
        """CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            text TEXT, remind_at TEXT, done BOOLEAN DEFAULT FALSE, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            text TEXT, done BOOLEAN DEFAULT FALSE,
            category TEXT DEFAULT 'general', created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            title TEXT, content TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY, person TEXT, name TEXT, dob TEXT, relation TEXT)""",
        """CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY, title TEXT, content TEXT,
            from_person TEXT, created_at TEXT, active BOOLEAN DEFAULT TRUE)""",
        """CREATE TABLE IF NOT EXISTS rl_feedback (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            user_msg TEXT, jarvis_response TEXT, feedback TEXT,
            topic TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS personality_profiles (
            person TEXT PRIMARY KEY, summary TEXT, updated TEXT)""",
        """CREATE TABLE IF NOT EXISTS emotional_history (
            id SERIAL PRIMARY KEY, person TEXT,
            emotion TEXT, intensity TEXT, context TEXT, timestamp TEXT)""",
    ]
    for t in tables:
        cur.execute(t)
    conn.commit(); cur.close(); conn.close()
    print("✅ All tables ready")

# ── Auth ──────────────────────────────────────────────────────────────────────
def hash_pw(password: str) -> str:
    return hashlib.sha256(password.strip().encode()).hexdigest()

def seed_family():
    from config import FAMILY
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        for uname, info in FAMILY.items():
            cur.execute("""INSERT INTO users
                (username,password_hash,display_name,role,family_member,approved,created_at,login_count)
                VALUES (%s,%s,%s,%s,%s,TRUE,%s,0)
                ON CONFLICT (username) DO UPDATE SET
                password_hash=%s, display_name=%s, role=%s, family_member=%s, approved=TRUE""",
                (uname, hash_pw(info["password"]), info["display"], info["role"], info["display"], now,
                 hash_pw(info["password"]), info["display"], info["role"], info["display"]))
            print(f"  ✅ Seeded: {uname}")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"seed_family error: {e}")

def auth_login(username: str, password: str, device_id: str) -> dict:
    try:
        seed_family()
        conn = get_conn(); cur = conn.cursor()
        uname = username.strip().lower()
        cur.execute("SELECT username,display_name,role,family_member,approved,login_count FROM users WHERE username=%s", (uname,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return {"success": False, "error": f"Username '{uname}' not found."}
        # Re-fetch including password hash for verification
        cur.execute("SELECT username,display_name,role,family_member,approved,password_hash,login_count FROM users WHERE username=%s", (uname,))
        row = cur.fetchone()
        if not row or row[5] != hash_pw(password):
            cur.close(); conn.close()
            return {"success": False, "error": "Wrong password. Please try again."}
        if not row[4]:
            cur.close(); conn.close()
            return {"success": False, "error": "Account pending approval from Lucky."}
        now = datetime.now().isoformat()
        token = secrets.token_hex(32)
        cur.execute("UPDATE users SET last_login=%s, login_count=%s WHERE username=%s", (now, (row[6] or 0)+1, uname))
        cur.execute("INSERT INTO sessions (token,username,device_id,created_at,last_seen) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (token, uname, device_id, now, now))
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "token": token, "username": uname,
                "display_name": row[1], "role": row[2], "family_member": row[3]}
    except Exception as e:
        print(f"auth_login error: {e}")
        import traceback; traceback.print_exc()
        return {"success": False, "error": f"Login error: {str(e)[:100]}"}

def auth_verify(token: str) -> dict | None:
    try:
        if not token: return None
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT s.username, u.display_name, u.role, u.family_member
                       FROM sessions s JOIN users u ON s.username=u.username
                       WHERE s.token=%s AND u.approved=TRUE""", (token,))
        row = cur.fetchone()
        if not row: cur.close(); conn.close(); return None
        cur.execute("UPDATE sessions SET last_seen=%s WHERE token=%s", (datetime.now().isoformat(), token))
        conn.commit(); cur.close(); conn.close()
        return {"username": row[0], "display_name": row[1], "role": row[2], "family_member": row[3]}
    except Exception as e:
        print(f"auth_verify error: {e}"); return None

def auth_register_guest(username, password, display_name, relation, knows_member) -> dict:
    try:
        uname = username.strip().lower()
        if len(uname) < 3: return {"success": False, "error": "Username must be 3+ characters."}
        if len(password) < 6: return {"success": False, "error": "Password must be 6+ characters."}
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE username=%s", (uname,))
        if cur.fetchone(): cur.close(); conn.close(); return {"success": False, "error": "Username already taken."}
        now = datetime.now().isoformat()
        cur.execute("""INSERT INTO users (username,password_hash,display_name,role,family_member,approved,created_at,login_count)
                       VALUES (%s,%s,%s,'guest',%s,FALSE,%s,0)""",
                    (uname, hash_pw(password), display_name or uname, f"{relation}, knows {knows_member}", now))
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "message": "Account created! Waiting for Lucky to approve."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def admin_pending() -> list:
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT username,display_name,family_member,created_at FROM users WHERE approved=FALSE ORDER BY created_at DESC")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"username":r[0],"display_name":r[1],"relation":r[2],"created_at":r[3]} for r in rows]
    except: return []

def admin_approve(username: str) -> bool:
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE users SET approved=TRUE WHERE username=%s", (username,))
        conn.commit(); cur.close(); conn.close(); return True
    except: return False

# ── Memory ────────────────────────────────────────────────────────────────────
def save_message(role, content, device_id="unknown", private=False):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO memories (role,content,timestamp,device_id,private) VALUES (%s,%s,%s,%s,%s)",
                    (role, content, datetime.now().isoformat(), device_id, private))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_message: {e}")

def get_history(device_id, limit=12, is_admin=False):
    try:
        conn = get_conn(); cur = conn.cursor()
        if is_admin:
            cur.execute("SELECT role,content FROM memories WHERE private=FALSE ORDER BY id DESC LIMIT %s", (limit,))
        else:
            cur.execute("SELECT role,content FROM memories WHERE device_id=%s ORDER BY id DESC LIMIT %s", (device_id, limit))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as e: print(f"get_history: {e}"); return []

def save_fact(key, value, person="family"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO facts (key,value,updated,person) VALUES (%s,%s,%s,%s) ON CONFLICT (key) DO UPDATE SET value=%s, updated=%s",
                    (key, value, datetime.now().isoformat(), person, value, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_fact: {e}")

def get_facts(limit=30):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT key,value FROM facts LIMIT %s", (limit,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return {r[0]: r[1] for r in rows}
    except: return {}

# ── Devices ───────────────────────────────────────────────────────────────────
def save_device(device_id, device_name, owner, user_agent=""):
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute("""INSERT INTO devices (device_id,device_name,owner,last_seen,first_seen,user_agent)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (device_id) DO UPDATE SET device_name=%s, owner=%s, last_seen=%s""",
                    (device_id, device_name, owner, now, now, user_agent, device_name, owner, now))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_device: {e}")

def touch_device(device_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE devices SET last_seen=%s WHERE device_id=%s", (datetime.now().isoformat(), device_id))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"touch_device: {e}")

def get_device(device_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_name,owner FROM devices WHERE device_id=%s", (device_id,))
        row = cur.fetchone(); cur.close(); conn.close()
        return {"name": row[0], "owner": row[1]} if row else None
    except: return None

def get_all_devices():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_id,device_name,owner,last_seen FROM devices ORDER BY last_seen DESC")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id":r[0],"name":r[1],"owner":r[2],"last_seen":r[3]} for r in rows]
    except: return []

# ── Reminders ─────────────────────────────────────────────────────────────────
def save_reminder(person, device_id, text, remind_at):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO reminders (person,device_id,text,remind_at,created_at) VALUES (%s,%s,%s,%s,%s)",
                    (person, device_id, text, remind_at, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_reminder: {e}")

def get_due_reminders(device_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute("SELECT id,text FROM reminders WHERE device_id=%s AND remind_at<=%s AND done=FALSE", (device_id, now))
        rows = cur.fetchall()
        if rows:
            ids = [r[0] for r in rows]
            cur.execute("UPDATE reminders SET done=TRUE WHERE id=ANY(%s)", (ids,))
            conn.commit()
        cur.close(); conn.close()
        return [{"id": r[0], "text": r[1]} for r in rows]
    except: return []

# ── Todos ─────────────────────────────────────────────────────────────────────
def save_todo(person, device_id, text, category="general"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO todos (person,device_id,text,category,created_at) VALUES (%s,%s,%s,%s,%s)",
                    (person, device_id, text, category, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_todo: {e}")

def get_todos(device_id, person):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,text,done,category FROM todos WHERE device_id=%s OR person=%s ORDER BY id DESC LIMIT 10",
                    (device_id, person))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id":r[0],"text":r[1],"done":r[2],"category":r[3]} for r in rows]
    except: return []

# ── Notes ─────────────────────────────────────────────────────────────────────
def save_note(person, device_id, title, content):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO notes (person,device_id,title,content,created_at) VALUES (%s,%s,%s,%s,%s)",
                    (person, device_id, title, content, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_note: {e}")

# ── Birthdays ─────────────────────────────────────────────────────────────────
def get_upcoming_birthdays(days=7):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT name,dob,relation FROM birthdays")
        rows = cur.fetchall(); cur.close(); conn.close()
        today = datetime.now()
        upcoming = []
        for name, dob, relation in rows:
            try:
                bd = datetime.strptime(dob, "%d/%m")
                bd = bd.replace(year=today.year)
                if bd < today: bd = bd.replace(year=today.year+1)
                days_left = (bd - today).days
                if days_left <= days:
                    upcoming.append({"name": name, "days_left": days_left, "relation": relation})
            except: pass
        return sorted(upcoming, key=lambda x: x["days_left"])
    except: return []

# ── Announcements ─────────────────────────────────────────────────────────────
def save_announcement(title, content, from_person):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO announcements (title,content,from_person,created_at) VALUES (%s,%s,%s,%s)",
                    (title, content, from_person, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_announcement: {e}")

def get_announcements():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT title,content,from_person FROM announcements WHERE active=TRUE ORDER BY id DESC LIMIT 3")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"title":r[0],"content":r[1],"from":r[2]} for r in rows]
    except: return []

# ── RL Feedback ───────────────────────────────────────────────────────────────
def save_feedback(person, device_id, user_msg, jarvis_response, feedback):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO rl_feedback (person,device_id,user_msg,jarvis_response,feedback,created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                    (person, device_id, user_msg, jarvis_response, feedback, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_feedback: {e}")

def get_rl_patterns(person):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT user_msg,jarvis_response FROM rl_feedback WHERE person=%s AND feedback='positive' ORDER BY id DESC LIMIT 5", (person,))
        pos = [f"'{r[0]}' → '{r[1][:60]}'" for r in cur.fetchall()]
        cur.execute("SELECT user_msg,jarvis_response FROM rl_feedback WHERE person=%s AND feedback='negative' ORDER BY id DESC LIMIT 5", (person,))
        neg = [f"'{r[0]}' → '{r[1][:60]}'" for r in cur.fetchall()]
        cur.close(); conn.close()
        return pos, neg
    except: return [], []

# ── Personality ───────────────────────────────────────────────────────────────
def save_personality(person, summary):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO personality_profiles (person,summary,updated) VALUES (%s,%s,%s) ON CONFLICT (person) DO UPDATE SET summary=%s, updated=%s",
                    (person, summary, datetime.now().isoformat(), summary, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_personality: {e}")

def get_personality(person):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT summary FROM personality_profiles WHERE person=%s", (person,))
        row = cur.fetchone(); cur.close(); conn.close()
        return row[0] if row else None
    except: return None

def save_emotion(person, emotion, intensity, context):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO emotional_history (person,emotion,intensity,context,timestamp) VALUES (%s,%s,%s,%s,%s)",
                    (person, emotion, intensity, context, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_emotion: {e}")

def get_recent_emotion(person):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT emotion,intensity,context FROM emotional_history WHERE person=%s ORDER BY id DESC LIMIT 1", (person,))
        row = cur.fetchone(); cur.close(); conn.close()
        return {"emotion": row[0], "intensity": row[1], "context": row[2]} if row else None
    except: return None

# ── Admin ─────────────────────────────────────────────────────────────────────
def get_all_users():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT username,display_name,role,approved,last_login,login_count FROM users ORDER BY role,username")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"username":r[0],"display_name":r[1],"role":r[2],"approved":r[3],"last_login":r[4],"login_count":r[5]} for r in rows]
    except: return []

def wipe_chat(device_id=None):
    try:
        conn = get_conn(); cur = conn.cursor()
        if device_id:
            cur.execute("DELETE FROM memories WHERE device_id=%s", (device_id,))
        else:
            cur.execute("DELETE FROM memories")
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"wipe_chat: {e}")

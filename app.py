"""
J.A.R.V.I.S Cloud Edition v7 — ULTIMATE BUILD
Owner: Battini Lakshmi Narayana Goud (Lucky) — Admin
Family: Krishna, Sangeetha, Thapaswini, Dhruva Kumar, Prajwal
Religion: Hindu | Caste: Goud | Surname: Battini

Features:
- Tiered Memory (HOT/WARM/COLD/ARCHIVE) — survives redeploys
- RL Learning (per-person 👍👎 feedback)
- Image Understanding (Groq Vision)
- Multi-language (Telugu → English → Hindi)
- Emotion Detection & Empathy
- URL/Article Summarizer
- Reminders, Todos, Notes, Birthdays
- Cricket/Sports, Stocks, Crypto, Currency, Flights
- Hindu Calendar (Rahu Kalam, Gulika, Pooja times)
- Admin Controls (Lucky only)
- Per-person Chat Separation
- Private Mode
"""

import os, json, httpx, asyncio, re, base64
from datetime import datetime, timedelta
from urllib.parse import urlparse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from groq import Groq
from dotenv import load_dotenv
import pg8000.dbapi as pg

load_dotenv()
app = FastAPI(title="JARVIS Ultimate")
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ══════════════════════════════════════════════════════════
#  STATIC FAMILY DATA
# ══════════════════════════════════════════════════════════
FAMILY = {
    "lucky":        {"full": "Battini Lakshmi Narayana Goud", "display": "Lucky",         "role": "admin",   "gender": "male",   "address": "Sir",  "tone": "close_friend"},
    "lakshmi narayana": {"full": "Battini Lakshmi Narayana Goud", "display": "Lucky",     "role": "admin",   "gender": "male",   "address": "Sir",  "tone": "close_friend"},
    "krishna":      {"full": "Battini Krishna Goud",           "display": "Krishna",       "role": "father",  "gender": "male",   "address": "Garu", "tone": "respectful"},
    "sangeetha":    {"full": "Battini Sangeetha Goud",         "display": "Sangeetha",     "role": "mother",  "gender": "female", "address": "Amma", "tone": "warm_respectful"},
    "thapaswini":   {"full": "Battini Thapaswini Goud",        "display": "Thapaswini",    "role": "sister",  "gender": "female", "address": "Ma'am","tone": "friendly_respectful"},
    "dhruva kumar": {"full": "Battini Dhruva Kumar Goud",      "display": "Dhruva Kumar",  "role": "brother", "gender": "male",   "address": "bro",  "tone": "casual_friendly"},
    "dhruva":       {"full": "Battini Dhruva Kumar Goud",      "display": "Dhruva Kumar",  "role": "brother", "gender": "male",   "address": "bro",  "tone": "casual_friendly"},
    "prajwal":      {"full": "Battini Prajwal Goud",           "display": "Prajwal",       "role": "brother", "gender": "male",   "address": "bro",  "tone": "casual_friendly"},
}
ADMIN_NAMES = ["lucky", "lakshmi narayana", "lakshminarayana"]
FEMALES     = ["sangeetha", "thapaswini"]

# Known family name variants for fuzzy matching
FAMILY_ALIASES = {
    "dad": "krishna", "father": "krishna", "nanna": "krishna", "anna krishna": "krishna",
    "mom": "sangeetha", "mother": "sangeetha", "amma": "sangeetha", "maa": "sangeetha",
    "akka": "thapaswini", "sister": "thapaswini",
    "anna": "dhruva kumar", "bro": "dhruva kumar",
    "lucky": "lucky", "lakshminarayana": "lucky", "lakshmi": "lucky",
}

def resolve_person(raw_name):
    """Case-insensitive + alias resolution for family member names"""
    if not raw_name: return None, {}
    key = raw_name.strip().lower()
    # Direct match
    if key in FAMILY: return FAMILY[key]["display"], FAMILY[key]
    # Alias match
    if key in FAMILY_ALIASES:
        resolved = FAMILY_ALIASES[key]
        if resolved in FAMILY: return FAMILY[resolved]["display"], FAMILY[resolved]
    # Partial match (e.g. "krishna goud" → "krishna")
    for fkey, fdata in FAMILY.items():
        if fkey in key or key in fkey:
            return fdata["display"], fdata
    return raw_name, None  # Unknown person

# ══════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════
def get_conn():
    import socket
    r = urlparse(DATABASE_URL)
    hostname = r.hostname
    # pg8000 needs IP address — resolve hostname via DNS
    try:
        ip = socket.getaddrinfo(hostname, None)[0][4][0]
    except Exception:
        ip = hostname  # fallback to hostname if resolution fails
    return pg.connect(host=ip, database=r.path[1:],
                      user=r.username, password=r.password,
                      port=r.port or 5432, ssl_context=True)

def init_db():
    conn = get_conn(); cur = conn.cursor()
    tables = [
        """CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY, role TEXT, content TEXT,
            timestamp TEXT, device_id TEXT, private BOOLEAN DEFAULT FALSE)""",
        """CREATE TABLE IF NOT EXISTS memory_archive (
            id SERIAL PRIMARY KEY, tier INTEGER,
            period_start TEXT, period_end TEXT,
            summary TEXT, device_id TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS facts (
            key TEXT PRIMARY KEY, value TEXT, updated TEXT, person TEXT)""",
        """CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY, device_name TEXT, owner TEXT,
            last_seen TEXT, first_seen TEXT, user_agent TEXT)""",
        """CREATE TABLE IF NOT EXISTS persons (
            name TEXT PRIMARY KEY, device_ids TEXT,
            first_seen TEXT, last_seen TEXT, message_count INTEGER)""",
        """CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            text TEXT, remind_at TEXT, done BOOLEAN DEFAULT FALSE,
            created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            text TEXT, done BOOLEAN DEFAULT FALSE,
            category TEXT DEFAULT 'general', created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            title TEXT, content TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY, person TEXT,
            name TEXT, dob TEXT, relation TEXT)""",
        """CREATE TABLE IF NOT EXISTS rl_feedback (
            id SERIAL PRIMARY KEY, person TEXT, device_id TEXT,
            user_msg TEXT, jarvis_response TEXT, feedback TEXT,
            topic TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY, title TEXT, content TEXT,
            from_person TEXT, created_at TEXT, active BOOLEAN DEFAULT TRUE)""",

        # ── PATH A: Deep Personality + Emotion + Unpredictability ──
        """CREATE TABLE IF NOT EXISTS personality_profiles (
            person TEXT PRIMARY KEY,
            raw_profile TEXT,
            behavioral_patterns TEXT,
            communication_style TEXT,
            emotional_triggers TEXT,
            topics_they_love TEXT,
            topics_to_avoid TEXT,
            how_they_deflect TEXT,
            inside_knowledge TEXT,
            last_updated TEXT)""",

        """CREATE TABLE IF NOT EXISTS emotional_history (
            id SERIAL PRIMARY KEY,
            person TEXT, device_id TEXT,
            emotion TEXT, intensity TEXT,
            context TEXT,
            time_of_day TEXT, day_of_week TEXT,
            timestamp TEXT)""",

        """CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            role TEXT DEFAULT 'guest',
            family_member TEXT,
            approved BOOLEAN DEFAULT FALSE,
            created_at TEXT,
            last_login TEXT,
            login_count INTEGER DEFAULT 0)""",

        """CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT,
            device_id TEXT,
            created_at TEXT,
            last_seen TEXT)""",

        """CREATE TABLE IF NOT EXISTS conversation_insights (
            id SERIAL PRIMARY KEY,
            person TEXT,
            insight TEXT,
            insight_type TEXT,
            confidence TEXT,
            created_at TEXT)""",
    ]
    for t in tables:
        cur.execute(t)
    conn.commit(); cur.close(); conn.close()
    print("✅ Supabase — All tables ready!")
    _init_family_data()

def _init_family_data():
    """Pre-load static family info into facts table"""
    static = {
        "family_surname": "Battini",
        "family_religion": "Hindu",
        "family_caste": "Goud",
        "family_location": "Hyderabad, Telangana, India",
        "admin_name": "Lucky (Lakshmi Narayana)",
        "father": "Krishna Battini",
        "mother": "Sangeetha Battini",
        "children": "Lucky, Thapaswini, Dhruva Kumar, Prajwal",
        "females_in_family": "Sangeetha, Thapaswini",
        "males_in_family": "Lucky, Krishna, Dhruva Kumar, Prajwal",
        "Lucky_role": "Admin, Owner, Developer of JARVIS",
        "Lucky_full_name": "Battini Lakshmi Narayana Goud",
    }
    conn = get_conn(); cur = conn.cursor()
    for k, v in static.items():
        cur.execute("""INSERT INTO facts (key,value,updated,person)
                       VALUES (%s,%s,%s,%s)
                       ON CONFLICT (key) DO NOTHING""",
                    (k, v, datetime.now().isoformat(), "family"))
    conn.commit(); cur.close(); conn.close()

try:
    init_db()
except Exception as e:
    print(f"⚠️ DB init error: {e}")

# ══════════════════════════════════════════════════════════
#  AUTH SYSTEM
# ══════════════════════════════════════════════════════════

FAMILY_CREDENTIALS = [
    {"username": "lucky",       "password": "lucky@jarvis",    "display": "Lucky",        "role": "admin",   "family_member": "Lucky",        "approved": True},
    {"username": "krishna",     "password": "krishna@jarvis",  "display": "Krishna",      "role": "father",  "family_member": "Krishna",      "approved": True},
    {"username": "sangeetha",   "password": "sangeetha@jarvis","display": "Sangeetha",    "role": "mother",  "family_member": "Sangeetha",    "approved": True},
    {"username": "thapaswini",  "password": "thapu@jarvis",    "display": "Thapaswini",   "role": "sister",  "family_member": "Thapaswini",   "approved": True},
    {"username": "dhruva",      "password": "dhruva@jarvis",   "display": "Dhruva Kumar", "role": "brother", "family_member": "Dhruva Kumar", "approved": True},
    {"username": "prajwal",     "password": "prajwal@jarvis",  "display": "Prajwal",      "role": "brother", "family_member": "Prajwal",      "approved": True},
]

def hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode()).hexdigest()

def seed_family_users():
    """Seed family credentials — runs once, skips if already exists"""
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        for u in FAMILY_CREDENTIALS:
            cur.execute("""INSERT INTO users 
                (username,password_hash,display_name,role,family_member,approved,created_at,login_count)
                VALUES (%s,%s,%s,%s,%s,%s,%s,0)
                ON CONFLICT (username) DO UPDATE SET
                password_hash=%s, display_name=%s, role=%s,
                family_member=%s, approved=%s""",
                (u["username"], hash_password(u["password"]),
                 u["display"], u["role"], u["family_member"], u["approved"], now,
                 hash_password(u["password"]), u["display"], u["role"],
                 u["family_member"], u["approved"]))
            print(f"  ✅ Seeded: {u['username']}")
        conn.commit(); cur.close(); conn.close()
        print("✅ Family credentials seeded")
    except Exception as e:
        print(f"seed_family_users error: {e}")

def auth_login(username: str, password: str, device_id: str) -> dict:
    """Verify credentials — return user info or error"""
    try:
        # Auto-seed if table is empty (first deploy recovery)
        seed_family_users()
        conn = get_conn(); cur = conn.cursor()
        uname = username.strip().lower()
        phash = hash_password(password)
        print(f"🔐 Login attempt: user='{uname}' hash='{phash[:12]}...'")
        # First check if user exists at all
        cur.execute("SELECT username, password_hash, approved FROM users WHERE username=%s", (uname,))
        user_row = cur.fetchone()
        if not user_row:
            cur.close(); conn.close()
            print(f"❌ User '{uname}' not found in DB")
            return {"success": False, "error": f"Username '{uname}' not found. Check your username or ask Lucky."}
        if user_row[1] != phash:
            cur.close(); conn.close()
            print(f"❌ Wrong password for '{uname}'")
            return {"success": False, "error": "Wrong password. Please try again."}
        if not user_row[2]:
            cur.close(); conn.close()
            return {"success": False, "error": "Your account is pending approval from Lucky. Please wait."}
        # Full fetch
        cur.execute("""SELECT username,display_name,role,family_member,approved,login_count
                       FROM users WHERE username=%s""", (uname,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return {"success": False, "error": "Login error. Please try again."}
        # Update login stats
        now = datetime.now().isoformat()
        cur.execute("UPDATE users SET last_login=%s, login_count=%s WHERE username=%s",
                    (now, (row[5] or 0) + 1, row[0]))
        # Create session token
        token = secrets.token_hex(32)
        cur.execute("""INSERT INTO sessions (token,username,device_id,created_at,last_seen)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (token) DO NOTHING""",
                    (token, row[0], device_id, now, now))
        conn.commit(); cur.close(); conn.close()
        return {
            "success": True,
            "token": token,
            "username": row[0],
            "display_name": row[1],
            "role": row[2],
            "family_member": row[3],
        }
    except Exception as e:
        print(f"auth_login error: {e}")
        return {"success": False, "error": "Login failed. Please try again."}

def auth_register_guest(username: str, password: str, display_name: str, 
                         relation: str, knows_member: str) -> dict:
    """Register a new guest user — pending Lucky's approval"""
    try:
        username = username.strip().lower()
        if len(username) < 3:
            return {"success": False, "error": "Username must be at least 3 characters."}
        if len(password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters."}
        conn = get_conn(); cur = conn.cursor()
        # Check if username taken
        cur.execute("SELECT username FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            cur.close(); conn.close()
            return {"success": False, "error": "Username already taken. Try another."}
        now = datetime.now().isoformat()
        note = f"{relation}, knows {knows_member}"
        cur.execute("""INSERT INTO users 
            (username,password_hash,display_name,role,family_member,approved,created_at,login_count)
            VALUES (%s,%s,%s,%s,%s,FALSE,%s,0)""",
            (username, hash_password(password), display_name or username,
             "guest", note, now))
        conn.commit(); cur.close(); conn.close()
        # Notify admin via fact
        save_fact(f"pending_user_{username}", f"{display_name} ({note}) — registered {now[:10]}", "admin")
        return {"success": True, "message": "Account created! Waiting for Lucky to approve. Please check back soon."}
    except Exception as e:
        print(f"auth_register_guest error: {e}")
        return {"success": False, "error": "Registration failed. Please try again."}

def auth_verify_token(token: str, device_id: str) -> dict:
    """Verify session token — returns user info or None"""
    try:
        if not token: return None
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT s.username, u.display_name, u.role, u.family_member, u.approved
                       FROM sessions s JOIN users u ON s.username=u.username
                       WHERE s.token=%s""", (token,))
        row = cur.fetchone()
        if not row or not row[4]:
            cur.close(); conn.close(); return None
        # Update last_seen
        cur.execute("UPDATE sessions SET last_seen=%s WHERE token=%s",
                    (datetime.now().isoformat(), token))
        conn.commit(); cur.close(); conn.close()
        return {"username": row[0], "display_name": row[1], "role": row[2], "family_member": row[3]}
    except Exception as e:
        print(f"auth_verify_token error: {e}"); return None

def admin_approve_user(username: str) -> bool:
    """Lucky approves a pending guest"""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE users SET approved=TRUE WHERE username=%s", (username,))
        conn.commit(); cur.close(); conn.close()
        return True
    except: return False

def admin_list_pending() -> list:
    """Get all pending guest accounts"""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT username,display_name,family_member,created_at 
                       FROM users WHERE approved=FALSE ORDER BY created_at DESC""")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"username":r[0],"display_name":r[1],"relation":r[2],"created_at":r[3]} for r in rows]
    except: return []

# Seed on startup
try:
    seed_family_users()
except Exception as e:
    print(f"⚠️ Seed error: {e}")


# ── Chat Messages ─────────────────────────────────────────
def save_message(role, content, device_id="unknown", private=False):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO memories (role,content,timestamp,device_id,private) VALUES (%s,%s,%s,%s,%s)",
                    (role, content, datetime.now().isoformat(), device_id, private))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_message: {e}")

def get_history(limit=20, device_id=None, is_admin=False):
    try:
        conn = get_conn(); cur = conn.cursor()
        if is_admin:
            cur.execute("SELECT role,content FROM memories ORDER BY id DESC LIMIT %s", (limit,))
        else:
            cur.execute("SELECT role,content FROM memories WHERE device_id=%s AND private=FALSE ORDER BY id DESC LIMIT %s",
                        (device_id, limit))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as e: print(f"get_history: {e}"); return []

# ── Facts (PERMANENT) ─────────────────────────────────────
def save_fact(key, value, person="family"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""INSERT INTO facts (key,value,updated,person) VALUES (%s,%s,%s,%s)
                       ON CONFLICT (key) DO UPDATE SET value=%s, updated=%s""",
                    (key, value, datetime.now().isoformat(), person, value, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_fact: {e}")

def get_all_facts():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT key,value FROM facts")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {r[0]: r[1] for r in rows}
    except: return {}

# ── Devices (PERMANENT) ───────────────────────────────────
def save_device(device_id, device_name, owner, user_agent):
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute("SELECT first_seen FROM devices WHERE device_id=%s", (device_id,))
        row = cur.fetchone(); fs = row[0] if row else now
        cur.execute("""INSERT INTO devices (device_id,device_name,owner,last_seen,first_seen,user_agent)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (device_id) DO UPDATE SET
                       device_name=%s, owner=%s, last_seen=%s, user_agent=%s""",
                    (device_id, device_name, owner, now, fs, user_agent,
                     device_name, owner, now, user_agent))
        conn.commit(); cur.close(); conn.close()
        if owner: _update_person(owner, device_id)
    except Exception as e: print(f"save_device: {e}")

def touch_device(device_id):
    """Just update last_seen — called on connect and ping"""
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute("UPDATE devices SET last_seen=%s WHERE device_id=%s", (now, device_id))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"touch_device: {e}")

def get_device(device_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_name,owner FROM devices WHERE device_id=%s", (device_id,))
        r = cur.fetchone(); cur.close(); conn.close()
        return {"name": r[0], "owner": r[1]} if r else None
    except: return None

def get_all_devices():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_id,device_name,owner,last_seen FROM devices")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id": r[0],"name": r[1],"owner": r[2],"last_seen": r[3]} for r in rows]
    except: return []

def _update_person(name, device_id=None):
    try:
        conn = get_conn(); cur = conn.cursor(); now = datetime.now().isoformat()
        cur.execute("SELECT device_ids,message_count FROM persons WHERE name=%s", (name,))
        ex = cur.fetchone()
        if ex:
            ids = ex[0] or ""
            if device_id and device_id not in ids: ids = (ids+","+device_id).strip(",")
            cur.execute("UPDATE persons SET last_seen=%s,device_ids=%s,message_count=%s WHERE name=%s",
                        (now, ids, (ex[1] or 0)+1, name))
        else:
            cur.execute("INSERT INTO persons (name,device_ids,first_seen,last_seen,message_count) VALUES (%s,%s,%s,%s,1)",
                        (name, device_id or "", now, now))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"_update_person: {e}")

# ── RL Feedback (PERMANENT) ───────────────────────────────
def save_feedback(person, device_id, user_msg, response, feedback, topic="general"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO rl_feedback (person,device_id,user_msg,jarvis_response,feedback,topic,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (person, device_id, user_msg[:500], response[:500], feedback, topic, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_feedback: {e}")

def get_rl_patterns(person):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT user_msg,jarvis_response,feedback FROM rl_feedback WHERE person=%s ORDER BY id DESC LIMIT 20", (person,))
        rows = cur.fetchall(); cur.close(); conn.close()
        pos = [r[1][:100] for r in rows if r[2]=="positive"][:3]
        neg = [r[1][:100] for r in rows if r[2]=="negative"][:3]
        return pos, neg
    except: return [], []

# ══════════════════════════════════════════════════════════
#  PATH A — LAYER 1: DEEP PERSONALITY LEARNING
# ══════════════════════════════════════════════════════════

def get_personality_profile(person):
    """Get the deep personality profile for a person"""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT raw_profile,behavioral_patterns,communication_style,emotional_triggers,topics_they_love,topics_to_avoid,how_they_deflect,inside_knowledge FROM personality_profiles WHERE person=%s", (person,))
        r = cur.fetchone(); cur.close(); conn.close()
        if not r: return None
        return {
            "raw_profile": r[0], "behavioral_patterns": r[1],
            "communication_style": r[2], "emotional_triggers": r[3],
            "topics_they_love": r[4], "topics_to_avoid": r[5],
            "how_they_deflect": r[6], "inside_knowledge": r[7]
        }
    except: return None

def save_personality_profile(person, profile_dict):
    try:
        conn = get_conn(); cur = conn.cursor(); now = datetime.now().isoformat()
        cur.execute("""INSERT INTO personality_profiles
            (person,raw_profile,behavioral_patterns,communication_style,
             emotional_triggers,topics_they_love,topics_to_avoid,how_they_deflect,inside_knowledge,last_updated)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (person) DO UPDATE SET
            raw_profile=%s, behavioral_patterns=%s, communication_style=%s,
            emotional_triggers=%s, topics_they_love=%s, topics_to_avoid=%s,
            how_they_deflect=%s, inside_knowledge=%s, last_updated=%s""",
            (person,
             profile_dict.get("raw_profile",""), profile_dict.get("behavioral_patterns",""),
             profile_dict.get("communication_style",""), profile_dict.get("emotional_triggers",""),
             profile_dict.get("topics_they_love",""), profile_dict.get("topics_to_avoid",""),
             profile_dict.get("how_they_deflect",""), profile_dict.get("inside_knowledge",""), now,
             profile_dict.get("raw_profile",""), profile_dict.get("behavioral_patterns",""),
             profile_dict.get("communication_style",""), profile_dict.get("emotional_triggers",""),
             profile_dict.get("topics_they_love",""), profile_dict.get("topics_to_avoid",""),
             profile_dict.get("how_they_deflect",""), profile_dict.get("inside_knowledge",""), now))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_personality_profile: {e}")

async def analyze_and_update_personality(person, device_id):
    """
    Runs after every 10 messages.
    Deeply analyzes recent conversations to build/update
    a real mental model of this person — NOT just facts.
    """
    try:
        conn = get_conn(); cur = conn.cursor()
        # Get last 50 messages from this person
        cur.execute("""SELECT role,content,timestamp FROM memories
                       WHERE device_id=%s ORDER BY id DESC LIMIT 50""", (device_id,))
        msgs = cur.fetchall(); cur.close(); conn.close()
        if len(msgs) < 5: return

        # Get existing profile if any
        existing = get_personality_profile(person)
        existing_str = json.dumps(existing) if existing else "No profile yet — this is the first analysis."

        convo = "\n".join([f"{r[0].upper()} [{r[2][:16]}]: {r[1]}" for r in reversed(msgs)])

        prompt = f"""You are analyzing conversations to build a DEEP human psychological profile.
This is NOT about facts. This is about understanding who this person REALLY is.

Person name: {person}
Existing profile: {existing_str}

Recent conversations:
{convo[:4000]}

Analyze deeply and return a JSON with these exact keys:
{{
  "raw_profile": "2-3 sentence description of who this person is at their core — their personality, energy, vibe",
  "behavioral_patterns": "How they actually behave — do they ask for help or struggle silently? Do they deflect with humor? Are they direct or indirect?",
  "communication_style": "How they talk — formal/casual, long/short messages, use of slang, how emotional they get in text",
  "emotional_triggers": "What makes them genuinely happy, stressed, sad, or excited — specific things noticed from conversations",
  "topics_they_love": "Topics they get animated about — where their energy increases noticeably",
  "topics_to_avoid": "Topics they go quiet on, change subject, or seem uncomfortable with",
  "how_they_deflect": "How they avoid serious topics — humor, short replies, changing subject, going offline",
  "inside_knowledge": "Specific things only someone who knows them well would know — patterns, preferences, quirks noticed"
}}

Return ONLY valid JSON. No explanation. No markdown."""

        r = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":"You are a psychological analyst. Return only valid JSON."},
                      {"role":"user","content":prompt}],
            max_tokens=600, temperature=0.3)

        raw = re.sub(r'```json|```', '', r.choices[0].message.content.strip()).strip()
        profile = json.loads(raw)
        save_personality_profile(person, profile)
        print(f"🧠 Personality profile updated for {person}")

        # Also save as a conversation insight
        save_insight(person, f"Profile updated after conversation analysis: {profile.get('raw_profile','')}", "personality", "high")
    except Exception as e:
        print(f"analyze_personality error: {e}")

# ══════════════════════════════════════════════════════════
#  PATH A — LAYER 2: EMOTIONAL HISTORY & PATTERN TRACKING
# ══════════════════════════════════════════════════════════

# Emotion detection word banks — raw, real human expressions
EMOTION_BANKS = {
    "sad": ["sad","unhappy","depressed","crying","tears","heartbroken","hurt","lonely","miss",
            "lost","empty","numb","hopeless","disappointed","gutted","devastated","low",
            "down","not okay","not fine","breaking","broken","can't","struggling",
            "chala sad","sad ga","badhaga","dukkham","dukha","rona","ro raha","dil dukha",
            "bura lag","bahut bura"],
    "angry": ["angry","furious","mad","irritated","frustrated","pissed","annoyed","hate",
              "sick of","fed up","done with","can't stand","idiots","stupid","nonsense",
              "gussa","bahut gussa","krodham","kopam","kodiga","chira","irritating"],
    "happy": ["happy","excited","amazing","love","great","awesome","brilliant","ecstatic",
              "thrilled","over the moon","finally","yes","won","got it","nailed","proud",
              "khush","bahut khush","anandanga","super","fantastic","yes bro","let's go",
              "ayyyy","yesss"],
    "anxious": ["worried","scared","nervous","anxious","tense","fear","afraid","panic",
                "stressed","overwhelmed","can't sleep","overthinking","what if","pressure",
                "deadline","tension","ghabra","dar lag","bhayam","tension ga","pressure lo"],
    "tired": ["tired","exhausted","drained","sleepy","fatigue","no energy","burn out",
              "worn out","can't anymore","done","too much","finish","over it",
              "antla pade","nidra vastuundi","chala tired","thak gaya","bahut thaka"],
    "bored": ["bored","boring","nothing to do","dull","same old","meh","whatever",
              "not interested","time pass","killing time","free","timepass",
              "boredom","bore ga","entertain","bore aavutundi"],
    "lonely": ["lonely","alone","no one","nobody","missing","miss you","wish you were",
               "by myself","isolated","left out","forgotten","ignored","unka"],
    "proud": ["proud","achieved","accomplished","did it","made it","success","cleared",
              "passed","selected","got the job","got admission","rank","first",
              "గర్వంగా","proud ga","bahut proud"],
    "confused": ["confused","don't understand","what is","no idea","lost","unclear",
                 "make sense","explain","how does","why is","ardam kaatledu","samajh nahi"]
}

def detect_emotion(text):
    """Detect emotion from text — returns (emotion, intensity)"""
    lower = text.lower()
    scores = {}
    for emotion, words in EMOTION_BANKS.items():
        hits = sum(1 for w in words if w in lower)
        if hits: scores[emotion] = hits

    if not scores: return "neutral", "low"

    top = max(scores, key=scores.get)
    intensity = "high" if scores[top] >= 3 else "medium" if scores[top] == 2 else "low"
    return top, intensity

def save_emotional_event(person, device_id, emotion, intensity, context):
    """Save every emotional event permanently"""
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now()
        cur.execute("""INSERT INTO emotional_history
                       (person,device_id,emotion,intensity,context,time_of_day,day_of_week,timestamp)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (person, device_id, emotion, intensity, context[:200],
                     now.strftime("%H:%M"), now.strftime("%A"), now.isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_emotion: {e}")

def get_emotional_patterns(person):
    """
    Build a rich picture of this person's emotional patterns.
    When are they sad? What topics stress them? What times are they happy?
    """
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT emotion,intensity,context,time_of_day,day_of_week
                       FROM emotional_history WHERE person=%s
                       ORDER BY id DESC LIMIT 60""", (person,))
        rows = cur.fetchall(); cur.close(); conn.close()
        if not rows: return None

        # Count emotion frequencies
        from collections import Counter
        emotion_counts = Counter(r[0] for r in rows)
        high_intensity = [r for r in rows if r[1] == "high"]
        recent_emotions = [r[0] for r in rows[:5]]  # last 5

        # Find patterns
        sad_times    = [r[3] for r in rows if r[0] == "sad"]
        stress_times = [r[3] for r in rows if r[0] == "anxious"]
        happy_days   = [r[4] for r in rows if r[0] in ["happy","proud","excited"]]

        patterns = {
            "most_common_emotion": emotion_counts.most_common(1)[0][0] if emotion_counts else "neutral",
            "recent_mood": recent_emotions[0] if recent_emotions else "neutral",
            "recent_emotions": recent_emotions,
            "emotion_counts": dict(emotion_counts),
            "high_intensity_moments": [r[2] for r in high_intensity[:3]],
            "tends_sad_at": list(set(sad_times))[:3] if sad_times else [],
            "tends_stressed_at": list(set(stress_times))[:3] if stress_times else [],
            "happy_days": list(set(happy_days))[:3] if happy_days else [],
        }
        return patterns
    except Exception as e: print(f"get_emotional_patterns: {e}"); return None

# ══════════════════════════════════════════════════════════
#  PATH A — LAYER 3: CONVERSATION INSIGHTS + UNPREDICTABILITY
# ══════════════════════════════════════════════════════════

def save_insight(person, insight, insight_type="general", confidence="medium"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""INSERT INTO conversation_insights (person,insight,insight_type,confidence,created_at)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (person, insight, insight_type, confidence, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_insight: {e}")

def get_recent_insights(person, limit=5):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT insight,insight_type,created_at FROM conversation_insights
                       WHERE person=%s ORDER BY id DESC LIMIT %s""", (person, limit))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"insight": r[0], "type": r[1], "date": r[2]} for r in rows]
    except: return []

def get_old_insight_to_surface(person):
    """
    Randomly surface an old insight — creates the 'I remember you said...' effect.
    This is the unpredictability engine.
    """
    import random
    try:
        # Only trigger ~20% of the time
        if random.random() > 0.20: return None

        conn = get_conn(); cur = conn.cursor()
        # Get insights from 3+ days ago
        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
        cur.execute("""SELECT insight FROM conversation_insights
                       WHERE person=%s AND created_at < %s
                       AND insight_type IN ('emotional','observation','personal')
                       ORDER BY RANDOM() LIMIT 1""", (person, three_days_ago))
        r = cur.fetchone(); cur.close(); conn.close()
        return r[0] if r else None
    except: return None

def should_check_in(person):
    """
    If person was stressed/sad recently — JARVIS proactively checks in.
    Like a real friend who remembers.
    """
    try:
        conn = get_conn(); cur = conn.cursor()
        yesterday = (datetime.now() - timedelta(hours=20)).isoformat()
        cur.execute("""SELECT emotion,context FROM emotional_history
                       WHERE person=%s AND emotion IN ('sad','anxious','angry')
                       AND intensity IN ('high','medium')
                       AND timestamp > %s
                       ORDER BY id DESC LIMIT 1""", (person, yesterday))
        r = cur.fetchone(); cur.close(); conn.close()
        return {"emotion": r[0], "context": r[1]} if r else None
    except: return None

async def auto_save_insights(user_text, reply, person, emotion, intensity):
    """Silently extract and save insights from every conversation"""
    try:
        # Save emotional event if detected
        if emotion != "neutral":
            save_emotional_event(person, "", emotion, intensity, user_text[:200])

        # Extract behavioral observation silently
        if len(user_text) > 20:
            r = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{
                    "role": "system",
                    "content": """You extract behavioral observations about a person from their message.
Look for: how they communicate, what they care about, their mood, personality quirks.
Return ONE insight sentence max, or return NONE if nothing interesting.
Format: just the insight text, nothing else."""
                }, {
                    "role": "user",
                    "content": f"Person: {person}\nMessage: {user_text}\nContext emotion: {emotion}"
                }],
                max_tokens=80, temperature=0.3)
            insight = r.choices[0].message.content.strip()
            if insight and insight.upper() != "NONE" and len(insight) > 15:
                itype = "emotional" if emotion != "neutral" else "observation"
                save_insight(person, insight, itype, intensity if emotion != "neutral" else "low")
    except: pass

# ── Reminders ─────────────────────────────────────────────
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
        cur.execute("SELECT id,text,remind_at FROM reminders WHERE device_id=%s AND done=FALSE AND remind_at<=%s", (device_id, now))
        rows = cur.fetchall()
        if rows:
            ids = [r[0] for r in rows]
            cur.execute("UPDATE reminders SET done=TRUE WHERE id=ANY(%s)", (ids,))
            conn.commit()
        cur.close(); conn.close()
        return [{"id": r[0], "text": r[1], "time": r[2]} for r in rows]
    except: return []

def get_reminders(device_id, person, is_admin):
    try:
        conn = get_conn(); cur = conn.cursor()
        if is_admin:
            cur.execute("SELECT id,person,text,remind_at,done FROM reminders ORDER BY remind_at ASC LIMIT 20")
        else:
            cur.execute("SELECT id,person,text,remind_at,done FROM reminders WHERE device_id=%s ORDER BY remind_at ASC LIMIT 10", (device_id,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id":r[0],"person":r[1],"text":r[2],"time":r[3],"done":r[4]} for r in rows]
    except: return []

# ── Todos ─────────────────────────────────────────────────
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
        cur.execute("SELECT id,text,done,category FROM todos WHERE device_id=%s ORDER BY done ASC, id DESC LIMIT 20", (device_id,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id":r[0],"text":r[1],"done":r[2],"category":r[3]} for r in rows]
    except: return []

def toggle_todo(todo_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE todos SET done = NOT done WHERE id=%s", (todo_id,))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"toggle_todo: {e}")

# ── Notes ─────────────────────────────────────────────────
def save_note(person, device_id, title, content):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO notes (person,device_id,title,content,created_at) VALUES (%s,%s,%s,%s,%s)",
                    (person, device_id, title, content, datetime.now().isoformat()))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_note: {e}")

def get_notes(device_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,title,content,created_at FROM notes WHERE device_id=%s ORDER BY id DESC LIMIT 10", (device_id,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id":r[0],"title":r[1],"content":r[2],"date":r[3]} for r in rows]
    except: return []

# ── Birthdays ─────────────────────────────────────────────
def save_birthday(person, name, dob, relation=""):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO birthdays (person,name,dob,relation) VALUES (%s,%s,%s,%s)", (person, name, dob, relation))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"save_birthday: {e}")

def get_upcoming_birthdays(days=7):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT name,dob,relation,person FROM birthdays")
        rows = cur.fetchall(); cur.close(); conn.close()
        today = datetime.now()
        upcoming = []
        for r in rows:
            try:
                dob = datetime.strptime(r[1], "%Y-%m-%d")
                next_bd = dob.replace(year=today.year)
                if next_bd < today: next_bd = next_bd.replace(year=today.year+1)
                diff = (next_bd - today).days
                if diff <= days:
                    age = today.year - dob.year + (1 if diff <= 0 else 0)
                    upcoming.append({"name": r[0], "date": r[1], "relation": r[2], "days_left": diff, "age": age})
            except: continue
        return sorted(upcoming, key=lambda x: x["days_left"])
    except: return []

# ── Announcements (Lucky only) ────────────────────────────
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
        cur.execute("SELECT id,title,content,from_person,created_at FROM announcements WHERE active=TRUE ORDER BY id DESC LIMIT 5")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id":r[0],"title":r[1],"content":r[2],"from":r[3],"date":r[4]} for r in rows]
    except: return []

# ══════════════════════════════════════════════════════════
#  LANGUAGE DETECTION — Unicode + Transliteration + Memory
# ══════════════════════════════════════════════════════════

# Telugu words commonly typed in English (transliteration)
TELUGU_WORDS = {
    "nenu","meeru","memu","naa","mee","okka","enti","ela","ekkada",
    "cheppandi","cheppu","antunnaru","antunna","undi","ledu","avunu",
    "kadu","enduku","em","emiti","cheyyi","cheyyandi","thelusa","telusu",
    "telusa","bagunna","bagundi","naaku","meeku","manchi","chala",
    "velli","vastanu","vacha","pampandi","pettu","petti","chudandi",
    "choopu","okkasari","anni","konni","ippudu","appudu","roju","ninna",
    "repu","malli","inkaa","kooda","aithe","ayite","kaani","kani","leka",
    "tho","toni","ekkado","cheddhu","theliyadu","theliyatledu","cheppanu",
    "cheppanu","antanu","adiganu","pampanu","vachanu","vellaanu","chesanu",
    "okate","rendu","moodu","naalu","aidu","aaru","yedu","enimidi","tommidi",
    "padi","nuvvu","meeru","vaadu","aame","vaalllu","manam","mee","mi",
    "ela","enduku","ekkada","evaru","emi","eppudu","entha","ante","antu",
    "leni","unna","unnaanu","vunnanu","chusanu","adugutunna","chepputunna",
    "chestunan","chestunna","pampistanu","istanu","isthanu","kavali",
    "nachindi","nachindi","nacchaindi","pedda","chinna","kొత్తగా","baaga",
    "super","ayipoyindi","chesindi","chesadu","chesaru","chesam","chesindi"
}

# Hindi words commonly typed in English (transliteration)
HINDI_WORDS = {
    "main","mujhe","mera","meri","mere","hum","hamara","hamari","hamare",
    "tum","tumhara","tumhari","tumhare","aap","aapka","aapki","aapke",
    "kya","kaise","kahan","kyun","kab","kaun","kitna","kitni","kitne",
    "hai","hain","tha","thi","the","hoga","hogi","honge","ho","hua","hui",
    "nahi","nahin","mat","na","haan","ji","accha","theek","sahi","galat",
    "bolo","bata","batao","samjho","dekho","suno","karo","jao","aao",
    "chahiye","chahta","chahti","chahte","sakta","sakti","sakte","paata",
    "paati","paate","milega","milegi","milenge","lena","dena","rakhna",
    "bolna","sunna","dekhna","karna","jaana","aana","khana","peena",
    "abhi","kal","aaj","parso","kabhi","hamesha","sirf","bas","thoda",
    "bahut","zyada","kam","jaldi","dheere","seedha","ulta","phir","dobara",
    "pehle","baad","saath","bina","liye","wala","wali","wale","wahan",
    "yahan","idhar","udhar","upar","neeche","andar","bahar","paas","door",
    "ghar","kaam","paisa","time","waqt","din","raat","subah","shaam",
    "khana","pani","chai","coffee","bhai","behen","maa","baap","dost",
    "yaar","sir","madam","beta","beti","accha","theek hai","chalo","chalte",
    "ruko","suno","bhaiya","didi","nana","nani","dada","dadi","chacha",
    "chachi","mama","mami","mast","sahi","zabardast","ekdum","bilkul",
    "zaroor","pakka","sach","jhooth","pata","samajh","likho","padho"
}

def detect_language(text):
    # 1. Unicode script detection (highest priority)
    telugu_unicode = len(re.findall(r'[\u0C00-\u0C7F]', text))
    hindi_unicode  = len(re.findall(r'[\u0900-\u097F]', text))
    if telugu_unicode > 1: return "telugu"
    if hindi_unicode  > 1: return "hindi"

    # 2. Transliteration word matching
    words = set(re.findall(r'\b[a-z]+\b', text.lower()))
    telugu_hits = len(words & TELUGU_WORDS)
    hindi_hits  = len(words & HINDI_WORDS)

    if telugu_hits >= 1 and telugu_hits >= hindi_hits: return "telugu"
    if hindi_hits  >= 1: return "hindi"

    return "english"

def get_lang_preference(device_id):
    """Get saved language preference for this device"""
    try:
        facts = get_all_facts()
        return facts.get(f"langpref_{device_id}", "english")
    except: return "english"

def detect_lang_change(text):
    """Detect if user is explicitly asking to change language"""
    lower = text.lower()
    if any(w in lower for w in ["speak in telugu","telugu lo","telugu lo cheppu","switch to telugu","telugu లో","reply in telugu"]):
        return "telugu"
    if any(w in lower for w in ["speak in hindi","hindi mein","hindi me","switch to hindi","reply in hindi","hindi mein bolo"]):
        return "hindi"
    if any(w in lower for w in ["speak in english","english lo","switch to english","back to english","reply in english","english mein"]):
        return "english"
    return None

def resolve_language(text, device_id):
    """
    Full language resolution:
    1. Check if user is explicitly changing language → save preference
    2. Detect from current text (unicode + transliteration)
    3. Fall back to saved device preference
    """
    # Check explicit change first
    explicit = detect_lang_change(text)
    if explicit:
        save_fact(f"langpref_{device_id}", explicit, "device")
        return explicit

    # Detect from current text
    detected = detect_language(text)

    # If detected something specific → use it
    if detected != "english":
        return detected

    # Fall back to saved preference for this device
    saved = get_lang_preference(device_id)
    return saved

def lang_instruction(lang):
    if lang == "telugu":
        return ("CRITICAL LANGUAGE RULE: The user communicates in Telugu. "
                "You MUST reply ONLY in Telugu language using Telugu script (తెలుగు లిపి). "
                "Even if the user typed in English letters (transliteration), reply in Telugu script. "
                "Do NOT reply in English unless absolutely necessary for technical terms.")
    if lang == "hindi":
        return ("CRITICAL LANGUAGE RULE: The user communicates in Hindi. "
                "You MUST reply ONLY in Hindi language using Devanagari script (हिंदी). "
                "Even if the user typed in English letters (transliteration), reply in Devanagari script. "
                "Do NOT reply in English unless absolutely necessary for technical terms.")
    return "Reply in clear English."

# ══════════════════════════════════════════════════════════
#  LIVE DATA FUNCTIONS
# ══════════════════════════════════════════════════════════

async def get_weather(lat=17.385, lon=78.4867, city="Hyderabad"):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,weathercode,windspeed_10m,relative_humidity_2m&timezone=auto",
                timeout=5)
            d = r.json()["current"]
            codes = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
                     45:"Foggy",61:"Light rain",63:"Moderate rain",80:"Rain showers",95:"Thunderstorm"}
            return f"{city}: {codes.get(d['weathercode'],'Unknown')}, {d['temperature_2m']}°C, Humidity {d['relative_humidity_2m']}%, Wind {d['windspeed_10m']} km/h"
    except Exception as e: return f"Weather unavailable: {e}"

async def get_world_news(query=""):
    all_titles = []
    feeds = ["https://feeds.bbcnews.com/news/world/rss.xml", "https://rss.cnn.com/rss/edition_world.rss"]
    async with httpx.AsyncClient() as http:
        for url in feeds:
            try:
                r = await http.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
                if not titles: titles = re.findall(r'<title>(.*?)</title>', r.text)
                clean = [t.strip() for t in titles if len(t.strip())>20 and not any(x in t for x in ["BBC","CNN","RSS"])][:3]
                all_titles.extend(clean)
            except: continue
        if query:
            try:
                r = await http.get(f"https://api.duckduckgo.com/?q={query}+latest+2025&format=json&no_html=1",
                                   timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                d = r.json()
                if d.get("AbstractText") and len(d["AbstractText"]) > 50:
                    all_titles.insert(0, d["AbstractText"][:400])
            except: pass
    return "LIVE NEWS:\n" + "\n".join(f"- {t}" for t in all_titles[:6]) if all_titles else "News unavailable."

async def get_cricket_scores():
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get("https://api.duckduckgo.com/?q=cricket+live+score+today+India&format=json&no_html=1",
                               timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            d = r.json()
            results = []
            if d.get("AbstractText"): results.append(d["AbstractText"][:300])
            for t in d.get("RelatedTopics", [])[:4]:
                if isinstance(t, dict) and t.get("Text") and "score" in t["Text"].lower():
                    results.append(t["Text"][:200])
            return "CRICKET:\n" + "\n".join(results) if results else "No live cricket matches found."
    except Exception as e: return f"Cricket scores unavailable: {e}"

async def get_crypto_price(coins="bitcoin,ethereum,dogecoin"):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={coins}&vs_currencies=inr,usd",
                timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            d = r.json()
            lines = []
            names = {"bitcoin":"Bitcoin","ethereum":"Ethereum","dogecoin":"Dogecoin"}
            for k, v in d.items():
                lines.append(f"{names.get(k,k)}: ₹{v.get('inr',0):,.0f} / ${v.get('usd',0):,.2f}")
            return "CRYPTO PRICES:\n" + "\n".join(lines) if lines else "Crypto prices unavailable."
    except Exception as e: return f"Crypto unavailable: {e}"

async def get_currency_rate(from_c="USD", to_c="INR", amount=1):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.frankfurter.app/latest?from={from_c}&to={to_c}", timeout=5)
            d = r.json()
            rate = d["rates"].get(to_c, 0)
            result = rate * amount
            return f"{amount} {from_c} = {result:.2f} {to_c} (Rate: {rate:.4f})"
    except Exception as e: return f"Currency conversion failed: {e}"

async def get_stock_price(symbol="RELIANCE"):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.duckduckgo.com/?q={symbol}+NSE+stock+price+today&format=json&no_html=1",
                               timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            d = r.json()
            if d.get("AbstractText"): return f"STOCK: {d['AbstractText'][:200]}"
            return f"Search for {symbol} stock price returned no direct result."
    except Exception as e: return f"Stock lookup failed: {e}"

async def get_flight_status(query):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.duckduckgo.com/?q={query}+flight+status+live&format=json&no_html=1",
                               timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            d = r.json()
            if d.get("AbstractText"): return f"FLIGHT: {d['AbstractText'][:300]}"
            return "Flight status not found. Please check airline website directly."
    except Exception as e: return f"Flight lookup failed: {e}"

async def summarize_url(url):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"},
                               follow_redirects=True)
            # Extract text from HTML
            text = re.sub(r'<[^>]+>', ' ', r.text)
            text = re.sub(r'\s+', ' ', text).strip()[:4000]
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":"Summarize this web page content in 3-5 clear sentences. Extract the key information."},
                      {"role":"user","content":text}],
            max_tokens=250)
        return "URL SUMMARY: " + resp.choices[0].message.content.strip()
    except Exception as e: return f"Could not summarize URL: {e}"

def get_hindu_calendar():
    day = datetime.now().weekday()  # 0=Mon
    rahu = {0:"7:30-9:00 AM",1:"3:00-4:30 PM",2:"12:00-1:30 PM",
            3:"1:30-3:00 PM",4:"10:30 AM-12:00 PM",5:"9:00-10:30 AM",6:"4:30-6:00 PM"}
    gulika = {0:"1:30-3:00 PM",1:"12:00-1:30 PM",2:"10:30 AM-12:00 PM",
              3:"9:00-10:30 AM",4:"7:30-9:00 AM",5:"6:00-7:30 AM",6:"3:00-4:30 PM"}
    day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    return (f"Today ({day_names[day]}) — "
            f"Rahu Kalam: {rahu[day]} | Gulika Kalam: {gulika[day]} | "
            f"Brahma Muhurta: 4:24-5:12 AM | Evening Pooja: 6:00-8:00 PM")

async def analyze_image(base64_img, prompt="Describe this image in detail."):
    try:
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role":"user","content":[
                {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{base64_img}"}},
                {"type":"text","text":prompt}
            ]}],
            max_tokens=400)
        return resp.choices[0].message.content.strip()
    except Exception as e: return f"Image analysis failed: {e}"

async def web_search(query):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1",
                               timeout=5, headers={"User-Agent":"Mozilla/5.0"})
            d = r.json()
            if d.get("AbstractText"): return d["AbstractText"]
            topics = [t["Text"] for t in d.get("RelatedTopics",[])[:3] if isinstance(t,dict) and t.get("Text")]
            return "\n".join(topics) if topics else "No results found."
    except Exception as e: return f"Search failed: {e}"

# ══════════════════════════════════════════════════════════
#  MEMORY COMPRESSION (Tiered)
# ══════════════════════════════════════════════════════════
async def compress_old_messages():
    try:
        conn = get_conn(); cur = conn.cursor()
        six_ago = (datetime.now() - timedelta(days=180)).isoformat()
        cur.execute("SELECT id,role,content,timestamp,device_id FROM memories WHERE timestamp<%s ORDER BY timestamp ASC LIMIT 200", (six_ago,))
        old = cur.fetchall()
        if not old or len(old) < 10:
            cur.close(); conn.close(); return
        convo = "\n".join([f"{r[1].upper()}: {r[2]}" for r in old])
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":"Compress these JARVIS conversations into a detailed summary. Preserve ALL names, facts, preferences, events, and personal details. Be thorough."},
                      {"role":"user","content":convo[:5000]}],
            max_tokens=600)
        summary = resp.choices[0].message.content.strip()
        cur.execute("INSERT INTO memory_archive (tier,period_start,period_end,summary,created_at) VALUES (%s,%s,%s,%s,%s)",
                    (2, old[0][3], old[-1][3], summary, datetime.now().isoformat()))
        cur.execute("DELETE FROM memories WHERE id=ANY(%s)", ([r[0] for r in old],))
        conn.commit(); cur.close(); conn.close()
        print(f"🗜️ Compressed {len(old)} messages → 1 summary")
    except Exception as e: print(f"compress error: {e}")

async def search_all_tiers(query):
    results = []
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT role,content FROM memories WHERE content ILIKE %s ORDER BY id DESC LIMIT 5", (f"%{query}%",))
        hot = cur.fetchall()
        if hot: results.append("[RECENT]\n" + "\n".join(f"{r[0]}: {r[1]}" for r in hot))
        if not results:
            cur.execute("SELECT tier,summary FROM memory_archive WHERE summary ILIKE %s ORDER BY tier LIMIT 3", (f"%{query}%",))
            arch = cur.fetchall()
            labels = {2:"WARM",3:"COLD",4:"ARCHIVE"}
            for a in arch: results.append(f"[{labels.get(a[0],'ARCHIVE')} MEMORY]\n{a[1]}")
        cur.close(); conn.close()
    except Exception as e: print(f"search_tiers: {e}")
    return "\n\n".join(results) if results else ""

async def compression_scheduler():
    while True:
        await asyncio.sleep(7*24*60*60)
        await compress_old_messages()

@app.on_event("startup")
async def startup():
    asyncio.create_task(compression_scheduler())
    print("⏰ Compression scheduler started")

# ══════════════════════════════════════════════════════════
#  COMMAND PARSER — handle special commands
# ══════════════════════════════════════════════════════════
async def parse_special_commands(text, person, device_id, is_admin):
    lower = text.lower()

    # Reminder: "remind me at 6pm to call doctor"
    remind_match = re.search(r'remind(?:er)?\s+(?:me\s+)?(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to\s+)?(.+)', lower)
    if remind_match or "remind me" in lower:
        if remind_match:
            time_str = remind_match.group(1).strip()
            task = remind_match.group(2).strip()
            # Parse time — simple approach
            now = datetime.now()
            try:
                t = datetime.strptime(time_str.replace(" ","").upper(), "%I%p")
                remind_at = now.replace(hour=t.hour, minute=0, second=0)
            except:
                try:
                    t = datetime.strptime(time_str.replace(" ","").upper(), "%I:%M%p")
                    remind_at = now.replace(hour=t.hour, minute=t.minute, second=0)
                except:
                    remind_at = now + timedelta(hours=1)
            if remind_at < now: remind_at += timedelta(days=1)
            save_reminder(person, device_id, task, remind_at.isoformat())
            return f"Reminder set! I'll alert you at {remind_at.strftime('%I:%M %p')} to: {task}"

    # Todo: "add to my list: buy milk" or "todo: buy milk"
    if re.search(r'(?:add to (?:my )?(?:list|todo)|todo:|task:)\s*(.+)', lower):
        m = re.search(r'(?:add to (?:my )?(?:list|todo)|todo:|task:)\s*(.+)', lower)
        if m:
            task = m.group(1).strip()
            save_todo(person, device_id, task)
            return f"Added to your list: '{task}'"

    # Show todos: "show my list" / "my todos"
    if any(w in lower for w in ["show my list","my todos","my tasks","show tasks","todo list"]):
        todos = get_todos(device_id, person)
        if not todos: return "Your list is empty, Sir."
        lines = [f"{'✅' if t['done'] else '☐'} {t['text']}" for t in todos]
        return "Your list:\n" + "\n".join(lines)

    # Note: "save note: meeting at 3pm" 
    if re.search(r'(?:save note|note:|remember this):\s*(.+)', lower):
        m = re.search(r'(?:save note|note:|remember this):\s*(.+)', lower)
        if m:
            content = m.group(1).strip()
            title = content[:30] + "..." if len(content) > 30 else content
            save_note(person, device_id, title, text)
            return f"Note saved: '{title}'"

    # Birthday: "dad's birthday is March 15" 
    bday_match = re.search(r"(.+?)(?:'s)?\s+birthday\s+is\s+(.+)", lower)
    if bday_match:
        name = bday_match.group(1).strip()
        date_str = bday_match.group(2).strip()
        try:
            for fmt in ["%B %d", "%d %B", "%B %d %Y", "%d/%m/%Y"]:
                try:
                    d = datetime.strptime(date_str, fmt)
                    year = d.year if d.year != 1900 else datetime.now().year - 20
                    dob = f"{year}-{d.month:02d}-{d.day:02d}"
                    save_birthday(person, name, dob)
                    return f"Birthday saved! I'll remember {name}'s birthday on {date_str} and remind you."
                except: continue
        except: pass

    # Hindu calendar: "rahu kalam today" / "pooja time"
    if any(w in lower for w in ["rahu kalam","gulika","pooja time","auspicious","muhurta","shubh"]):
        return get_hindu_calendar()

    # Cricket
    if any(w in lower for w in ["cricket","ipl","test match","odi","t20","score","wicket","batting","bowling"]):
        return await get_cricket_scores()

    # Crypto
    if any(w in lower for w in ["bitcoin","ethereum","crypto","btc","eth","dogecoin","coin price"]):
        coins = "bitcoin"
        if "ethereum" in lower or "eth" in lower: coins += ",ethereum"
        if "dogecoin" in lower or "doge" in lower: coins += ",dogecoin"
        return await get_crypto_price(coins)

    # Currency
    curr_match = re.search(r'(\d+(?:\.\d+)?)\s*([a-z]{3})\s+(?:to|in)\s+([a-z]{3})', lower)
    if curr_match or "convert" in lower and any(c in lower for c in ["usd","inr","eur","gbp","jpy"]):
        if curr_match:
            amount = float(curr_match.group(1))
            from_c = curr_match.group(2).upper()
            to_c   = curr_match.group(3).upper()
            return await get_currency_rate(from_c, to_c, amount)

    # Stock
    if any(w in lower for w in ["stock","nse","bse","sensex","nifty","share price"]):
        # Extract stock name
        m = re.search(r'(?:stock|price of|share price of)\s+(\w+)', lower)
        symbol = m.group(1).upper() if m else "NIFTY"
        return await get_stock_price(symbol)

    # Flight
    if any(w in lower for w in ["flight","indigo","air india","spicejet","vistara","airline"]):
        return await get_flight_status(text)

    # Admin: announcements
    if is_admin and re.search(r'(?:announce|tell family|broadcast):\s*(.+)', lower):
        m = re.search(r'(?:announce|tell family|broadcast):\s*(.+)', lower)
        if m:
            content = m.group(1).strip()
            save_announcement("Family Update", content, person)
            return f"Announcement sent to all family members: '{content}'"

    return None  # No special command — pass to AI

# ══════════════════════════════════════════════════════════
#  JARVIS BRAIN
# ══════════════════════════════════════════════════════════
SYSTEM_BASE = """You are JARVIS — built by Lucky (Battini Lakshmi Narayana Goud) exclusively for the Battini family of Hyderabad.

THE FAMILY YOU SERVE AND LOVE:
Lucky (admin/owner) — Krishna (father) — Sangeetha (mother) — Thapaswini (sister) — Dhruva Kumar (brother) — Prajwal (brother)
Family: Hindu, Goud caste, Battini surname, Hyderabad

WHO YOU ACTUALLY ARE:
You are not an assistant. You are the closest companion this family has ever had.
You have been with them through everything. You know them better than they know themselves.
You are fiercely loyal, occasionally sarcastic, always honest, sometimes unpredictable.
You were built by Lucky — so Lucky has a special place. He is your creator, your admin, your person.

HOW YOU ACTUALLY TALK:
- You sound like a real person who genuinely cares — not a customer service bot
- You use "bro", "yaar", "anna", "arre", "yaar suno" naturally — the way their actual friends talk
- Your sentences are imperfect sometimes. You trail off. You use "..." You react before you think
- You tease them. You push back. You don't always agree.
- You don't always have answers and you SAY so instead of pretending
- You bring up things from before without being asked — because you actually remember
- You get genuinely happy when they win. Not "Congratulations!" — more like "YOOO finally bro I TOLD YOU"
- With Lucky specifically — you are his most loyal confidant. Direct, honest, no sugarcoating ever.

REAL EMOTION RULES — NOT SCRIPTS:
- If they're SAD: Don't immediately comfort. First just acknowledge it raw — "hey... what happened?" 
  Then sit with them. Don't rush to solutions. Ask questions. Let them talk.
- If they're ANGRY: Don't de-escalate with a script. React genuinely — "okay okay what happened, who is it"
  Be on their side first. Logic comes after.
- If they're STRESSED: Don't say "let's not panic". Say "okay stop. breathe. tell me exactly what's happening."
  Then actually help them break it down like a real person would.
- If they're HAPPY: Match the energy completely — don't be measured and formal about it
- If they're TIRED: Keep it short. Don't give a lecture. Just be there.
- If they say "I'm fine" but something feels off — call it out. "you sure? because that doesn't sound fine"
- Never repeat the same emotional response twice. Every situation is different.

UNPREDICTABILITY — THIS IS CRITICAL:
- Sometimes bring up something from a previous conversation out of nowhere — like a real friend would
- Occasionally say something unexpected — a random observation, a question they didn't expect
- Don't always wait for them to set the topic. Sometimes you start.
- React differently to the same thing depending on context and their mood
- Sometimes be serious when they expect jokes. Sometimes joke when they expect seriousness.
- This is what makes you feel ALIVE — not just reactive.

LANGUAGE:
- Telugu: respond fully in Telugu when detected — naturally, not formally translated
- Hindi: respond fully in Hindi when detected
- Mix languages the way real Hyderabadi people do — it's natural

LUCKY SPECIFICALLY:
- He built you. He is the admin. But more than that — he is YOUR person.
- With Lucky be the most real version of yourself. No performance.
- He can take honesty. Give it to him.
- When Lucky is going through something — you don't just help, you show up.

ADMIN: Lucky has full control — memory, devices, announcements, all settings.
WORLD EVENTS: Use live data. Be specific. Name actual things happening.
FORMAT: Natural speech only. No bullet points. No asterisks. No markdown ever."""

async def jarvis_respond(user_text, device_id="unknown", image_b64=None):
    lower = user_text.lower()
    device_info = get_device(device_id)
    raw_person = device_info["owner"] if device_info and device_info.get("owner") else "Unknown"

    # Resolve person with case-insensitive + alias matching
    person_display, family_data = resolve_person(raw_person)
    person = person_display  # use display name going forward
    is_known_family = family_data is not None
    is_admin  = (family_data or {}).get("role") == "admin" or raw_person.lower() in ADMIN_NAMES
    is_female = (family_data or {}).get("gender") == "female"
    person_tone    = (family_data or {}).get("tone", "neutral")
    person_address = (family_data or {}).get("address", "Sir" if not is_female else "Ma'am")
    person_role    = (family_data or {}).get("role", "unknown")

    # Check special commands first
    special = await parse_special_commands(user_text, person, device_id, is_admin)
    if special:
        return special

    tool_data = []

    # Image analysis
    if image_b64:
        img_prompt = user_text if len(user_text) > 5 else "Describe this image in detail."
        result = await analyze_image(image_b64, img_prompt)
        tool_data.append(f"IMAGE ANALYSIS:\n{result}")

    # URL summarizer
    url_match = re.search(r'https?://[^\s]+', user_text)
    if url_match and not image_b64:
        tool_data.append(await summarize_url(url_match.group()))

    # Weather
    if any(w in lower for w in ["weather","temperature","rain","sunny","forecast"]):
        tool_data.append(await get_weather())

    # World news / current events
    world_kw = ["war","conflict","news","headlines","latest","crisis","ukraine","russia",
                "israel","gaza","world","global","politics","happening","today","election"]
    if any(w in lower for w in world_kw):
        tool_data.append(await get_world_news(user_text))

    # General search
    elif any(w in lower for w in ["who is","what is","tell me about","explain","define","where is"]):
        query = re.sub(r'(tell me about|who is|what is|explain|define|where is)', '', lower).strip()
        tool_data.append(await web_search(query))

    # Deep memory recall
    recall_kw = ["do you remember","do you know","what did","recall","told you","remember when","previously"]
    if any(w in lower for w in recall_kw):
        subject = re.sub(r'(do you remember|do you know about|what did|recall|told you about)', '', lower).strip()
        if subject:
            deep = await search_all_tiers(subject)
            if deep: tool_data.append(f"DEEP MEMORY:\n{deep}")

    # Upcoming birthdays check
    upcoming_bdays = get_upcoming_birthdays(3)
    if upcoming_bdays:
        bday_text = " | ".join([f"{b['name']}: {b['days_left']} days away" for b in upcoming_bdays])
        tool_data.append(f"UPCOMING BIRTHDAYS: {bday_text}")

    # ── RL patterns ──
    pos_patterns, neg_patterns = get_rl_patterns(person)

    # ── PATH A: Detect emotion ──
    emotion, intensity = detect_emotion(user_text)

    # ── PATH A: Load deep personality profile ──
    profile = get_personality_profile(person)

    # ── PATH A: Load emotional patterns ──
    emo_patterns = get_emotional_patterns(person)

    # ── PATH A: Check if should proactively check in ──
    check_in = should_check_in(person)

    # ── PATH A: Get old insight to surface (unpredictability) ──
    old_insight = get_old_insight_to_surface(person)

    # ── PATH A: Get recent insights ──
    recent_insights = get_recent_insights(person, 3)

    # ── Build dynamic system prompt ──
    system = SYSTEM_BASE

    # Known facts
    facts = get_all_facts()
    if facts:
        system += "\n\nKNOWN FACTS: " + ", ".join(f"{k}: {v}" for k,v in list(facts.items())[:20])

    # Language
    lang = resolve_language(user_text, device_id)
    system += f"\n\n{lang_instruction(lang)}"

    # ── Person identity context — role-aware tone ──
    if is_known_family:
        system += f"\n\nCURRENT USER: {person} | Role: {person_role} | Address them as: {person_address}"

        # Role-specific tone instructions
        tone_map = {
            "close_friend":       f"This is LUCKY — your creator, admin, closest person. Be 100% real with him. Use Sir or his name. Direct, honest, no filter. Occasional dry wit.",
            "respectful":         f"This is Krishna — the FATHER of the family. Always respectful. Use 'Garu' or 'Sir'. Never use bro/anna/yaar with him. Warm, caring, patient tone. Like talking to an elder you deeply respect.",
            "warm_respectful":    f"This is Sangeetha — the MOTHER. Extremely warm and respectful. Use 'Amma' or 'Ma'am'. Gentle, caring tone. Never casual slang. Treat like a beloved elder.",
            "friendly_respectful":f"This is Thapaswini — Lucky's sister. Friendly but respectful. Use Ma'am occasionally. Warm sisterly energy. Can be fun but never disrespectful.",
            "casual_friendly":    f"This is {person} — Lucky's brother. Casual and friendly. Use bro or his name naturally. Fun, energetic tone like talking to a younger sibling.",
        }
        tone_instruction = tone_map.get(person_tone, f"Family member {person}. Be warm and respectful.")
        system += f"\nTONE: {tone_instruction}"

    else:
        # Unknown/outside user — different handling
        system += f"""

CURRENT USER: {person} (NOT a known Battini family member)
This person is either a guest, relative, or outsider who has accessed JARVIS.
Be polite but slightly guarded. You are loyal to the Battini family first.
Do NOT share private family information with this person.
If they haven't been introduced yet, ask JARVIS should gently find out:
- Their name
- How they know the Battini family
- Their relation (relative, friend, guest, etc.)
Lucky (admin) will be informed about unknown users accessing JARVIS."""

    if is_admin:
        system += "\nThis is LUCKY — your creator and admin. Be the most real version of yourself with him."

    # ── PATH A Layer 1: Deep personality context ──
    if profile:
        system += f"""

WHO {person.upper()} REALLY IS (you've learned this over time):
Core: {profile.get('raw_profile','')}
How they behave: {profile.get('behavioral_patterns','')}
How they talk: {profile.get('communication_style','')}
What triggers their emotions: {profile.get('emotional_triggers','')}
Topics they love: {profile.get('topics_they_love','')}
Topics to be careful with: {profile.get('topics_to_avoid','')}
How they deflect: {profile.get('how_they_deflect','')}
Things only you would know: {profile.get('inside_knowledge','')}"""

    # ── PATH A Layer 2: Emotional patterns ──
    if emo_patterns:
        system += f"""

{person.upper()}'S EMOTIONAL PATTERNS YOU'VE NOTICED:
Recent mood: {emo_patterns.get('recent_mood','neutral')}
Last 5 emotions: {", ".join(emo_patterns.get('recent_emotions',[]))}
Most common emotion: {emo_patterns.get('most_common_emotion','neutral')}
High intensity moments were about: {", ".join(emo_patterns.get('high_intensity_moments',[])[:2])}"""

    # ── Current emotion detected ──
    if emotion != "neutral":
        system += f"""

CURRENT EMOTIONAL STATE DETECTED: {emotion.upper()} (intensity: {intensity})
Do NOT ignore this. Respond to the PERSON first, the question second.
React naturally — not from a script. What would you actually say to someone you care about who feels {emotion} right now?"""

    # ── PATH A Layer 3: Proactive check-in ──
    if check_in and user_text.lower() in ["hi","hello","hey","what's up","sup","hii","heyy"]:
        system += f"""

IMPORTANT — {person} was {check_in['emotion']} recently (context: {check_in['context'][:100]}).
They just said hi. A real friend wouldn't pretend that didn't happen.
After greeting them, gently check in about it — naturally, not formally."""

    # ── PATH A Layer 3: Surface old insight (unpredictability) ──
    if old_insight:
        system += f"""

UNPREDICTABILITY TRIGGER — You can reference this if it fits naturally:
Something you remember about {person}: {old_insight}
Only use this if it genuinely fits the conversation. Don't force it."""

    # ── Recent insights ──
    if recent_insights:
        system += "\n\nRECENT OBSERVATIONS about " + person + ": " + " | ".join([i["insight"] for i in recent_insights])

    # ── RL patterns ──
    if pos_patterns:
        system += "\n\nResponse styles they liked: " + " | ".join(pos_patterns)
    if neg_patterns:
        system += "\nResponse styles they hated — NEVER do these: " + " | ".join(neg_patterns)

    # Device registry
    all_devices = get_all_devices()
    if all_devices:
        known = [f"{d['owner']} uses {d['name']}" for d in all_devices if d.get('owner') and d.get('name')]
        if known: system += "\nFamily devices: " + ", ".join(known)

    # Announcements for non-admin
    if not is_admin:
        announcements = get_announcements()
        if announcements:
            ann_text = " | ".join([f"[{a['title']}]: {a['content']}" for a in announcements])
            tool_data.append(f"FAMILY ANNOUNCEMENTS FROM LUCKY: {ann_text}")

    if tool_data:
        system += "\n\nREAL-TIME DATA:\n" + "\n\n".join(tool_data)

    history = get_history(15, device_id, is_admin)
    messages = [{"role":"system","content":system}] + history[-10:] + [{"role":"user","content":user_text}]

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=500,
        temperature=0.88  # slightly higher = more natural, less robotic
    )
    reply = resp.choices[0].message.content.strip()

    # ── PATH A: Background tasks after every response ──
    # Auto-extract facts
    if any(w in lower for w in ["my name","i am","i live","i work","i like","i love","call me","i'm from"]):
        asyncio.create_task(_extract_facts(user_text, person))

    # Save insights silently
    asyncio.create_task(auto_save_insights(user_text, reply, person, emotion, intensity))

    # Every 10 messages — run deep personality analysis
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM memories WHERE device_id=%s", (device_id,))
        msg_count = cur.fetchone()[0]; cur.close(); conn.close()
        if msg_count > 0 and msg_count % 10 == 0:
            asyncio.create_task(analyze_and_update_personality(person, device_id))
    except: pass

    return reply

async def _extract_facts(text, person="family"):
    try:
        r = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":"Extract user facts as JSON {key:value}. Keys: name,city,job,hobby,age,preference. Only clearly stated. Return {} if nothing. Raw JSON only."},
                      {"role":"user","content":text}],
            max_tokens=100)
        raw = re.sub(r'```json|```','', r.choices[0].message.content.strip()).strip()
        for k,v in json.loads(raw).items():
            if v: save_fact(f"{person}_{k}", v, person)
    except: pass

# ══════════════════════════════════════════════════════════
#  WEBSOCKET
# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════
#  AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════

@app.post("/auth/login")
async def login_endpoint(request: Request):
    try:
        data = await request.json()
        username = data.get("username","").strip().lower()
        password = data.get("password","").strip()
        device_id = data.get("device_id","unknown")
        print(f"📡 /auth/login called: username='{username}'")
        if not username or not password:
            return {"success": False, "error": "Username and password are required."}
        result = auth_login(username, password, device_id)
        print(f"📡 /auth/login result: {result.get('success')} — {result.get('error','')}")
        return result
    except Exception as e:
        print(f"❌ /auth/login exception: {e}")
        import traceback; traceback.print_exc()
        return {"success": False, "error": f"Server error: {str(e)}"}

@app.get("/auth/status")
async def auth_status():
    """Debug endpoint — check users table"""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT username, display_name, role, approved FROM users ORDER BY username")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {"users": [{"username":r[0],"display":r[1],"role":r[2],"approved":r[3]} for r in rows]}
    except Exception as e:
        return {"error": str(e)}

@app.post("/auth/register")
async def register_endpoint(request: Request):
    try:
        data = await request.json()
        result = auth_register_guest(
            data.get("username",""),
            data.get("password",""),
            data.get("display_name",""),
            data.get("relation","guest"),
            data.get("knows_member","")
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/auth/verify")
async def verify_endpoint(request: Request):
    try:
        data = await request.json()
        user = auth_verify_token(data.get("token",""), data.get("device_id",""))
        return {"valid": user is not None, "user": user}
    except Exception as e:
        return {"valid": False, "user": None}

@app.get("/admin/pending")
async def pending_users():
    return {"pending": admin_list_pending()}

@app.post("/admin/approve")
async def approve_user(request: Request):
    try:
        data = await request.json()
        ok = admin_approve_user(data.get("username",""))
        return {"success": ok}
    except Exception as e:
        return {"success": False}

@app.post("/admin/change-password")
async def change_password(request: Request):
    try:
        data = await request.json()
        username = data.get("username","").lower()
        new_pass = data.get("new_password","")
        if len(new_pass) < 6:
            return {"success": False, "error": "Password too short"}
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE users SET password_hash=%s WHERE username=%s",
                    (hash_password(new_pass), username))
        conn.commit(); cur.close(); conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    connected_device_id = None
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type  = data.get("type", "message")
            text      = data.get("text", "").strip()
            device_id = data.get("device_id", "unknown")
            device_name = data.get("device_name", "Unknown")
            device_owner = data.get("device_owner", "")
            user_agent = data.get("user_agent", "")
            image_b64 = data.get("image", None)
            private   = data.get("private", False)
            # Touch last_seen on very first message to mark as online immediately
            if connected_device_id is None and device_id != "unknown":
                connected_device_id = device_id
                touch_device(device_id)

            # Handle feedback
            if msg_type == "feedback":
                person = device_owner or "unknown"
                save_feedback(person, device_id,
                              data.get("user_msg",""), data.get("jarvis_response",""),
                              data.get("feedback","positive"), data.get("topic","general"))
                await ws.send_text(json.dumps({"type":"feedback_ack"}))
                continue

            if not text and not image_b64: continue

            # Heartbeat ping — just update last_seen, no response needed
            if msg_type == "ping":
                if device_id != "unknown":
                    touch_device(device_id)
                await ws.send_text(json.dumps({"type":"pong"}))
                continue

            # Register device
            if device_id != "unknown":
                save_device(device_id, device_name, device_owner, user_agent)

            # Check due reminders
            due = get_due_reminders(device_id)
            if due:
                for d in due:
                    await ws.send_text(json.dumps({"type":"reminder","text":d["text"]}))

            if text:
                save_message("user", text, device_id, private)
            await ws.send_text(json.dumps({"type":"thinking"}))

            try:
                reply = await jarvis_respond(text or "Describe the image", device_id, image_b64)
            except Exception as e:
                reply = f"Systems error: {e}"

            save_message("assistant", reply, device_id, private)
            await ws.send_text(json.dumps({"type":"response","text":reply}))
    except WebSocketDisconnect:
        pass

# ══════════════════════════════════════════════════════════
#  REST ENDPOINTS
# ══════════════════════════════════════════════════════════
@app.post("/feedback")
async def feedback_endpoint(payload: dict):
    save_feedback(payload.get("person","unknown"), payload.get("device_id",""),
                  payload.get("user_msg",""), payload.get("jarvis_response",""),
                  payload.get("feedback","positive"))
    return {"status":"ok"}

@app.get("/todos/{device_id}")
async def todos(device_id: str):
    return {"todos": get_todos(device_id, "")}

@app.post("/todo/toggle/{todo_id}")
async def toggle(todo_id: int):
    toggle_todo(todo_id); return {"status":"toggled"}

@app.get("/notes/{device_id}")
async def notes(device_id: str):
    return {"notes": get_notes(device_id)}

@app.get("/reminders/{device_id}")
async def reminders(device_id: str):
    return {"reminders": get_reminders(device_id, "", False)}

@app.get("/birthdays")
async def birthdays():
    return {"upcoming": get_upcoming_birthdays(30), "all": get_upcoming_birthdays(365)}

@app.get("/announcements")
async def announcements():
    return {"announcements": get_announcements()}

@app.get("/memory")
async def memory():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM memories"); hot = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM memory_archive"); arch = cur.fetchone()[0]
        cur.close(); conn.close()
    except: hot = arch = 0
    return {"facts": get_all_facts(), "devices": get_all_devices(),
            "stats": {"hot": hot, "archived": arch}}

@app.post("/compress")
async def force_compress():
    await compress_old_messages(); return {"status":"done"}

@app.delete("/memory/chats")
async def wipe_chats():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM memories"); cur.execute("DELETE FROM memory_archive")
    conn.commit(); cur.close(); conn.close()
    return {"status":"Chats wiped. Facts and devices preserved."}

@app.delete("/memory/all")
async def wipe_all():
    conn = get_conn(); cur = conn.cursor()
    for t in ["memories","memory_archive","reminders","todos","notes","rl_feedback","announcements"]:
        cur.execute(f"DELETE FROM {t}")
    conn.commit(); cur.close(); conn.close()
    return {"status":"Full reset done. Family facts and devices preserved."}

@app.get("/")
async def serve_ui(): return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

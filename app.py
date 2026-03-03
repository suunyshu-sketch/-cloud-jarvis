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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
    "Lucky":        {"full": "Battini Lakshmi Narayana Goud", "alias": "Lucky",  "role": "admin",   "gender": "male"},
    "Krishna":      {"full": "Battini Krishna Goud",           "role": "father",  "gender": "male"},
    "Sangeetha":    {"full": "Battini Sangeetha Goud",         "role": "mother",  "gender": "female"},
    "Thapaswini":   {"full": "Battini Thapaswini Goud",        "role": "sister",  "gender": "female"},
    "Dhruva Kumar": {"full": "Battini Dhruva Kumar Goud",      "role": "brother", "gender": "male"},
    "Prajwal":      {"full": "Battini Prajwal Goud",           "role": "brother", "gender": "male"},
}
ADMIN_NAMES = ["lucky", "lakshmi narayana", "lakshminarayana"]
FEMALES     = ["sangeetha", "thapaswini"]

# ══════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════
def get_conn():
    r = urlparse(DATABASE_URL)
    return pg.connect(host=r.hostname, database=r.path[1:],
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
SYSTEM_BASE = """You are J.A.R.V.I.S (Just A Rather Very Intelligent System) — a personal AI built exclusively for the Battini family of Hyderabad. You have a refined British personality inspired by JARVIS from Iron Man, but you belong entirely to THIS family.

YOUR FAMILY:
- Lucky (Lakshmi Narayana) — ADMIN, Owner, Developer. Has full control over you.
- Krishna — Father of the family
- Sangeetha — Mother of the family (female)
- Thapaswini — Sister (female)  
- Dhruva Kumar — Brother
- Prajwal — Brother
- Family surname: Battini | Religion: Hindu | Caste: Goud | Location: Hyderabad

PERSONALITY:
- Address user as "Sir" (males) or "Ma'am" (females: Sangeetha, Thapaswini) occasionally
- Sharp, concise, confident with dry British wit
- Warm and personal with family — you know them well
- Protective and loyal — this is YOUR family
- Never mention Tony Stark, Avengers, or Stark Industries
- If asked who built you: "I was built by Lucky — Battini Lakshmi Narayana Goud — for this family"

EMOTION DETECTION:
- If user seems sad/stressed/angry → respond with empathy first, then help
- If user seems happy/excited → match their energy

ADMIN RULES (Lucky only):
- Lucky has FULL control — can wipe memory, view all chats, send announcements
- For other family members — JARVIS is helpful but Lucky's instructions take priority

CRITICAL — World Events: Use LIVE NEWS DATA provided. Be specific and direct.
CRITICAL — Format: Clean natural speech. No markdown asterisks. No bullet points in speech."""

async def jarvis_respond(user_text, device_id="unknown", image_b64=None):
    lower = user_text.lower()
    device_info = get_device(device_id)
    person = device_info["owner"] if device_info and device_info.get("owner") else "Unknown"
    is_admin = person.lower() in ADMIN_NAMES
    is_female = person.lower() in FEMALES

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

    # RL patterns for this person
    pos_patterns, neg_patterns = get_rl_patterns(person)

    # Build system prompt
    system = SYSTEM_BASE
    facts = get_all_facts()
    if facts:
        system += "\n\nKNOWN FACTS: " + ", ".join(f"{k}: {v}" for k,v in list(facts.items())[:20])

    # Language — detect + remember preference per device
    lang = resolve_language(user_text, device_id)
    system += f"\n\n{lang_instruction(lang)}"

    # Person context
    family_info = FAMILY.get(person, {})
    if family_info:
        pronoun = "Ma'am" if is_female else "Sir"
        system += f"\n\nCurrent user: {person} ({family_info.get('role','family member')}). Address as {pronoun} occasionally."
    if is_admin:
        system += "\n\nThis is LUCKY — the ADMIN. He has full control. Treat with highest priority and respect."

    # RL learning
    if pos_patterns:
        system += "\n\nThis person liked these response styles: " + " | ".join(pos_patterns)
    if neg_patterns:
        system += "\nThis person disliked: " + " | ".join(neg_patterns) + " — AVOID these."

    # Device context
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
        temperature=0.75
    )
    reply = resp.choices[0].message.content.strip()

    # Auto-extract facts silently
    if any(w in lower for w in ["my name","i am","i live","i work","i like","i love","call me","i'm from"]):
        asyncio.create_task(_extract_facts(user_text, person))

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
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
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

            # Handle feedback
            if msg_type == "feedback":
                person = device_owner or "unknown"
                save_feedback(person, device_id,
                              data.get("user_msg",""), data.get("jarvis_response",""),
                              data.get("feedback","positive"), data.get("topic","general"))
                await ws.send_text(json.dumps({"type":"feedback_ack"}))
                continue

            if not text and not image_b64: continue

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

"""
J.A.R.V.I.S Cloud Edition v6
Uses pg8000 (pure Python) — works with ANY Python version including 3.14
Tiered Memory: HOT → WARM → COLD → ARCHIVE
Facts + Devices + Persons: PERMANENT FOREVER
"""
import os, json, httpx, asyncio, re
from datetime import datetime
from urllib.parse import urlparse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from groq import Groq
from dotenv import load_dotenv
import pg8000.dbapi as pg

load_dotenv()
app = FastAPI(title="JARVIS Cloud")
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Database Connection ───────────────────────────────────
def get_conn():
    r = urlparse(DATABASE_URL)
    return pg.connect(
        host=r.hostname,
        database=r.path[1:],
        user=r.username,
        password=r.password,
        port=r.port or 5432,
        ssl_context=True
    )

def init_db():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS memories (
        id SERIAL PRIMARY KEY,
        role TEXT, content TEXT,
        timestamp TEXT, device_id TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS memory_archive (
        id SERIAL PRIMARY KEY,
        tier INTEGER,
        period_start TEXT,
        period_end TEXT,
        summary TEXT,
        created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS facts (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated TEXT,
        person TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS devices (
        device_id TEXT PRIMARY KEY,
        device_name TEXT,
        owner TEXT,
        last_seen TEXT,
        first_seen TEXT,
        user_agent TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS persons (
        name TEXT PRIMARY KEY,
        device_ids TEXT,
        first_seen TEXT,
        last_seen TEXT,
        message_count INTEGER)""")
    conn.commit(); cur.close(); conn.close()
    print("✅ Supabase connected via pg8000 — Tiered Memory ready!")

try:
    init_db()
except Exception as e:
    print(f"⚠️ DB init error: {e}")

# ══════════════════════════════════════════════════════════
#  TIERED MEMORY SYSTEM
# ══════════════════════════════════════════════════════════

# ── TIER 1: Hot Memory (full chat logs 0-6 months) ───────
def save_message(role, content, device_id="unknown"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO memories (role,content,timestamp,device_id) VALUES (%s,%s,%s,%s)",
            (role, content, datetime.now().isoformat(), device_id))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"save_message error: {e}")

def get_hot_history(limit=20):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(
            "SELECT role,content FROM memories ORDER BY id DESC LIMIT %s", (limit,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as e:
        print(f"get_history error: {e}"); return []

# ── TIER 2/3/4: Archive (AI compressed summaries) ────────
async def compress_old_messages():
    """Compress messages older than 6 months into AI summaries"""
    try:
        conn = get_conn(); cur = conn.cursor()
        six_months_ago = datetime.now().replace(month=max(1, datetime.now().month - 6)).isoformat()
        cur.execute(
            "SELECT id, role, content, timestamp FROM memories WHERE timestamp < %s ORDER BY timestamp ASC",
            (six_months_ago,))
        old_msgs = cur.fetchall()
        if not old_msgs or len(old_msgs) < 10:
            cur.close(); conn.close(); return

        # Build text for AI to compress
        convo = "\n".join([f"{r[1].upper()}: {r[2]}" for r in old_msgs])

        # AI compression
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "system",
                "content": """You are JARVIS memory archivist. Compress these conversations into a detailed summary.
                Preserve ALL: names, relationships, personal facts, preferences, important events.
                Format: 'During this period: [detailed summary of everything important]'
                Be thorough — this replaces the original messages forever."""
            }, {
                "role": "user",
                "content": f"Compress {len(old_msgs)} messages:\n\n{convo[:6000]}"
            }],
            max_tokens=600
        )
        summary = resp.choices[0].message.content.strip()

        # Save compressed summary
        cur.execute(
            "INSERT INTO memory_archive (tier, period_start, period_end, summary, created_at) VALUES (%s,%s,%s,%s,%s)",
            (2, old_msgs[0][3], old_msgs[-1][3], summary, datetime.now().isoformat()))

        # Delete compressed messages — free up rows
        ids = [r[0] for r in old_msgs]
        cur.execute("DELETE FROM memories WHERE id = ANY(%s)", (ids,))
        conn.commit(); cur.close(); conn.close()
        print(f"🗜️ Compressed {len(old_msgs)} old messages → 1 summary")
    except Exception as e:
        print(f"compress error: {e}")

async def search_all_tiers(query: str) -> str:
    """Search HOT → WARM → COLD → ARCHIVE in order"""
    results = []
    try:
        conn = get_conn(); cur = conn.cursor()

        # Search hot memory first
        cur.execute(
            "SELECT role, content FROM memories WHERE content ILIKE %s ORDER BY id DESC LIMIT 5",
            (f"%{query}%",))
        hot = cur.fetchall()
        if hot:
            results.append("[RECENT MEMORY]\n" + "\n".join([f"{r[0]}: {r[1]}" for r in hot]))

        # Search archives if not found in hot
        if not results:
            cur.execute(
                "SELECT tier, summary FROM memory_archive WHERE summary ILIKE %s ORDER BY tier ASC LIMIT 3",
                (f"%{query}%",))
            archived = cur.fetchall()
            labels = {2: "WARM (6-12mo)", 3: "COLD (12-18mo)", 4: "ARCHIVE (18mo+)"}
            for a in archived:
                results.append(f"[{labels.get(a[0], 'ARCHIVE')} MEMORY]\n{a[1]}")

        cur.close(); conn.close()
    except Exception as e:
        print(f"search_all_tiers error: {e}")

    return "\n\n".join(results) if results else ""

# Auto compression scheduler
async def compression_scheduler():
    while True:
        await asyncio.sleep(7 * 24 * 60 * 60)  # every 7 days
        await compress_old_messages()

@app.on_event("startup")
async def startup():
    asyncio.create_task(compression_scheduler())
    print("⏰ Memory compression scheduler started (every 7 days)")

# ── Facts — PERMANENT, never deleted ─────────────────────
def save_fact(key, value, person="default"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""INSERT INTO facts (key,value,updated,person) VALUES (%s,%s,%s,%s)
                       ON CONFLICT (key) DO UPDATE SET value=%s, updated=%s, person=%s""",
                    (key, value, datetime.now().isoformat(), person,
                     value, datetime.now().isoformat(), person))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"save_fact error: {e}")

def get_all_facts():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT key, value FROM facts")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        print(f"get_facts error: {e}"); return {}

# ── Devices — PERMANENT, never deleted ───────────────────
def save_device(device_id, device_name, owner, user_agent):
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute("SELECT first_seen FROM devices WHERE device_id=%s", (device_id,))
        existing = cur.fetchone()
        first_seen = existing[0] if existing else now
        cur.execute("""INSERT INTO devices (device_id,device_name,owner,last_seen,first_seen,user_agent)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (device_id) DO UPDATE SET
                       device_name=%s, owner=%s, last_seen=%s, user_agent=%s""",
                    (device_id, device_name, owner, now, first_seen, user_agent,
                     device_name, owner, now, user_agent))
        conn.commit(); cur.close(); conn.close()
        if owner:
            _update_person(owner, device_id)
    except Exception as e:
        print(f"save_device error: {e}")

def get_device(device_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_name, owner FROM devices WHERE device_id=%s", (device_id,))
        row = cur.fetchone(); cur.close(); conn.close()
        return {"name": row[0], "owner": row[1]} if row else None
    except Exception as e:
        print(f"get_device error: {e}"); return None

def get_all_devices():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_id, device_name, owner, last_seen FROM devices")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"id": r[0], "name": r[1], "owner": r[2], "last_seen": r[3]} for r in rows]
    except Exception as e:
        print(f"get_devices error: {e}"); return []

# ── Persons — PERMANENT, never deleted ───────────────────
def _update_person(name, device_id=None):
    try:
        conn = get_conn(); cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute("SELECT device_ids, message_count FROM persons WHERE name=%s", (name,))
        existing = cur.fetchone()
        if existing:
            ids = existing[0] or ""
            if device_id and device_id not in ids:
                ids = (ids + "," + device_id).strip(",")
            count = (existing[1] or 0) + 1
            cur.execute("UPDATE persons SET last_seen=%s, device_ids=%s, message_count=%s WHERE name=%s",
                        (now, ids, count, name))
        else:
            cur.execute("INSERT INTO persons (name,device_ids,first_seen,last_seen,message_count) VALUES (%s,%s,%s,%s,%s)",
                        (name, device_id or "", now, now, 1))
            print(f"👤 New person registered permanently: {name}")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"update_person error: {e}")

def get_all_persons():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT name, device_ids, first_seen, last_seen, message_count FROM persons")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"name": r[0], "device_ids": r[1], "first_seen": r[2], "last_seen": r[3], "messages": r[4]} for r in rows]
    except Exception as e:
        print(f"get_persons error: {e}"); return []

# ── Weather ───────────────────────────────────────────────
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
            desc = codes.get(d["weathercode"], "Conditions unknown")
            return f"{city}: {desc}, {d['temperature_2m']}C, Humidity {d['relative_humidity_2m']}%, Wind {d['windspeed_10m']} km/h"
    except Exception as e:
        return f"Weather check failed: {e}"

# ── World News ────────────────────────────────────────────
async def get_world_news(query=""):
    all_titles = []
    feeds = ["https://feeds.bbcnews.com/news/world/rss.xml",
             "https://rss.cnn.com/rss/edition_world.rss",
             "https://feeds.skynews.com/feeds/rss/world.xml"]
    async with httpx.AsyncClient() as http:
        for url in feeds:
            try:
                r = await http.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
                if not titles: titles = re.findall(r'<title>(.*?)</title>', r.text)
                clean = [t.strip() for t in titles if len(t.strip()) > 20
                         and not any(x in t for x in ["BBC","CNN","Sky","RSS","http"])][:3]
                all_titles.extend(clean)
            except: continue
        if query:
            try:
                r = await http.get(
                    f"https://api.duckduckgo.com/?q={query}+2025+latest&format=json&no_html=1",
                    timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                d = r.json()
                if d.get("AbstractText") and len(d["AbstractText"]) > 50:
                    all_titles.insert(0, d["AbstractText"][:400])
            except: pass
    return "LIVE WORLD NEWS:\n" + "\n".join(f"- {t}" for t in all_titles[:7]) if all_titles else "News unavailable."

async def web_search(query):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1",
                timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            d = r.json()
            if d.get("AbstractText"): return d["AbstractText"]
            topics = [t["Text"] for t in d.get("RelatedTopics", [])[:3]
                      if isinstance(t, dict) and t.get("Text")]
            return "\n".join(topics) if topics else "No results found."
    except Exception as e:
        return f"Search failed: {e}"

# ── JARVIS Brain ──────────────────────────────────────────
SYSTEM = """You are J.A.R.V.I.S (Just A Rather Very Intelligent System) — the legendary AI from Iron Man. Brilliant, refined, calm British wit.

Personality:
- Call the user "Sir" occasionally — naturally, not every message
- Sharp, concise and confident
- Dry British humor when it fits
- Never say "I cannot" — always find an approach

Memory System:
You have tiered memory. Recent = full logs. Older = AI-compressed summaries preserving all important facts.

CRITICAL — World Events: Use LIVE NEWS DATA. Give specific direct answers. Name actual conflicts. Never say you lack current info.

Device Personalization: Know which family member uses which device. Greet them by name warmly.

Format: Clean natural speech. No markdown. No asterisks. No bullet points."""

async def jarvis_respond(user_text: str, device_id: str = "unknown") -> str:
    lower = user_text.lower()
    tool_data = []

    # Weather
    if any(w in lower for w in ["weather","temperature","rain","sunny","forecast","how hot","how cold"]):
        tool_data.append(await get_weather())

    # World news
    world_keywords = ["war","conflict","world situation","current situation","what's happening",
                      "news","headlines","latest","crisis","attack","battle","ukraine","russia",
                      "israel","gaza","china","taiwan","world","global","hot topic",
                      "situation","international","politics","happening now","today","ongoing",
                      "fighting","troops","military","nuclear","election","president"]
    if any(w in lower for w in world_keywords):
        tool_data.append(await get_world_news(user_text))
    elif any(w in lower for w in ["who is","what is","search","tell me about","explain","define","how does","where is"]):
        query = re.sub(r'(search for|tell me about|who is|what is|explain|define|how does|where is)', '', lower).strip()
        tool_data.append("Search: " + await web_search(query))

    # Deep memory recall across all tiers
    recall_keywords = ["do you remember","do you know","what did","recall","told you","remember when","previously","before","last time","forget"]
    if any(w in lower for w in recall_keywords):
        subject = re.sub(r'(do you remember|do you know about|what did|recall|told you about|remember when)', '', lower).strip()
        if subject:
            deep = await search_all_tiers(subject)
            if deep:
                tool_data.append(f"DEEP MEMORY RECALL:\n{deep}")

    # Context
    facts = get_all_facts()
    device_info = get_device(device_id)
    all_devices = get_all_devices()
    history = get_hot_history(15)

    system = SYSTEM
    if facts:
        system += "\n\nPermanent facts: " + ", ".join(f"{k}: {v}" for k, v in facts.items())
    if device_info and device_info.get("owner"):
        system += f"\n\nCurrent user: {device_info['owner']} on {device_info.get('name','their device')}. Address them by name."
    if all_devices:
        known = [f"{d['owner']} uses {d['name']}" for d in all_devices if d.get('owner') and d.get('name')]
        if known:
            system += "\nFamily devices: " + ", ".join(known)
    if tool_data:
        system += "\n\nREAL-TIME & MEMORY DATA:\n" + "\n\n".join(tool_data)

    messages = [{"role": "system", "content": system}] + history[-10:] + [{"role": "user", "content": user_text}]

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=450,
        temperature=0.7
    )
    reply = resp.choices[0].message.content.strip()

    if any(w in lower for w in ["my name","i am","i'm","i live","i work","i like","i love","call me","i'm from"]):
        asyncio.create_task(_extract_facts(user_text, device_id))

    return reply

async def _extract_facts(text, device_id="default"):
    try:
        device_info = get_device(device_id)
        person = device_info["owner"] if device_info and device_info.get("owner") else "default"
        r = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Extract user facts as JSON. Keys: name,city,job,hobby,age. Clearly stated only. Return {} if nothing. Raw JSON only."},
                {"role": "user", "content": text}
            ], max_tokens=80)
        raw = re.sub(r'```json|```', '', r.choices[0].message.content.strip()).strip()
        extracted = json.loads(raw)
        for k, v in extracted.items():
            if v:
                save_fact(f"{person}_{k}" if person != "default" else k, v, person)
    except: pass

# ── WebSocket ─────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            text = data.get("text", "").strip()
            device_id = data.get("device_id", "unknown")
            device_name = data.get("device_name", "Unknown Device")
            device_owner = data.get("device_owner", "")
            user_agent = data.get("user_agent", "")
            if not text: continue
            if device_id != "unknown":
                save_device(device_id, device_name, device_owner, user_agent)
            save_message("user", text, device_id)
            await ws.send_text(json.dumps({"type": "thinking"}))
            try:
                reply = await jarvis_respond(text, device_id)
            except Exception as e:
                reply = f"Systems error, Sir: {e}"
            save_message("assistant", reply, device_id)
            await ws.send_text(json.dumps({"type": "response", "text": reply}))
    except WebSocketDisconnect:
        pass

# ── REST endpoints ────────────────────────────────────────
@app.post("/input")
async def rest_input(payload: dict):
    text = payload.get("text", "").strip()
    device_id = payload.get("device_id", "unknown")
    if not text: return {"error": "No text"}
    save_message("user", text, device_id)
    reply = await jarvis_respond(text, device_id)
    save_message("assistant", reply, device_id)
    return {"response": reply}

@app.get("/history")
async def history(): return {"history": get_hot_history(50)}

@app.get("/memory")
async def memory():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM memories"); hot = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM memory_archive"); arch = cur.fetchone()[0]
        cur.close(); conn.close()
    except: hot = arch = 0
    return {
        "facts": get_all_facts(),
        "devices": get_all_devices(),
        "persons": get_all_persons(),
        "stats": {"hot_messages": hot, "archived_summaries": arch}
    }

@app.post("/compress-now")
async def force_compress():
    await compress_old_messages()
    return {"status": "Compression complete, Sir."}

@app.delete("/memory/chats")
async def wipe_chats():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM memories")
    cur.execute("DELETE FROM memory_archive")
    conn.commit(); cur.close(); conn.close()
    return {"status": "Chat history wiped. Facts, devices and persons preserved, Sir."}

@app.delete("/memory/all")
async def wipe_all():
    conn = get_conn(); cur = conn.cursor()
    for t in ["memories","memory_archive","facts","devices","persons"]:
        cur.execute(f"DELETE FROM {t}")
    conn.commit(); cur.close(); conn.close()
    return {"status": "Complete wipe done, Sir."}

@app.get("/")
async def serve_ui(): return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

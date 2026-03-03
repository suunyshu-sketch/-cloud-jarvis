"""
J.A.R.V.I.S Cloud Edition v6
Tiered Memory Architecture:
  TIER 1 — HOT    (0-6 months):   Full chat logs
  TIER 2 — WARM   (6-12 months):  AI compressed summaries
  TIER 3 — COLD   (12-18 months): Further compressed
  TIER 4 — ARCHIVE(18+ months):   Ultra compressed

Search order: HOT → WARM → COLD → ARCHIVE
Facts + Devices: PERMANENT, never touched
"""
import os, json, httpx, asyncio, re
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from groq import Groq
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()
app = FastAPI(title="JARVIS Cloud")
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Database Setup ────────────────────────────────────────
def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_conn(); cur = conn.cursor()

    # TIER 1: Full chat logs (0-6 months)
    cur.execute("""CREATE TABLE IF NOT EXISTS memories (
        id SERIAL PRIMARY KEY,
        role TEXT, content TEXT,
        timestamp TIMESTAMPTZ DEFAULT NOW(),
        device_id TEXT)""")

    # TIER 2/3/4: Compressed memory summaries
    # tier: 2=warm(6-12mo), 3=cold(12-18mo), 4=archive(18mo+)
    cur.execute("""CREATE TABLE IF NOT EXISTS memory_archive (
        id SERIAL PRIMARY KEY,
        tier INTEGER,
        period_start TIMESTAMPTZ,
        period_end TIMESTAMPTZ,
        summary TEXT,
        device_id TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW())""")

    # PERMANENT: User facts (never deleted/compressed)
    cur.execute("""CREATE TABLE IF NOT EXISTS facts (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated TIMESTAMPTZ DEFAULT NOW(),
        person TEXT DEFAULT 'default')""")

    # PERMANENT: Devices (never deleted)
    cur.execute("""CREATE TABLE IF NOT EXISTS devices (
        device_id TEXT PRIMARY KEY,
        device_name TEXT, owner TEXT,
        last_seen TIMESTAMPTZ,
        first_seen TIMESTAMPTZ DEFAULT NOW(),
        user_agent TEXT)""")

    # PERMANENT: Person profiles (never deleted)
    cur.execute("""CREATE TABLE IF NOT EXISTS persons (
        name TEXT PRIMARY KEY,
        device_ids TEXT DEFAULT '',
        first_seen TIMESTAMPTZ DEFAULT NOW(),
        last_seen TIMESTAMPTZ DEFAULT NOW(),
        message_count INTEGER DEFAULT 0)""")

    conn.commit(); cur.close(); conn.close()
    print("✅ Supabase connected — Tiered Memory System ready!")

try:
    init_db()
except Exception as e:
    print(f"⚠️ DB init error: {e}")

# ══════════════════════════════════════════════════════════
#  TIERED MEMORY SYSTEM
# ══════════════════════════════════════════════════════════

# ── TIER 1: Hot Memory (0-6 months, full logs) ────────────
def save_message(role, content, device_id="unknown"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO memories (role,content,device_id) VALUES (%s,%s,%s)",
            (role, content, device_id))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"save_message error: {e}")

def get_hot_history(limit=20):
    """Get recent full chat history (TIER 1 — last 6 months)"""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT role, content FROM memories
                       WHERE timestamp > NOW() - INTERVAL '6 months'
                       ORDER BY id DESC LIMIT %s""", (limit,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception as e:
        print(f"get_hot_history error: {e}"); return []

# ── Archive: Compress old tier into summary ───────────────
async def compress_tier(months_start: int, months_end: int, tier: int):
    """
    AI compresses messages from a time window into a summary.
    e.g. compress_tier(6, 12, 2) = compress 6-12 month old messages into TIER 2
    """
    try:
        conn = get_conn(); cur = conn.cursor()

        # Get messages in this time window
        cur.execute("""
            SELECT role, content, timestamp, device_id FROM memories
            WHERE timestamp < NOW() - INTERVAL '%s months'
            AND   timestamp > NOW() - INTERVAL '%s months'
            ORDER BY timestamp ASC
        """, (months_start, months_end))
        messages = cur.fetchall()

        if not messages or len(messages) < 5:
            cur.close(); conn.close()
            return 0  # Not enough to compress

        # Build text for AI to summarize
        convo_text = "\n".join([
            f"[{m['timestamp']}] {m['role'].upper()}: {m['content']}"
            for m in messages
        ])

        # Use AI to create intelligent summary
        summary_resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "system",
                "content": """You are a memory archivist for JARVIS AI. 
                Compress these conversations into a detailed summary that preserves ALL important information:
                - Every person mentioned (names, relationships, preferences, details)
                - Important facts learned about users
                - Key events or topics discussed
                - Device usage patterns
                - Any personal information shared
                
                Write as: "During [time period], the following was learned and discussed: ..."
                Be thorough — this summary replaces the original messages forever.
                Preserve ALL names, facts, preferences and personal details mentioned."""
            }, {
                "role": "user",
                "content": f"Compress these {len(messages)} messages into a detailed memory summary:\n\n{convo_text[:6000]}"
            }],
            max_tokens=800
        )
        summary = summary_resp.choices[0].message.content.strip()

        # Save compressed summary to archive
        period_end = f"NOW() - INTERVAL '{months_start} months'"
        cur.execute("""
            INSERT INTO memory_archive (tier, period_start, period_end, summary)
            VALUES (%s, NOW() - INTERVAL '%s months', NOW() - INTERVAL '%s months', %s)
        """, (tier, months_end, months_start, summary))

        # Delete original messages that were compressed
        cur.execute("""
            DELETE FROM memories
            WHERE timestamp < NOW() - INTERVAL '%s months'
            AND   timestamp > NOW() - INTERVAL '%s months'
        """, (months_start, months_end))

        deleted = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        print(f"🗜️ TIER {tier}: Compressed {deleted} messages into 1 summary ({months_start}-{months_end} months ago)")
        return deleted

    except Exception as e:
        print(f"compress_tier error: {e}"); return 0

async def run_memory_compression():
    """
    Full compression cycle — runs automatically every 7 days.
    
    Flow:
    - Messages 6-12 months old  → compressed to TIER 2 summaries
    - Messages 12-18 months old → TIER 2 summaries re-compressed to TIER 3
    - Messages 18+ months old   → TIER 3 summaries re-compressed to TIER 4
    """
    print("🔄 Running memory compression cycle...")

    # Compress 6-12 month old full messages → TIER 2
    compressed = await compress_tier(6, 12, 2)

    # Re-compress existing TIER 2 summaries that are now 12-18 months old → TIER 3
    await recompress_archive_tier(2, 3, 12, 18)

    # Re-compress TIER 3 summaries that are 18+ months old → TIER 4
    await recompress_archive_tier(3, 4, 18, 999)

    print("✅ Memory compression cycle complete!")

async def recompress_archive_tier(from_tier: int, to_tier: int, months_min: int, months_max: int):
    """Re-compress old archive summaries into even smaller summaries"""
    try:
        conn = get_conn(); cur = conn.cursor()
        if months_max == 999:
            cur.execute("""SELECT id, summary FROM memory_archive
                           WHERE tier=%s AND period_end < NOW() - INTERVAL '%s months'""",
                        (from_tier, months_min))
        else:
            cur.execute("""SELECT id, summary FROM memory_archive
                           WHERE tier=%s
                           AND period_end BETWEEN NOW() - INTERVAL '%s months'
                           AND NOW() - INTERVAL '%s months'""",
                        (from_tier, months_max, months_min))

        old_summaries = cur.fetchall()
        if not old_summaries:
            cur.close(); conn.close(); return

        combined = "\n\n---\n\n".join([s["summary"] for s in old_summaries])
        ids = [s["id"] for s in old_summaries]

        # Re-compress with AI
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "system",
                "content": "Re-compress these memory summaries into one ultra-compact summary. Keep ALL names, personal facts, and important information. Remove only repetition and trivial chat."
            }, {
                "role": "user",
                "content": combined[:5000]
            }],
            max_tokens=600
        )
        new_summary = resp.choices[0].message.content.strip()

        # Save new compressed tier
        cur.execute("""INSERT INTO memory_archive (tier, period_start, period_end, summary)
                       VALUES (%s, NOW() - INTERVAL '999 months', NOW() - INTERVAL '%s months', %s)""",
                    (to_tier, months_min, new_summary))

        # Delete old summaries that were re-compressed
        cur.execute("DELETE FROM memory_archive WHERE id = ANY(%s)", (ids,))
        conn.commit(); cur.close(); conn.close()
        print(f"🗜️ Re-compressed {len(old_summaries)} TIER {from_tier} → 1 TIER {to_tier} summary")

    except Exception as e:
        print(f"recompress error: {e}")

# ── Tiered Memory Search ──────────────────────────────────
async def search_all_memory_tiers(query: str) -> str:
    """
    Search HOT → WARM → COLD → ARCHIVE in order.
    Stop as soon as relevant info found.
    This is called when JARVIS needs deep memory recall.
    """
    results = []

    # TIER 1: Search hot memory (recent full logs)
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT role, content FROM memories
                       WHERE content ILIKE %s
                       AND timestamp > NOW() - INTERVAL '6 months'
                       ORDER BY id DESC LIMIT 5""", (f"%{query}%",))
        hot = cur.fetchall(); cur.close(); conn.close()
        if hot:
            results.append(f"[RECENT MEMORY]\n" + "\n".join([f"{r['role']}: {r['content']}" for r in hot]))
    except Exception as e:
        print(f"hot search error: {e}")

    # TIER 2, 3, 4: Search archive summaries
    if not results:
        try:
            conn = get_conn(); cur = conn.cursor()
            cur.execute("""SELECT tier, summary FROM memory_archive
                           WHERE summary ILIKE %s
                           ORDER BY tier ASC, period_end DESC LIMIT 3""", (f"%{query}%",))
            archived = cur.fetchall(); cur.close(); conn.close()
            for a in archived:
                tier_name = {2: "WARM (6-12mo)", 3: "COLD (12-18mo)", 4: "ARCHIVE (18mo+)"}.get(a["tier"], "ARCHIVE")
                results.append(f"[{tier_name} MEMORY SUMMARY]\n{a['summary']}")
        except Exception as e:
            print(f"archive search error: {e}")

    return "\n\n".join(results) if results else ""

# ── Scheduled Compression (runs every 7 days) ─────────────
compression_task = None

async def compression_scheduler():
    """Run compression every 7 days automatically"""
    while True:
        await asyncio.sleep(7 * 24 * 60 * 60)  # 7 days
        await run_memory_compression()

@app.on_event("startup")
async def startup():
    global compression_task
    compression_task = asyncio.create_task(compression_scheduler())
    print("⏰ Memory compression scheduler started (runs every 7 days)")

# ── Facts (PERMANENT) ─────────────────────────────────────
def save_fact(key, value, person="default"):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""INSERT INTO facts (key,value,updated,person) VALUES (%s,%s,NOW(),%s)
                       ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated=NOW(), person=EXCLUDED.person""",
                    (key, value, person))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"save_fact error: {e}")

def get_all_facts():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT key, value FROM facts")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print(f"get_facts error: {e}"); return {}

# ── Devices (PERMANENT) ───────────────────────────────────
def save_device(device_id, device_name, owner, user_agent):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""INSERT INTO devices (device_id,device_name,owner,last_seen,user_agent)
                       VALUES (%s,%s,%s,NOW(),%s)
                       ON CONFLICT (device_id) DO UPDATE SET
                       device_name=EXCLUDED.device_name, owner=EXCLUDED.owner,
                       last_seen=NOW(), user_agent=EXCLUDED.user_agent""",
                    (device_id, device_name, owner, user_agent))
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
        return {"name": row["device_name"], "owner": row["owner"]} if row else None
    except Exception as e:
        print(f"get_device error: {e}"); return None

def get_all_devices():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_id, device_name, owner, last_seen FROM devices")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"get_devices error: {e}"); return []

def _update_person(name, device_id=None):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT device_ids FROM persons WHERE name=%s", (name,))
        existing = cur.fetchone()
        if existing:
            ids = existing["device_ids"] or ""
            if device_id and device_id not in ids:
                ids = (ids + "," + device_id).strip(",")
            cur.execute("UPDATE persons SET last_seen=NOW(), device_ids=%s, message_count=message_count+1 WHERE name=%s",
                        (ids, name))
        else:
            cur.execute("INSERT INTO persons (name,device_ids,message_count) VALUES (%s,%s,1)",
                        (name, device_id or ""))
            print(f"👤 New person registered permanently: {name}")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"update_person error: {e}")

def get_all_persons():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT name, device_ids, first_seen, last_seen, message_count FROM persons")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
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
                r = await http.get(f"https://api.duckduckgo.com/?q={query}+2025+latest&format=json&no_html=1",
                                   timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                d = r.json()
                if d.get("AbstractText") and len(d["AbstractText"]) > 50:
                    all_titles.insert(0, d["AbstractText"][:400])
            except: pass
    return "LIVE WORLD NEWS:\n" + "\n".join(f"- {t}" for t in all_titles[:7]) if all_titles else "News unavailable."

async def web_search(query):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1",
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
You have a tiered memory system. Recent memories are full conversations. Older memories are AI-compressed summaries that still preserve all important facts. When you recall something from a summary, acknowledge it naturally.

CRITICAL — World Events:
Use LIVE NEWS DATA provided. Give specific, direct answers. Name actual ongoing conflicts. Never say you lack current info.

Device Personalization:
Know which family member uses which device. Greet them by name.

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

    # General search
    elif any(w in lower for w in ["who is","what is","search","tell me about","explain","define","how does","where is"]):
        query = re.sub(r'(search for|tell me about|who is|what is|explain|define|how does|where is)', '', lower).strip()
        tool_data.append("Search: " + await web_search(query))

    # Deep memory recall — search ALL tiers
    memory_recall_keywords = ["do you remember","do you know","what did","who is","recall","forget",
                               "told you","remember when","last time","before","previously"]
    deep_memory = ""
    if any(w in lower for w in memory_recall_keywords):
        # Extract the subject to search for
        search_term = re.sub(r'(do you remember|do you know about|what did|recall|told you about)', '', lower).strip()
        if search_term:
            deep_memory = await search_all_memory_tiers(search_term)
            if deep_memory:
                tool_data.append(f"DEEP MEMORY RECALL (searched all tiers):\n{deep_memory}")

    # Build full context
    facts = get_all_facts()
    device_info = get_device(device_id)
    all_devices = get_all_devices()
    history = get_hot_history(15)

    system = SYSTEM
    if facts:
        system += "\n\nPermanent known facts: " + ", ".join(f"{k}: {v}" for k, v in facts.items())
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

    # Extract and save user facts permanently
    if any(w in lower for w in ["my name","i am","i'm","i live","i work","i like","i love","call me","i'm from"]):
        asyncio.create_task(_extract_facts(user_text, device_id))

    return reply

async def _extract_facts(text, device_id="default"):
    try:
        # Determine person from device
        device_info = get_device(device_id)
        person = device_info["owner"] if device_info and device_info.get("owner") else "default"

        r = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Extract user facts as JSON. Keys: name,city,job,hobby,age,relationship. Clearly stated facts only. Return {} if nothing. Raw JSON only."},
                {"role": "user", "content": text}
            ], max_tokens=80)
        raw = re.sub(r'```json|```', '', r.choices[0].message.content.strip()).strip()
        facts = json.loads(raw)
        for k, v in facts.items():
            if v:
                # Save with person tag so we know whose fact it is
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
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM memories"); hot = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM memory_archive"); archived = cur.fetchone()["c"]
    cur.close(); conn.close()
    return {
        "facts": get_all_facts(),
        "devices": get_all_devices(),
        "persons": get_all_persons(),
        "stats": {
            "hot_messages": hot,
            "archived_summaries": archived,
            "note": "Facts and devices are permanent — never deleted"
        }
    }

@app.post("/compress-now")
async def force_compress():
    """Manually trigger memory compression"""
    await run_memory_compression()
    return {"status": "Memory compression complete, Sir."}

@app.delete("/memory/chats")
async def wipe_chats_only():
    """Wipe only chat logs — keep facts, devices, persons"""
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM memories")
    cur.execute("DELETE FROM memory_archive")
    conn.commit(); cur.close(); conn.close()
    return {"status": "Chat history wiped. All facts, devices and person profiles preserved, Sir."}

@app.delete("/memory/all")
async def wipe_all():
    """Wipe everything including facts"""
    conn = get_conn(); cur = conn.cursor()
    for table in ["memories","memory_archive","facts","devices","persons"]:
        cur.execute(f"DELETE FROM {table}")
    conn.commit(); cur.close(); conn.close()
    return {"status": "Complete memory wipe done, Sir."}

@app.get("/")
async def serve_ui(): return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

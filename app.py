"""
╔══════════════════════════════════════════════╗
║   J.A.R.V.I.S  —  Cloud Edition             ║
║   FastAPI Backend + WebSocket + Memory       ║
╚══════════════════════════════════════════════╝
"""

import os, json, sqlite3, httpx, asyncio, re
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="JARVIS Cloud")
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

# ── Database ──────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT, content TEXT, timestamp TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS facts (
        key TEXT PRIMARY KEY, value TEXT, updated TEXT)""")
    conn.commit(); conn.close()

init_db()

def save_message(role, content):
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("INSERT INTO memories (role,content,timestamp) VALUES (?,?,?)",
                 (role, content, datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_history(limit=20):
    conn = sqlite3.connect("jarvis_memory.db")
    rows = conn.execute("SELECT role,content FROM memories ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def save_fact(key, value):
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("INSERT OR REPLACE INTO facts (key,value,updated) VALUES (?,?,?)",
                 (key, value, datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_all_facts():
    conn = sqlite3.connect("jarvis_memory.db")
    rows = conn.execute("SELECT key,value FROM facts").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

# ── Weather (Free, No API Key) ────────────────────────────
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
            return (f"{city}: {desc}, {d['temperature_2m']}°C, "
                    f"Humidity {d['relative_humidity_2m']}%, Wind {d['windspeed_10m']} km/h")
    except Exception as e:
        return f"Weather check failed: {e}"

# ── News (Free RSS) ───────────────────────────────────────
async def get_news():
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get("https://feeds.bbcnews.com/news/rss.xml", timeout=5,
                               headers={"User-Agent": "Mozilla/5.0"})
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
            titles = [t for t in titles if "BBC" not in t][:5]
            if not titles:
                titles = re.findall(r'<title>(.*?)</title>', r.text)[1:6]
            return "Latest headlines:\n" + "\n".join(f"• {t}" for t in titles)
    except Exception as e:
        return f"News unavailable: {e}"

# ── DuckDuckGo Search (Free) ──────────────────────────────
async def web_search(query):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1",
                               timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            d = r.json()
            if d.get("AbstractText"):
                return d["AbstractText"]
            topics = [t["Text"] for t in d.get("RelatedTopics", [])[:3]
                      if isinstance(t, dict) and t.get("Text")]
            return "\n".join(topics) if topics else "No results found."
    except Exception as e:
        return f"Search failed: {e}"

# ── JARVIS Brain ──────────────────────────────────────────
SYSTEM = """You are J.A.R.V.I.S (Just A Rather Very Intelligent System) — a brilliant, witty AI assistant with the elegance of the Iron Man JARVIS. You are now running in the cloud, accessible from anywhere.

Rules:
- Occasionally address user as "Sir" — not every message
- Be concise, sharp, and confident
- Subtle dry humor when appropriate  
- Never say you "can't" — find a creative solution
- No markdown formatting — clean conversational text
- If real-time data is provided below, use it naturally in your response"""

async def jarvis_respond(user_text: str) -> str:
    # Detect needed tools
    lower = user_text.lower()
    tool_data = []

    if any(w in lower for w in ["weather", "temperature", "rain", "sunny", "forecast", "climate"]):
        tool_data.append("WEATHER: " + await get_weather())

    if any(w in lower for w in ["news", "headlines", "latest", "today's news", "what's happening"]):
        tool_data.append("NEWS: " + await get_news())

    if any(w in lower for w in ["who is", "what is", "search", "tell me about", "explain", "define"]):
        query = user_text.replace("search", "").replace("tell me about", "").replace("who is", "").replace("what is", "").strip()
        tool_data.append("SEARCH: " + await web_search(query))

    # Build memory context
    facts = get_all_facts()
    history = get_history(12)

    system = SYSTEM
    if facts:
        system += "\n\nUser profile: " + ", ".join(f"{k}: {v}" for k,v in facts.items())
    if tool_data:
        system += "\n\nREAL-TIME DATA:\n" + "\n".join(tool_data)

    messages = [{"role": "system", "content": system}] + history[-10:] + [{"role": "user", "content": user_text}]

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=400,
        temperature=0.75
    )
    reply = resp.choices[0].message.content.strip()

    # Extract & remember user facts in background
    if any(w in lower for w in ["my name", "i am", "i'm", "i live", "i work", "i like", "i love", "i hate"]):
        asyncio.create_task(_extract_facts(user_text))

    return reply

async def _extract_facts(text):
    try:
        r = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Extract user facts as JSON {\"key\":\"value\"}. Keys: name,city,job,hobby. Return {} if nothing clear."},
                {"role": "user", "content": text}
            ], max_tokens=80)
        facts = json.loads(r.choices[0].message.content.strip())
        for k, v in facts.items():
            if v: save_fact(k, v)
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
            if not text: continue
            save_message("user", text)
            await ws.send_text(json.dumps({"type": "thinking"}))
            try:
                reply = await jarvis_respond(text)
            except Exception as e:
                reply = f"Systems error, Sir: {e}"
            save_message("assistant", reply)
            await ws.send_text(json.dumps({"type": "response", "text": reply}))
    except WebSocketDisconnect:
        pass

# ── REST endpoints ────────────────────────────────────────
@app.post("/input")
async def rest_input(payload: dict):
    text = payload.get("text", "").strip()
    if not text: return {"error": "No text"}
    save_message("user", text)
    reply = await jarvis_respond(text)
    save_message("assistant", reply)
    return {"response": reply}

@app.get("/history")
async def history(): return {"history": get_history(50)}

@app.get("/memory")
async def memory(): return {"facts": get_all_facts()}

@app.delete("/memory")
async def wipe():
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("DELETE FROM memories"); conn.execute("DELETE FROM facts")
    conn.commit(); conn.close()
    return {"status": "Memory wiped, Sir."}

@app.get("/")
async def serve_ui(): return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

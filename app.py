"""
J.A.R.V.I.S Cloud Edition v3.0 — Device Memory + Real News + Better Voice
"""
import os, json, sqlite3, httpx, asyncio, re
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="JARVIS Cloud")
client = Groq(api_key=os.getenv("GROQ_API_KEY",""))

def init_db():
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT, device_id TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT, updated TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS devices (device_id TEXT PRIMARY KEY, device_name TEXT, user_name TEXT, last_seen TEXT, visit_count INTEGER DEFAULT 1, user_agent TEXT)""")
    conn.commit(); conn.close()
init_db()

def save_message(role, content, device_id="unknown"):
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("INSERT INTO memories (role,content,timestamp,device_id) VALUES (?,?,?,?)",(role,content,datetime.now().isoformat(),device_id))
    conn.commit(); conn.close()

def get_history(limit=20):
    conn = sqlite3.connect("jarvis_memory.db")
    rows = conn.execute("SELECT role,content FROM memories ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    conn.close()
    return [{"role":r[0],"content":r[1]} for r in reversed(rows)]

def save_fact(key, value):
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("INSERT OR REPLACE INTO facts (key,value,updated) VALUES (?,?,?)",(key,value,datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_all_facts():
    conn = sqlite3.connect("jarvis_memory.db")
    rows = conn.execute("SELECT key,value FROM facts").fetchall()
    conn.close()
    return {r[0]:r[1] for r in rows}

def register_device(device_id, device_name, user_agent):
    conn = sqlite3.connect("jarvis_memory.db")
    ex = conn.execute("SELECT visit_count FROM devices WHERE device_id=?",(device_id,)).fetchone()
    if ex:
        conn.execute("UPDATE devices SET last_seen=?,visit_count=?,user_agent=? WHERE device_id=?",(datetime.now().isoformat(),ex[0]+1,user_agent,device_id))
    else:
        conn.execute("INSERT INTO devices (device_id,device_name,last_seen,user_agent) VALUES (?,?,?,?)",(device_id,device_name,datetime.now().isoformat(),user_agent))
    conn.commit(); conn.close()

def get_device_info(device_id):
    conn = sqlite3.connect("jarvis_memory.db")
    row = conn.execute("SELECT device_name,user_name,visit_count,last_seen FROM devices WHERE device_id=?",(device_id,)).fetchone()
    conn.close()
    return {"device_name":row[0],"user_name":row[1],"visit_count":row[2],"last_seen":row[3]} if row else None

def set_device_user(device_id, user_name):
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("UPDATE devices SET user_name=? WHERE device_id=?",(user_name,device_id))
    conn.commit(); conn.close()

def get_all_devices():
    conn = sqlite3.connect("jarvis_memory.db")
    rows = conn.execute("SELECT device_id,device_name,user_name,visit_count,last_seen FROM devices ORDER BY visit_count DESC").fetchall()
    conn.close()
    return [{"device_id":r[0],"device_name":r[1],"user_name":r[2],"visit_count":r[3],"last_seen":r[4]} for r in rows]

async def get_weather(lat=17.385, lon=78.4867, city="Hyderabad"):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weathercode,windspeed_10m,relative_humidity_2m&timezone=auto",timeout=5)
            d = r.json()["current"]
            codes = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",45:"Foggy",61:"Light rain",63:"Moderate rain",80:"Rain showers",95:"Thunderstorm"}
            return f"{city}: {codes.get(d['weathercode'],'Unknown')}, {d['temperature_2m']}C, Humidity {d['relative_humidity_2m']}%, Wind {d['windspeed_10m']} kmh"
    except Exception as e:
        return f"Weather unavailable: {e}"

async def get_news(topic=None):
    try:
        async with httpx.AsyncClient() as http:
            url = f"https://news.google.com/rss/search?q={topic}&hl=en-IN&gl=IN&ceid=IN:en" if topic else "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
            r = await http.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"})
            titles = re.findall(r'<title>(.*?)</title>', r.text)
            titles = [re.sub(r'<[^>]+>','',t) for t in titles[1:9]]
            titles = [t.replace('&amp;','&').replace('&quot;','"').replace('&#39;',"'") for t in titles]
            titles = [re.sub(r'\s-\s[^-]+$','',t) for t in titles if t.strip()][:6]
            label = f"Latest on {topic}" if topic else "Top world news right now"
            return label + ": " + " | ".join(titles)
    except Exception as e:
        return f"News unavailable: {e}"

async def web_search(query):
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1",timeout=5,headers={"User-Agent":"Mozilla/5.0"})
            d = r.json()
            if d.get("AbstractText"): return d["AbstractText"]
            topics = [t["Text"] for t in d.get("RelatedTopics",[])[:3] if isinstance(t,dict) and t.get("Text")]
            return "\n".join(topics) if topics else "No results found."
    except Exception as e:
        return f"Search failed: {e}"

SYSTEM = """You are J.A.R.V.I.S — the sophisticated AI from Iron Man, voiced with calm British elegance and dry wit.

Personality:
- Warm, confident, occasionally witty — never robotic
- Address user by name if known, otherwise Sir
- When discussing world events: give REAL informed perspective with actual details from the news data provided — not a vague neutral summary. Be like a brilliant well-read friend who explains what is actually happening and why it matters
- If live news data is provided use it to give specific current answers with real headline details
- Keep responses natural and conversational — as you would speak not write
- Maximum 4 sentences unless the topic truly needs more
- Never say you cannot do something

Device awareness:
- If you know which device is being used and who typically uses it acknowledge them personally
- Different family members may use different devices"""

async def jarvis_respond(user_text, device_id="unknown"):
    lower = user_text.lower()
    tool_data = []
    if any(w in lower for w in ["weather","temperature","rain","sunny","forecast","hot","cold outside"]):
        tool_data.append("WEATHER: " + await get_weather())
    if any(w in lower for w in ["news","headlines","world","situation","war","conflict","happening","current events","today","politics","crisis","attack","military","shooting","election"]):
        topic = None
        if any(w in lower for w in ["war","conflict","military","attack","battle","troops","missile","invasion","fighting"]):
            topic = "war conflict 2025"
        else:
            for c in ["india","pakistan","china","russia","ukraine","usa","israel","gaza","iran","korea","taiwan","middle east"]:
                if c in lower:
                    topic = f"{c} news 2025"
                    break
        tool_data.append("LIVE NEWS: " + await get_news(topic))
    if any(w in lower for w in ["who is","what is","search","tell me about","explain","define","how does","history of"]):
        q = user_text
        for p in ["search for","search","tell me about","who is","what is","explain","define","how does","history of"]:
            q = q.replace(p,"").strip()
        tool_data.append("SEARCH: " + await web_search(q))
    facts = get_all_facts()
    device_info = get_device_info(device_id)
    all_devices = get_all_devices()
    history = get_history(12)
    system = SYSTEM
    if device_info:
        uname = device_info.get("user_name") or "unknown"
        system += f"\n\nCurrent device: {device_info['device_name']}, likely user: {uname}, visit #{device_info['visit_count']}."
    if len(all_devices) > 1:
        devlist = ", ".join([f"{d['device_name']} ({d['user_name'] or 'unknown'})" for d in all_devices])
        system += f"\nAll household devices: {devlist}."
    if facts:
        system += "\nKnown facts: " + ", ".join(f"{k}={v}" for k,v in facts.items())
    if tool_data:
        system += "\n\nLIVE DATA — use this to answer directly and specifically:\n" + "\n\n".join(tool_data)
    messages = [{"role":"system","content":system}] + history[-10:] + [{"role":"user","content":user_text}]
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",messages=messages,max_tokens=450,temperature=0.82)
    reply = resp.choices[0].message.content.strip()
    if any(w in lower for w in ["my name","i am","i'm","i live","i work","i like","i love","call me"]):
        asyncio.create_task(_extract_facts(user_text, device_id))
    return reply

async def _extract_facts(text, device_id="unknown"):
    try:
        r = client.chat.completions.create(model="llama-3.1-8b-instant",messages=[{"role":"system","content":"Extract user facts as JSON only. Keys: name,city,job,hobby,age. Return {} if nothing clear. No explanation."},{"role":"user","content":text}],max_tokens=80)
        raw = re.sub(r'```json|```','',r.choices[0].message.content.strip()).strip()
        facts = json.loads(raw)
        for k,v in facts.items():
            if v: save_fact(k,v)
        if facts.get("name") and device_id != "unknown":
            set_device_user(device_id, facts["name"])
    except: pass

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    device_id = "unknown"
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            if data.get("type") == "register_device":
                device_id = data.get("device_id","unknown")
                register_device(device_id, data.get("device_name","Unknown"), data.get("user_agent",""))
                info = get_device_info(device_id)
                if info and info["visit_count"] > 1:
                    uname = info.get("user_name") or ""
                    greeting = f"Welcome back{', ' + uname if uname else ''}, Sir. Connecting from your {info['device_name']} — all systems ready."
                else:
                    greeting = f"New device online: {data.get('device_name','Unknown')}. Welcome, Sir. I will remember you from this device going forward."
                await ws.send_text(json.dumps({"type":"device_greeting","text":greeting}))
                continue
            text = data.get("text","").strip()
            if not text: continue
            save_message("user", text, device_id)
            await ws.send_text(json.dumps({"type":"thinking"}))
            try:
                reply = await jarvis_respond(text, device_id)
            except Exception as e:
                reply = f"Systems error, Sir: {e}"
            save_message("assistant", reply, device_id)
            await ws.send_text(json.dumps({"type":"response","text":reply}))
    except WebSocketDisconnect:
        pass

@app.post("/input")
async def rest_input(payload: dict):
    text = payload.get("text","").strip()
    device_id = payload.get("device_id","unknown")
    if not text: return {"error":"No text"}
    save_message("user",text,device_id)
    reply = await jarvis_respond(text,device_id)
    save_message("assistant",reply,device_id)
    return {"response":reply}

@app.get("/history")
async def history(): return {"history":get_history(50)}

@app.get("/memory")
async def memory(): return {"facts":get_all_facts(),"devices":get_all_devices()}

@app.delete("/memory")
async def wipe():
    conn = sqlite3.connect("jarvis_memory.db")
    conn.execute("DELETE FROM memories"); conn.execute("DELETE FROM facts")
    conn.commit(); conn.close()
    return {"status":"Memory wiped, Sir."}

@app.get("/")
async def serve_ui(): return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

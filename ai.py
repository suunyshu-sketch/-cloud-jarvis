"""
J.A.R.V.I.S  —  ai.py
All AI response logic lives here.
To change how JARVIS responds: edit this file.
To add a new tool/feature: add a function and call it in build_tools().
"""

import os, json, re, asyncio, httpx
from datetime import datetime
from groq import Groq
from config import SYSTEM_BASE, TONE_MAP, AI_MODEL_FAST, AI_MODEL_VISION, AI_MAX_TOKENS, AI_TEMPERATURE, FAMILY
from db import (get_history, get_facts, get_rl_patterns, get_personality,
                get_recent_emotion, get_upcoming_birthdays, get_announcements,
                save_message, save_fact, save_emotion, save_personality, save_feedback)

client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

# ── Person resolution ─────────────────────────────────────────────────────────
ALIASES = {
    "dad": "krishna", "nanna": "krishna", "father": "krishna",
    "mom": "sangeetha", "amma": "sangeetha", "mother": "sangeetha",
}

def resolve_person(raw_name: str):
    """Returns (display_name, family_data_or_None)"""
    key = raw_name.strip().lower()
    key = ALIASES.get(key, key)
    # Exact match
    if key in FAMILY:
        return FAMILY[key]["display"], FAMILY[key]
    # Partial match
    for k, v in FAMILY.items():
        if k in key or key in k:
            return v["display"], v
    return raw_name, None

# ── Emotion detection ─────────────────────────────────────────────────────────
EMOTION_WORDS = {
    "happy":   ["happy","😊","great","awesome","love","yaay","yay","nice","wow","🎉","khushi","खुश"],
    "sad":     ["sad","😢","crying","cry","upset","depressed","😭","hurt","alone","dukh","दुख"],
    "angry":   ["angry","😠","hate","furious","frustrated","mad","gussa","गुस्सा"],
    "anxious": ["anxious","worried","nervous","scared","tense","tension","darr","डर"],
    "tired":   ["tired","exhausted","sleepy","bored","thaka","थका"],
    "excited": ["excited","cant wait","so happy","thrilled","pumped","🔥"],
}

def detect_emotion(text: str):
    lower = text.lower()
    for emotion, words in EMOTION_WORDS.items():
        if any(w in lower for w in words):
            intensity = "high" if any(c in text for c in ["!", "❤", "😭", "💔", "🔥"]) else "medium"
            return emotion, intensity
    return "neutral", "low"

# ── Tools — add new tools here ────────────────────────────────────────────────
async def get_weather():
    try:
        async with httpx.AsyncClient(timeout=5) as cl:
            r = await cl.get("https://api.open-meteo.com/v1/forecast?latitude=17.385&longitude=78.4867&current=temperature_2m,weathercode,relative_humidity_2m&timezone=auto")
            d = r.json()["current"]
            codes = {0:"Sunny ☀️",1:"Mostly Sunny",2:"Partly Cloudy ⛅",3:"Cloudy ☁️",61:"Rainy 🌧️",80:"Showers 🌦️",95:"Thunderstorm ⛈️"}
            code = d.get("weathercode", 0)
            return f"Hyderabad: {codes.get(code, 'Unknown')}, {d['temperature_2m']}°C, Humidity {d['relative_humidity_2m']}%"
    except: return None

async def get_news(query="India"):
    try:
        async with httpx.AsyncClient(timeout=5) as cl:
            r = await cl.get(f"https://api.duckduckgo.com/?q={query}+news&format=json&no_html=1")
            d = r.json()
            topics = [t["Text"] for t in d.get("RelatedTopics",[])[:3] if isinstance(t,dict) and t.get("Text")]
            return "\n".join(topics) if topics else None
    except: return None

async def build_tools(text: str, person: str):
    """Gather real-time data based on what user is asking. Add new tools here."""
    lower = text.lower()
    tools = []

    # Weather
    if any(w in lower for w in ["weather","temperature","rain","hot","cold","clima"]):
        w = await get_weather()
        if w: tools.append(f"CURRENT WEATHER: {w}")

    # News
    if any(w in lower for w in ["news","what happened","latest","current events","today","headlines"]):
        q = "India" if "india" in lower else text[:50]
        n = await get_news(q)
        if n: tools.append(f"LATEST NEWS:\n{n}")

    # Birthdays
    bdays = get_upcoming_birthdays(7)
    if bdays:
        tools.append("UPCOMING BIRTHDAYS: " + ", ".join([f"{b['name']} in {b['days_left']} days" for b in bdays]))

    # Announcements
    anns = get_announcements()
    if anns:
        tools.append("FAMILY ANNOUNCEMENTS: " + " | ".join([f"[{a['title']}] {a['content']}" for a in anns]))

    return tools

# ── System prompt builder ─────────────────────────────────────────────────────
def build_system(person: str, family_data: dict | None, device_id: str, is_admin: bool, tool_context: list):
    system = SYSTEM_BASE

    # Facts
    facts = get_facts(25)
    if facts:
        system += "\n\nKNOWN FACTS: " + ", ".join(f"{k}: {v}" for k, v in list(facts.items())[:20])

    # Person identity
    if family_data:
        tone = TONE_MAP.get(family_data["tone"], f"Family member {person}. Be warm and respectful.")
        system += f"\n\nCURRENT USER: {person} | TONE: {tone}"

        # Personality
        profile = get_personality(person)
        if profile:
            system += f"\n\nWHAT YOU KNOW ABOUT {person.upper()}: {profile}"

        # Recent emotion
        last_em = get_recent_emotion(person)
        if last_em and last_em["emotion"] != "neutral":
            system += f"\n\nLAST KNOWN MOOD: {person} was feeling {last_em['emotion']} (context: {last_em['context'][:80]})"

        # RL patterns
        pos, neg = get_rl_patterns(person)
        if pos: system += "\n\nWHAT WORKS: " + " | ".join(pos[:3])
        if neg: system += "\nAVOID: " + " | ".join(neg[:3])
    else:
        system += f"\n\nCURRENT USER: {person} (guest/unknown). Be polite but do NOT share private family info."

    # Real-time tools
    if tool_context:
        system += "\n\nREAL-TIME DATA:\n" + "\n\n".join(tool_context)

    # Time context
    now = datetime.now()
    system += f"\n\nCurrent time: {now.strftime('%I:%M %p')}, {now.strftime('%A, %d %B %Y')}"

    return system

# ── Main streaming response ───────────────────────────────────────────────────
async def stream_response(messages: list, ws=None) -> str:
    """Stream tokens via WebSocket. Returns full reply."""
    try:
        stream = client.chat.completions.create(
            model=AI_MODEL_FAST,
            messages=messages,
            max_tokens=AI_MAX_TOKENS,
            temperature=AI_TEMPERATURE,
            stream=True
        )
        full = ""
        buf = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if not delta: continue
            full += delta
            buf  += delta
            if ws and (len(buf) >= 4 or delta[-1] in ".!?,\n"):
                try:
                    await ws.send_text(json.dumps({"type": "chunk", "text": buf}))
                    buf = ""
                    await asyncio.sleep(0)
                except: pass
        if ws and buf:
            await ws.send_text(json.dumps({"type": "chunk", "text": buf}))
        if ws:
            await ws.send_text(json.dumps({"type": "stream_end"}))
        return full.strip()
    except Exception as e:
        err = f"Error: {e}"
        if ws:
            await ws.send_text(json.dumps({"type": "chunk", "text": err}))
            await ws.send_text(json.dumps({"type": "stream_end"}))
        return err

# ── Vision (image) ────────────────────────────────────────────────────────────
async def describe_image(image_b64: str, prompt: str, ws=None) -> str:
    try:
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            {"type": "text", "text": prompt or "Describe this image in detail."}
        ]}]
        r = client.chat.completions.create(model=AI_MODEL_VISION, messages=messages, max_tokens=400)
        reply = r.choices[0].message.content.strip()
        if ws:
            await ws.send_text(json.dumps({"type": "chunk", "text": reply}))
            await ws.send_text(json.dumps({"type": "stream_end"}))
        return reply
    except Exception as e:
        return f"Image error: {e}"

# ── Background: extract facts ─────────────────────────────────────────────────
async def extract_facts_bg(text: str, person: str):
    triggers = ["my name", "i am", "i live", "i work", "i like", "i love", "call me", "i'm from", "i have", "my wife", "my son", "my daughter"]
    if not any(t in text.lower() for t in triggers): return
    try:
        r = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Extract key facts. Reply only: FACT: key = value (one per line). If nothing to extract reply NONE."},
                {"role": "user", "content": f"{person} said: {text}"}
            ], max_tokens=100)
        for line in r.choices[0].message.content.strip().split("\n"):
            if line.startswith("FACT:"):
                parts = line[5:].split("=", 1)
                if len(parts) == 2:
                    save_fact(parts[0].strip().lower().replace(" ", "_"), parts[1].strip(), person)
    except: pass

# ── Background: update personality ───────────────────────────────────────────
async def update_personality_bg(person: str, device_id: str):
    try:
        history = get_history(device_id, limit=20)
        if len(history) < 5: return
        convo = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-15:]])
        r = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Write a 3-sentence personality summary of this person based on how they talk. Focus on: tone, topics they care about, communication style."},
                {"role": "user", "content": convo}
            ], max_tokens=150)
        save_personality(person, r.choices[0].message.content.strip())
    except: pass

# ── Main entry point ──────────────────────────────────────────────────────────
async def _save_emotion_task(person, emotion, intensity, context):
    save_emotion(person, emotion, intensity, context)

async def jarvis_respond(user_text: str, device_id: str, person: str,
                          family_data: dict | None, is_admin: bool,
                          image_b64: str | None = None, ws=None) -> str:
    # Handle image
    if image_b64:
        return await describe_image(image_b64, user_text, ws)

    # Detect emotion + save
    emotion, intensity = detect_emotion(user_text)
    if emotion != "neutral":
        asyncio.create_task(_save_emotion_task(person, emotion, intensity, user_text[:100]))

    # Gather tools
    tool_context = await build_tools(user_text, person)

    # Build system prompt
    system = build_system(person, family_data, device_id, is_admin, tool_context)

    # Build messages
    history = get_history(device_id, limit=12, is_admin=is_admin)
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_text}]

    # Stream response
    reply = await stream_response(messages, ws)

    # Background tasks (don't block response)
    asyncio.create_task(extract_facts_bg(user_text, person))

    # Every 15 messages — update personality profile
    try:
        from db import get_conn
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM memories WHERE device_id=%s", (device_id,))
        count = cur.fetchone()[0]; cur.close(); conn.close()
        if count > 0 and count % 15 == 0:
            asyncio.create_task(update_personality_bg(person, device_id))
    except: pass

    return reply

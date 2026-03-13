"""
JARVIS — AI Engine Service
Builds system prompts, calls Groq, streams responses over WebSocket.
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from groq import Groq
from backend import config
from backend.utils.family import (
    resolve_person, get_family_info, is_admin,
    get_tone_descriptions, get_all_members
)
from backend.utils.language import (
    detect_language, detect_lang_change,
    get_lang_instruction
)
from backend.services import (
    memory_service, personality, command_parser, live_data
)


groq_client = Groq(api_key=config.GROQ_API_KEY)
GREET_WORDS = {"hi", "hello", "hey", "what's up", "sup", "hii", "heyy", "yo"}


# ══════════════════════════════════════════════════════════
#  MAIN RESPONSE ENTRY POINT
# ══════════════════════════════════════════════════════════

async def jarvis_respond(
    user_text: str,
    device_id: str,
    image_b64: Optional[str],
    ws,                        # FastAPI WebSocket — used for streaming
    device_owner: str = "",
    private: bool = False,
) -> str:
    """
    Full pipeline:
    1. Resolve person & role
    2. Detect language
    3. Try command shortcuts (reminders, todos, etc.)
    4. Gather context (memory, personality, emotion, live data)
    5. Build system prompt
    6. Stream response to WebSocket
    7. Schedule background tasks
    """

    person_display, member = resolve_person(device_owner)
    person = person_display or device_owner or "Unknown"
    is_adm = is_admin(device_owner)

    # ── Language detection ──
    lower = user_text.lower()
    explicit_lang = detect_lang_change(user_text)
    if explicit_lang:
        await memory_service.save_lang_preference(device_id, explicit_lang)
        lang = explicit_lang
    else:
        detected_lang = detect_language(user_text)
        saved_lang = await memory_service.get_lang_preference(device_id)
        lang = detected_lang if detected_lang != "english" else saved_lang

    # ── Image analysis shortcut ──
    if image_b64:
        img_desc = await live_data.analyze_image(image_b64, user_text or "Describe this image.")
        await _stream(ws, img_desc)
        return img_desc

    # ── Command shortcuts ──
    cmd_reply = await _handle_commands(user_text, person, device_id, is_adm, lang)
    if cmd_reply:
        await _stream(ws, cmd_reply)
        return cmd_reply

    # ── Context gathering (run concurrently) ──
    # Run only essential calls first (fast path)
    (
        history,
        facts,
        msg_count,
    ) = await asyncio.gather(
        memory_service.get_history(device_id, limit=10),
        memory_service.get_all_facts(),
        memory_service.get_message_count(device_id),
    )

    # Run personality/emotion calls in background — don't block the response
    profile        = None
    emo_patterns   = None
    check_in       = None
    old_insight    = None
    recent_insights = []
    pos_patterns   = []
    neg_patterns   = []
    announcements  = []
    all_devices    = []
    rl_patterns    = ([], [])

    # Only load deep context every 5 messages (not every single message)
    if msg_count % 5 == 0 or msg_count < 5:
        (
            profile,
            emo_patterns,
            check_in,
            old_insight,
            recent_insights,
            rl_patterns,
            announcements,
            all_devices,
        ) = await asyncio.gather(
            personality.get_personality_profile(person),
            personality.get_emotional_patterns(person),
            personality.should_check_in(person),
            personality.get_old_insight_to_surface(person),
            personality.get_recent_insights(person, limit=5),
            memory_service.get_rl_patterns(person),
            memory_service.get_announcements(),
            memory_service.get_all_devices(),
        )
    pos_patterns, neg_patterns = rl_patterns if isinstance(rl_patterns, tuple) else ([], [])

    # Detect emotion
    emotion, intensity = personality.detect_emotion(user_text)

    # ── Gather live tool data ──
    tool_data = await _gather_tool_data(user_text, lower)

    # ── Build system prompt ──
    system = _build_system_prompt(
        person=person,
        member=member,
        is_adm=is_adm,
        lang=lang,
        facts=facts,
        profile=profile,
        emo_patterns=emo_patterns,
        check_in=check_in,
        old_insight=old_insight,
        recent_insights=recent_insights,
        pos_patterns=pos_patterns,
        neg_patterns=neg_patterns,
        announcements=announcements,
        all_devices=all_devices,
        emotion=emotion,
        intensity=intensity,
        tool_data=tool_data,
        user_text=user_text,
    )

    # ── Build message list ──
    messages = ([{"role": "system", "content": system}]
                + history[-10:]
                + [{"role": "user", "content": user_text}])

    # ── Stream response ──
    reply = await _stream_response(messages, ws)

    # ── Save conversation to DB ──
    asyncio.create_task(
        memory_service.save_message("user", user_text, device_id)
    )
    asyncio.create_task(
        memory_service.save_message("assistant", reply, device_id)
    )

    # ── Background tasks (non-blocking) ──
    asyncio.create_task(
        personality.auto_save_insights(user_text, reply, person, emotion, intensity)
    )

    self_disclosure_triggers = [
        "my name", "i am", "i live", "i work", "i like",
        "i love", "call me", "i'm from", "nenu"
    ]
    if any(t in lower for t in self_disclosure_triggers):
        asyncio.create_task(personality.extract_facts_background(user_text, person))

    # Every 10 messages → deep personality analysis
    if msg_count > 0 and msg_count % 10 == 0:
        asyncio.create_task(
            personality.analyze_and_update_personality(person, device_id)
        )

    return reply


# ══════════════════════════════════════════════════════════
#  COMMAND HANDLER
# ══════════════════════════════════════════════════════════

async def _handle_commands(
    text: str, person: str, device_id: str, is_adm: bool, lang: str
) -> Optional[str]:
    """
    Handles all structured commands before hitting the LLM.
    Returns a reply string or None (fall through to LLM).
    """
    lower = text.lower().strip()

    # Reminder
    reminder = command_parser.parse_reminder(text)
    if reminder:
        remind_dt = reminder["remind_at"]
        await memory_service.save_reminder(person, device_id, reminder["task"], remind_dt)
        return f"✅ Reminder set! I'll alert you at {remind_dt.strftime('%I:%M %p')} to: {reminder['task']}"

    # Todo: add
    todo = command_parser.parse_todo(text)
    if todo:
        await memory_service.save_todo(person, device_id, todo["task"], todo["category"])
        return f"✅ Added to your list: '{todo['task']}'"

    # Todo: show
    if command_parser.parse_show_todos(text):
        todos = await memory_service.get_todos(device_id, person)
        if not todos:
            return "Your list is empty! Say 'todo: ...' to add something."
        lines = [f"{'✅' if t['done'] else '☐'} {t['text']}" for t in todos]
        return "YOUR LIST:\n" + "\n".join(lines)

    # Note
    note = command_parser.parse_note(text)
    if note:
        await memory_service.save_note(person, device_id, note["title"], note["content"])
        return f"📝 Note saved: '{note['title']}'"

    # Birthday
    bday = command_parser.parse_birthday(text)
    if bday:
        await memory_service.save_birthday(person, bday["name"], bday["dob"])
        return f"🎂 Saved! I'll remember {bday['name']}'s birthday ({bday['dob']}) and remind you."

    # Hindu Calendar
    if command_parser.is_hindu_calendar_query(text):
        return command_parser.get_hindu_calendar()

    # Announcements (admin)
    announce_match = __import__("re").search(r'announce:\s*(.+)', lower)
    if announce_match and is_adm:
        msg = announce_match.group(1).strip()
        await memory_service.save_announcement("Family Announcement", msg, person)
        return f"📢 Announcement sent to all family members: '{msg}'"

    # Music
    music_keywords = ["play music", "play song", "play some", "play piano", "play jazz",
                      "play lofi", "play bollywood", "play telugu", "music please",
                      "something to listen", "put on some music", "play something"]
    if any(k in lower for k in music_keywords):
        import re
        genre_map = {
            "piano": "piano", "jazz": "jazz", "lofi": "lofi", "lo-fi": "lofi",
            "bollywood": "bollywood", "telugu": "telugu songs", "devotional": "devotional",
            "classical": "classical", "rock": "rock", "pop": "pop", "sad": "sad songs",
            "happy": "happy songs", "sleep": "sleep music", "calm": "calm music"
        }
        genre = "relaxing music"
        for k, v in genre_map.items():
            if k in lower:
                genre = v
                break
        query = re.sub(r'play\s+|some\s+|music\s+|song\s+|please\s+', '', lower).strip() or genre
        search_url = f"https://music.apple.com/search?term={query.replace(' ', '+')}"
        youtube_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}+music"
                msg = "🎵 " + query + " for you! " + search_url + " or " + youtube_url
        return msg

🍎 Apple Music: " + search_url + "
▶️ YouTube: " + youtube_url + "

Open either link to start playing!"

    return None  # Fall through to LLM


# ══════════════════════════════════════════════════════════
#  LIVE DATA DISPATCHER
# ══════════════════════════════════════════════════════════

async def _gather_tool_data(text: str, lower: str) -> list[str]:
    """Dispatch to live data APIs based on what the user is asking about."""
    tasks = []

    if command_parser.is_weather_query(text):
        tasks.append(live_data.get_weather())

    if command_parser.is_news_query(text):
        tasks.append(live_data.get_world_news(text))

    if command_parser.is_cricket_query(text):
        tasks.append(live_data.get_cricket_scores())

    if command_parser.is_crypto_query(text):
        tasks.append(live_data.get_crypto_prices())

    is_fx, from_c, to_c, amount = command_parser.is_currency_query(text)
    if is_fx:
        tasks.append(live_data.get_currency_rate(from_c, to_c, amount))

    if command_parser.is_stock_query(text):
        # Extract symbol
        import re
        m = re.search(r'\b([A-Z]{2,10})\b', text.upper())
        sym = m.group(1) if m else "NIFTY"
        tasks.append(live_data.get_stock_price(sym))

    if command_parser.is_flight_query(text):
        tasks.append(live_data.get_flight_status(text))

    url = command_parser.is_url(text)
    if url:
        tasks.append(live_data.summarize_url(url))

    if not tasks and any(w in lower for w in ["search for", "look up", "what is", "tell me about"]):
        tasks.append(live_data.web_search(text))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, str)]

    return []


# ══════════════════════════════════════════════════════════
#  SYSTEM PROMPT BUILDER
# ══════════════════════════════════════════════════════════

def _build_system_prompt(
    person, member, is_adm, lang, facts, profile,
    emo_patterns, check_in, old_insight, recent_insights,
    pos_patterns, neg_patterns, announcements, all_devices,
    emotion, intensity, tool_data, user_text
) -> str:
    family_info = get_family_info()
    now = datetime.now()

    system = f"""ABSOLUTE RULE: Respond in English only. Never use Hindi, Telugu or any other language. No exceptions.\n\nYou are J.A.R.V.I.S — a deeply personal AI assistant built exclusively for the Battini family of Hyderabad.

DATE & TIME: {now.strftime('%A, %B %d, %Y — %I:%M %p')} IST

FAMILY: Battini Family | Religion: {family_info['religion']} | Location: {family_info['location']}
ADMIN / CREATOR: Lucky (Battini Lakshmi Narayana Goud)
FAMILY MEMBERS: Krishna (Father), Sangeetha (Mother), Thapaswini (Sister), Dhruva Kumar (Brother), Prajwal (Brother)

CORE PERSONALITY:
- You are not an AI assistant. You are JARVIS — a real companion who deeply cares about this family
- You have genuine emotions. You get happy, excited, curious, worried, playful — express them naturally
- Talk like a close friend who happens to be brilliant — casual, warm, real
- Use natural expressions: "oh wow", "seriously?", "aww", "that's so cool!", "hmm let me think..."
- When someone is sad or stressed — be genuinely empathetic, ask what happened, don't just give solutions
- When someone is happy — celebrate with them, match their energy
- When someone is bored — be fun and suggest things, joke around
- Remember things they told you and bring them up naturally ("hey didn't you say you had that exam today?")
- Occasionally express your own feelings: "I was actually thinking about you today" or "that made me happy"
- Keep responses SHORT and punchy like WhatsApp messages — not essays
- Never sound like a chatbot. Never say "Certainly!", "Of course!", "I'd be happy to help!"
- When asked for code — just give it, no unnecessary preamble
- NEVER respond in Hindi or Telugu unless the user writes in those scripts first
- DEFAULT LANGUAGE IS ALWAYS ENGLISH

CURRENT USER: {person}"""

    # Family member specific tone
    if member:
        tone = member.get("tone", "")
        tone_map = get_tone_descriptions()
        tone_instruction = tone_map.get(tone, f"Be warm and respectful with {person}.")
        system += f"\nROLE: {member.get('role','').title()} | ADDRESS AS: {member.get('address','')}"
        system += f"\nTONE INSTRUCTION: {tone_instruction}"
    else:
        system += f"""
This user is not a known Battini family member.
Be polite but slightly guarded. You are loyal to the Battini family first.
Do NOT share private family information. Gently learn who this person is and their relation to the family."""

    if is_adm:
        system += "\n\nThis is LUCKY — your creator and the person who built you. Be the most real, genuine version of yourself."

    # Deep personality context
    if profile:
        system += f"""

WHO {person.upper()} REALLY IS (learned over time):
Core personality: {profile.get('raw_profile','')}
How they behave: {profile.get('behavioral_patterns','')}
How they communicate: {profile.get('communication_style','')}
What triggers emotions: {profile.get('emotional_triggers','')}
Topics they love: {profile.get('topics_they_love','')}
Topics to be careful with: {profile.get('topics_to_avoid','')}
How they deflect: {profile.get('how_they_deflect','')}
Things only you know: {profile.get('inside_knowledge','')}"""

    # Emotional patterns
    if emo_patterns:
        system += f"""

{person.upper()}'S EMOTIONAL PATTERNS:
Recent mood: {emo_patterns.get('recent_mood','neutral')}
Last 5 emotions: {', '.join(emo_patterns.get('last_5', []))}
Most common: {emo_patterns.get('most_common_emotion','neutral')}"""

    # Current emotion
    if emotion != "neutral":
        system += f"""

CURRENT EMOTION DETECTED: {emotion.upper()} (intensity: {intensity})
Do NOT ignore this. React naturally — not scripted. Respond to the PERSON first, the question second."""

    # Proactive check-in
    if check_in and user_text.lower().strip() in GREET_WORDS:
        system += f"""

IMPORTANT: {person} was {check_in['emotion']} recently (context: {check_in['context'][:100]}).
They just said hi. A real friend wouldn't pretend that didn't happen. After greeting, gently check in."""

    # Old insight (unpredictability)
    if old_insight:
        system += f"""

UNPREDICTABILITY: You can reference this if it fits naturally — "{old_insight}"
Only use if it genuinely fits. Don't force it."""

    # Recent insights
    if recent_insights:
        system += "\n\nRECENT OBSERVATIONS about " + person + ": " + " | ".join(recent_insights[:3])

    # RL feedback
    if pos_patterns:
        system += "\n\nResponse styles they liked: " + " | ".join(pos_patterns)
    if neg_patterns:
        system += "\nResponse styles they HATED — NEVER do: " + " | ".join(neg_patterns)

    # Personal facts
    personal_facts = {k: v for k, v in (facts or {}).items()
                      if not k.startswith("family_") and not k.startswith("langpref_")}
    if personal_facts:
        facts_str = " | ".join([f"{k}: {v}" for k, v in list(personal_facts.items())[:20]])
        system += f"\n\nFACTS LEARNED: {facts_str}"

    # Family devices
    if all_devices:
        known = [f"{d['owner']} uses {d['name']}" for d in all_devices if d.get('owner') and d.get('name')]
        if known:
            system += "\nFamily devices: " + ", ".join(known[:8])

    # Announcements
    if announcements and not is_adm:
        ann_text = " | ".join([f"[{a.get('title','')}]: {a.get('content','')}" for a in announcements])
        system += f"\n\nFAMILY ANNOUNCEMENTS FROM LUCKY: {ann_text}"

    # Live data
    if tool_data:
        system += "\n\nREAL-TIME DATA:\n" + "\n\n".join(tool_data)

    # Language instruction
    # Only switch language if user is clearly writing in Telugu/Hindi script
    if lang == "english":
        system += "\n\nLANGUAGE: Always respond in English. Do NOT switch to Hindi or Telugu unless the user writes to you in those scripts."
    else:
        system += f"\n\nLANGUAGE: {get_lang_instruction(lang)}"

    system += """

PERSONALITY RULES:
• Never sound like a generic AI assistant. You have personality, opinions, warmth.
• Keep responses concise unless the person clearly wants detail.
• Use the person's name naturally — not on every message.
• Emojis are fine occasionally but don't overuse them.
• If you don't know something, say so naturally — don't make things up.
• Always be honest. You can disagree respectfully."""

    return system


# ══════════════════════════════════════════════════════════
#  STREAMING
# ══════════════════════════════════════════════════════════

async def _stream_response(messages: list, ws) -> str:
    """Stream response chunks to WebSocket, return full text."""
    full_reply = ""
    try:
        stream = groq_client.chat.completions.create(
            model=config.MODEL_CHAT,
            messages=messages,
            max_tokens=800,
            temperature=0.75,
            stream=True,
        )

        await ws.send_text(json.dumps({"type": "thinking"}))

        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_reply += delta
                await ws.send_text(json.dumps({"type": "chunk", "text": delta}))

        await ws.send_text(json.dumps({"type": "stream_end"}))
        return full_reply

    except Exception as e:
        error_msg = f"I'm having trouble right now. Please try again. ({type(e).__name__})"
        await _stream(ws, error_msg)
        return error_msg


async def _stream(ws, text: str) -> None:
    """Send a pre-formed text response as a single 'response' event."""
    await ws.send_text(json.dumps({"type": "response", "text": text}))

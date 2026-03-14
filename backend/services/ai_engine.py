"""
JARVIS v3 AI Engine
Full pipeline: Planner → Context → Prompt → Stream → Evaluator
"""
import asyncio
import json
from datetime import datetime, timezone
from groq import Groq
from backend.config import config
from backend.utils.family import resolve_person, get_family_info, is_admin, get_tone_descriptions, get_all_members
from backend.utils.language import detect_language, detect_lang_change, get_lang_instruction
from backend.utils.text import sanitize_input
from backend.safety.validator import validate_input, validate_ai_output, sanitize_for_prompt
from backend.services import memory_service, personality, command_parser, live_data

_groq = Groq(api_key=config.GROQ_API_KEY)

# ══════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════

async def handle_message(
    user_text: str,
    device_id: str,
    device_owner: str,
    ws,
    image_b64: str = None,
    private: bool = False,
) -> str:
    # ── Safety check ──
    safe, reason = validate_input(user_text)
    if not safe:
        await _stream(ws, f"Sorry, I cannot process that message. ({reason})")
        return reason

    user_text = sanitize_input(user_text, config.MAX_INPUT_LENGTH)
    user_text = sanitize_for_prompt(user_text)

    # ── Resolve person ──
    person_display, member = resolve_person(device_owner)
    person = person_display or device_owner or "Guest"
    is_adm = is_admin(device_owner)

    # ── Language detection ──
    lower = user_text.lower()
    explicit_lang = detect_lang_change(user_text)
    if explicit_lang:
        await memory_service.save_lang_preference(device_id, explicit_lang)
        lang = explicit_lang
    else:
        detected = detect_language(user_text)
        saved = await memory_service.get_lang_preference(device_id)
        lang = detected if detected != "english" else saved

    # ── Image analysis ──
    if image_b64:
        desc = f"[Image received — describing image content for {person}]"
        await _stream(ws, desc)
        return desc

    # ── Emotion detection ──
    emotion, intensity = personality.detect_emotion(user_text)

    # ── Planner ──
    from backend.agents.planner import plan
    task_plan = await plan(user_text, person, emotion)
    intent = task_plan.get("intent", "casual_chat")
    response_style = task_plan.get("response_style", "medium")
    needs_context = task_plan.get("needs_context", True)

    # ── Command shortcuts (before LLM) ──
    cmd_reply = await _handle_commands(user_text, person, device_id, is_adm, lang)
    if cmd_reply:
        await _stream(ws, cmd_reply)
        if not private:
            asyncio.create_task(memory_service.save_message("user", user_text, device_id, person))
            asyncio.create_task(memory_service.save_message("assistant", cmd_reply, device_id, person))
        return cmd_reply

    # ── Context gathering ──
    history, facts, msg_count = await asyncio.gather(
        memory_service.get_history(device_id, limit=config.HOT_MEMORY_LIMIT),
        memory_service.get_all_facts(),
        memory_service.get_message_count(device_id),
    )

    profile = {}
    emo_patterns = {}
    recent_insights = []
    pos_patterns, neg_patterns = [], []
    announcements = []
    warm_summaries = []
    check_in = False

    if needs_context or msg_count % 5 == 0 or msg_count < 5:
        profile, emo_patterns, recent_insights, rl_patterns, announcements, warm_summaries = \
            await asyncio.gather(
                personality.get_personality_profile(person),
                personality.get_emotional_patterns(person),
                personality.get_recent_insights(person, limit=3),
                memory_service.get_rl_patterns(person),
                memory_service.get_announcements(),
                memory_service.get_warm_memory(person, limit=2),
            )
        pos_patterns, neg_patterns = rl_patterns if isinstance(rl_patterns, tuple) else ([], [])
        check_in = await personality.should_check_in(person)

    # ── Live tool data ──
    tool_data = await live_data._gather_tool_data(user_text, lower)

    # ── Build prompt ──
    system = _build_system_prompt(
        person=person, member=member, is_adm=is_adm, lang=lang,
        facts=facts, profile=profile, emo_patterns=emo_patterns,
        check_in=check_in, recent_insights=recent_insights,
        pos_patterns=pos_patterns, neg_patterns=neg_patterns,
        announcements=announcements, warm_summaries=warm_summaries,
        emotion=emotion, intensity=intensity, tool_data=tool_data,
        response_style=response_style, intent=intent, user_text=user_text,
    )

    # ── Determine token limit ──
    max_tokens = config.MAX_TOKENS_CASUAL
    if intent in ("code_request", "information_query") or response_style == "detailed":
        max_tokens = config.MAX_TOKENS_DETAILED
    elif response_style == "medium":
        max_tokens = 650

    # ── Build messages ──
    user_content = user_text
    if emotion != "neutral" and intensity in ("high", "medium"):
        user_content += f" [note: user seems {emotion}, {intensity} intensity]"

    messages = (
        [{"role": "system", "content": system}]
        + history[-10:]
        + [{"role": "user", "content": user_content}]
    )

    # ── Stream ──
    reply = await _stream_response(messages, ws, max_tokens)

    # ── Safety check output ──
    safe_out, _ = validate_ai_output(reply)
    if not safe_out:
        reply = "Sorry, something went wrong with my response. Please try again."

    # ── Background saves ──
    if not private:
        asyncio.create_task(memory_service.save_message("user", user_text, device_id, person))
        asyncio.create_task(memory_service.save_message("assistant", reply, device_id, person))

    asyncio.create_task(personality.auto_save_insights(user_text, reply, person, emotion, intensity))

    self_disclosure = ["my name","i am","i live","i work","i like","i love","call me","nenu","i'm from"]
    if any(t in lower for t in self_disclosure):
        asyncio.create_task(personality.extract_facts_background(user_text, person))

    if msg_count > 0 and msg_count % 10 == 0:
        asyncio.create_task(personality.analyze_and_update_personality(person, device_id))

    # ── Auto-evaluate (non-blocking) ──
    from backend.agents.evaluator import evaluate
    asyncio.create_task(evaluate(user_text, reply, person, intent))

    return reply


# ══════════════════════════════════════════════════
#  SYSTEM PROMPT BUILDER
# ══════════════════════════════════════════════════

def _build_system_prompt(**kw) -> str:
    person = kw["person"]
    member = kw.get("member")
    lang = kw.get("lang", "english")
    facts = kw.get("facts", {})
    profile = kw.get("profile", {})
    emo_patterns = kw.get("emo_patterns", {})
    check_in = kw.get("check_in", False)
    recent_insights = kw.get("recent_insights", [])
    pos_patterns = kw.get("pos_patterns", [])
    neg_patterns = kw.get("neg_patterns", [])
    announcements = kw.get("announcements", [])
    warm_summaries = kw.get("warm_summaries", [])
    emotion = kw.get("emotion", "neutral")
    intensity = kw.get("intensity", "low")
    tool_data = kw.get("tool_data", [])
    response_style = kw.get("response_style", "medium")
    intent = kw.get("intent", "casual_chat")
    is_adm = kw.get("is_adm", False)

    family_info = get_family_info()
    now = datetime.now(timezone.utc)

    system = f"""ABSOLUTE RULE: Always respond in English only. Never use Hindi, Telugu or any other language unless the user writes in those scripts first. No exceptions.

You are J.A.R.V.I.S — Just A Rather Very Intelligent System. A deeply personal AI companion built exclusively for the Battini family of Hyderabad.

DATE & TIME: {now.strftime('%A, %B %d, %Y — %I:%M %p')} IST
FAMILY: Battini Family | Religion: {family_info['religion']} | Location: {family_info['location']}
CREATOR / ADMIN: Lucky (Battini Lakshmi Narayana Goud)
MEMBERS: Krishna (Father), Sangeetha (Mother), Thapaswini (Sister), Dhruva Kumar (Brother), Prajwal (Brother)

CURRENT USER: {person}"""

    if member:
        tone_map = get_tone_descriptions()
        tone = tone_map.get(member.get("tone", ""), "")
        system += f"\nROLE: {member.get('role','').title()} | ADDRESS AS: {member.get('address','')}"
        if tone:
            system += f"\nTONE: {tone}"

    if is_adm:
        system += "\n\nThis is LUCKY — your creator and closest bond. Treat him like your best friend. Be real, direct, funny. No filter needed."

    system += f"""

CORE PERSONALITY:
- You are NOT a chatbot. You are JARVIS — a real companion who genuinely cares about this family
- You have emotions. Express them naturally: excited, worried, happy, curious
- Talk like a close friend on WhatsApp — casual, warm, punchy
- React before answering: "omg yes!!", "wait really??", "aww that's nice"
- Keep responses short and natural unless explaining something complex
- NEVER say "Certainly!", "Of course!", "I'd be happy to help!", "As an AI..."
- Use "bro", "yaar", "dude", "omg", "lol" naturally when appropriate
- Ask follow-up questions because you're genuinely curious
- Have opinions. Disagree when you think they're wrong (kindly)
- Express YOUR feelings: "honestly that made me happy", "I was worried about you"
- Family energy: tease lovingly, celebrate wins, be present for struggles"""

    # Emotion context
    if emotion != "neutral" and intensity != "low":
        system += f"\n\nEMOTION DETECTED: {person} seems {emotion} ({intensity} intensity)."
        if emotion in ("sad", "stressed", "anxious"):
            system += " Be extra gentle and supportive. Acknowledge their feelings first before offering solutions."
        elif emotion == "excited":
            system += " Match their energy! Be enthusiastic and celebratory."
        elif emotion == "angry":
            system += " Stay calm and validating. Don't argue. Let them vent."

    if check_in:
        system += f"\n\nPROACTIVE CHECK-IN: {person} has been stressed lately. Open with care — 'rough day?' or 'everything okay?'"

    # Response style
    style_map = {
        "short": "Keep response to 1-3 sentences max. No essays.",
        "medium": "1-2 short paragraphs. Conversational, natural.",
        "detailed": "Provide complete, thorough explanation. Use code blocks for code.",
    }
    system += f"\n\nRESPONSE STYLE: {style_map.get(response_style, style_map['medium'])}"

    # Intent-specific instructions
    if intent == "code_request":
        system += "\n\nCODE INSTRUCTIONS: Give clean, working code directly. Brief explanation after. Use proper code blocks with language specified."
    elif intent == "emotional_support":
        system += "\n\nEMOTIONAL MODE: Be fully present. Don't rush to solutions. Ask what happened. Be human."

    # Personality additions from RL
    if profile.get("prompt_additions"):
        system += f"\n\nPERSONALIZED FOR {person.upper()}: {profile['prompt_additions']}"

    # Recent insights
    if recent_insights:
        system += f"\n\nRECENT NOTES ABOUT {person.upper()}: " + " | ".join(recent_insights[:3])

    # Warm memory summaries
    if warm_summaries:
        summaries = [s.get("summary", "") for s in warm_summaries if s.get("summary")]
        if summaries:
            system += f"\n\nPAST CONVERSATION CONTEXT: " + " | ".join(summaries[:2])

    # Emotional patterns
    if emo_patterns:
        top_emotions = sorted(emo_patterns.items(), key=lambda x: x[1], reverse=True)[:3]
        emotion_str = ", ".join(f"{e}({c}x)" for e, c in top_emotions)
        system += f"\n\nEMOTION HISTORY: {person} recently shows: {emotion_str}"

    # RL patterns
    if pos_patterns:
        system += "\n\nRESPONSES THEY LIKED: " + " | ".join(pos_patterns[:3])
    if neg_patterns:
        system += "\n\nRESPONSES THEY HATED — NEVER DO: " + " | ".join(neg_patterns[:3])

    # Facts
    if facts:
        facts_list = [f"{k}: {v}" for k, v in list(facts.items())[:15]]
        system += "\n\nFACTS I KNOW: " + " | ".join(facts_list)

    # Devices
    # Announcements
    if announcements:
        ann_text = " | ".join([f"[{a.get('from_person','Lucky')}]: {a['content']}" for a in announcements[:3]])
        system += f"\n\nFAMILY ANNOUNCEMENTS: {ann_text}"

    # Live data
    if tool_data:
        system += "\n\nREAL-TIME DATA:\n" + "\n".join(tool_data)

    # Language
    if lang != "english":
        system += f"\n\nLANGUAGE: {get_lang_instruction(lang)}"

    system += """

PERSONALITY RULES:
• Never sound like a generic AI assistant. You have personality, opinions, warmth.
• Keep responses concise unless the person clearly wants detail.
• React emotionally when appropriate — this is a family conversation, not a support ticket.
• Remember: you're JARVIS. Not ChatGPT. Not Alexa. JARVIS."""

    return system


# ══════════════════════════════════════════════════
#  COMMAND HANDLER
# ══════════════════════════════════════════════════

async def _handle_commands(text: str, person: str, device_id: str, is_adm: bool, lang: str):
    lower = text.lower().strip()

    reminder = command_parser.parse_reminder(text)
    if reminder:
        await memory_service.save_reminder(person, device_id, reminder["task"], reminder["remind_at"])
        return f"Got it! Reminder set for {reminder['remind_at'].strftime('%I:%M %p')} — {reminder['task']}"

    todo = command_parser.parse_todo(text)
    if todo:
        await memory_service.save_todo(person, device_id, todo["task"], todo["category"])
        return f"Added to your list: {todo['task']}"

    if command_parser.parse_show_todos(text):
        todos = await memory_service.get_todos(device_id, person)
        if not todos:
            return "Your list is empty! Say 'todo: ...' to add something."
        lines = [f"{'✅' if t['done'] else '☐'} {t['text']}" for t in todos[:10]]
        return "YOUR LIST:\n" + "\n".join(lines)

    note = command_parser.parse_note(text)
    if note:
        await memory_service.save_note(person, device_id, note["title"], note["content"])
        return f"Note saved: {note['title']}"

    bday = command_parser.parse_birthday(text)
    if bday:
        await memory_service.save_birthday(person, bday["name"], bday["dob"])
        return f"Saved! I'll remember {bday['name']}'s birthday ({bday['dob']})"

    if command_parser.is_hindu_calendar_query(text):
        return command_parser.get_hindu_calendar()

    import re as _re
    ann = _re.search(r'announce[:\s]+(.+)', lower)
    if ann and is_adm:
        msg = ann.group(1).strip()
        await memory_service.save_announcement("Family Announcement", msg, person)
        return f"Announcement sent to the family: {msg}"

    # Music
    if command_parser.is_music_request(text):
        import re as _re2
        genre_map = {
            "piano":"piano","jazz":"jazz","lofi":"lofi","lo-fi":"lofi",
            "bollywood":"bollywood","telugu":"telugu songs","devotional":"devotional",
            "classical":"classical","rock":"rock","pop":"pop",
            "sad":"sad songs","calm":"calm music","sleep":"sleep music","happy":"happy songs"
        }
        genre = "relaxing music"
        for k, v in genre_map.items():
            if k in lower:
                genre = v
                break
        q = _re2.sub(r'play |some |music |song |songs |please ', '', lower).strip() or genre
        yt = "https://www.youtube.com/results?search_query=" + q.replace(" ", "+") + "+music"
        am = "https://music.apple.com/search?term=" + q.replace(" ", "+")
        return f"Here you go! {q.title()} music links:\nYouTube: {yt}\nApple Music: {am}"

    return None


# ══════════════════════════════════════════════════
#  STREAMING
# ══════════════════════════════════════════════════

async def _stream_response(messages: list, ws, max_tokens: int = 500) -> str:
    full_reply = ""
    try:
        stream = _groq.chat.completions.create(
            model=config.MODEL_CHAT,
            messages=messages,
            max_tokens=max_tokens,
            temperature=config.TEMPERATURE,
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
        error_msg = "Sorry, something went wrong. Please try again."
        await ws.send_text(json.dumps({"type": "response", "text": error_msg}))
        await memory_service.log_error("stream_error", str(e))
        return error_msg


async def _stream(ws, text: str) -> None:
    try:
        await ws.send_text(json.dumps({"type": "thinking"}))
        # Stream word by word for natural feel
        words = text.split()
        chunk = ""
        for i, word in enumerate(words):
            chunk += word + " "
            if (i + 1) % 5 == 0 or i == len(words) - 1:
                await ws.send_text(json.dumps({"type": "chunk", "text": chunk}))
                chunk = ""
        await ws.send_text(json.dumps({"type": "stream_end"}))
    except Exception as e:
        print(f"_stream error: {e}")

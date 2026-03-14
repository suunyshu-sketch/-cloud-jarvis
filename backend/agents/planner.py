import json
from groq import Groq
from backend.config import config

_groq = Groq(api_key=config.GROQ_API_KEY)

INTENT_TYPES = [
    "casual_chat",       # hi, how are you, bored, just talking
    "emotional_support", # sad, stressed, worried, need to vent
    "tool_request",      # weather, crypto, news, music
    "information_query", # what is X, explain X, how does X work
    "command",           # remind me, todo, note, birthday
    "code_request",      # write code, fix bug, explain code
    "family_query",      # about family members, relationships
]

_PLANNER_PROMPT = """You are a task planner for JARVIS AI assistant.
Analyze the user message and return a JSON plan.

Intent types: casual_chat, emotional_support, tool_request, information_query, command, code_request, family_query

Tools available: weather, crypto, news, cricket, currency, music, reminder, todo, note, url_summary

Respond ONLY with valid JSON like:
{"intent": "casual_chat", "tools": [], "response_style": "short", "needs_context": false}

response_style options: "short" (1-3 sentences), "medium" (1 paragraph), "detailed" (full explanation)
needs_context: true if the query needs memory/personality context loaded"""

async def plan(user_text: str, person: str, emotion: str) -> dict:
    try:
        # Fast heuristic check first (no API call needed)
        lower = user_text.lower().strip()

        # Greetings
        if lower in {"hi","hello","hey","hii","heyy","yo","sup","what's up","wassup"}:
            return {"intent": "casual_chat", "tools": [], "response_style": "short", "needs_context": True}

        # Emotional
        if emotion in {"sad","stressed","anxious","angry"} and len(user_text) > 20:
            return {"intent": "emotional_support", "tools": [], "response_style": "medium", "needs_context": True}

        # Code
        if any(w in lower for w in ["code","function","program","script","debug","error","python","javascript","java","html","css","sql"]):
            return {"intent": "code_request", "tools": [], "response_style": "detailed", "needs_context": False}

        # Commands
        from backend.services import command_parser
        if command_parser.parse_reminder(user_text) or command_parser.parse_todo(user_text) or \
           command_parser.parse_note(user_text) or command_parser.parse_birthday(user_text):
            return {"intent": "command", "tools": [], "response_style": "short", "needs_context": False}

        # Music
        if command_parser.is_music_request(user_text):
            return {"intent": "tool_request", "tools": ["music"], "response_style": "short", "needs_context": False}

        # Live data
        tools = []
        if command_parser.is_weather_query(user_text): tools.append("weather")
        if command_parser.is_crypto_query(user_text): tools.append("crypto")
        if command_parser.is_news_query(user_text): tools.append("news")
        if command_parser.is_cricket_query(user_text): tools.append("cricket")
        is_fx, *_ = command_parser.is_currency_query(user_text)
        if is_fx: tools.append("currency")
        if command_parser.is_url(user_text): tools.append("url_summary")

        if tools:
            return {"intent": "tool_request", "tools": tools, "response_style": "short", "needs_context": False}

        # Default — let Groq decide for ambiguous cases
        if len(user_text) > 50:
            resp = _groq.chat.completions.create(
                model=config.MODEL_PLANNER,
                messages=[
                    {"role": "system", "content": _PLANNER_PROMPT},
                    {"role": "user", "content": f"Person: {person}\nEmotion: {emotion}\nMessage: {user_text[:200]}"}
                ],
                max_tokens=config.MAX_TOKENS_PLANNER,
                temperature=0.1,
            )
            raw = resp.choices[0].message.content.strip()
            # Extract JSON
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))

        return {"intent": "casual_chat", "tools": [], "response_style": "medium", "needs_context": True}

    except Exception as e:
        print(f"planner error: {e}")
        return {"intent": "casual_chat", "tools": [], "response_style": "medium", "needs_context": True}

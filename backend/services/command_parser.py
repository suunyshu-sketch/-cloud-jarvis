"""
JARVIS — Command Parser Service
Phase 4: Pure functions that parse user text into structured commands.
No DB calls here — commands return data, the caller persists.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional


# ══════════════════════════════════════════════════════════
#  REMINDER PARSER
# ══════════════════════════════════════════════════════════

def parse_reminder(text: str) -> Optional[dict]:
    """
    Parses: "remind me at 6pm to call doctor"
            "set a reminder for 8:30am to take medicine"
            "remind me in 2 hours to check email"
    Returns: {"task": str, "remind_at": datetime} or None
    """
    lower = text.lower().strip()

    # Pattern: "remind me in X hours/minutes"
    rel_match = re.search(
        r'remind(?:er)?\s+(?:me\s+)?in\s+(\d+)\s+(hour|minute|min)s?\s+(?:to\s+)?(.+)',
        lower
    )
    if rel_match:
        amount = int(rel_match.group(1))
        unit = rel_match.group(2)
        task = rel_match.group(3).strip()
        delta = timedelta(hours=amount) if "hour" in unit else timedelta(minutes=amount)
        remind_at = datetime.now(timezone.utc) + delta
        return {"task": task, "remind_at": remind_at}

    # Pattern: "remind me at HH:MM am/pm to ..."
    abs_match = re.search(
        r'remind(?:er)?\s+(?:me\s+)?(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to\s+)?(.+)',
        lower
    )
    if not abs_match and "remind me" in lower:
        # Try more relaxed match
        abs_match = re.search(r'remind\s+me.*?(\d{1,2}(?::\d{2})?\s*(?:am|pm)).*?(?:to\s+)(.+)', lower)

    if abs_match:
        time_str = abs_match.group(1).strip()
        task = abs_match.group(2).strip()
        remind_at = _parse_time_string(time_str)
        if remind_at:
            return {"task": task, "remind_at": remind_at}

    return None


def _parse_time_string(time_str: str) -> Optional[datetime]:
    """Parse a time string like '6pm', '8:30am', '14:00' into today's datetime."""
    now = datetime.now(timezone.utc)
    time_str = time_str.strip().replace(" ", "").upper()

    formats = [
        ("%I%p",    False),
        ("%I:%M%p", False),
        ("%H:%M",   True),
        ("%H",      True),
    ]

    for fmt, is_24h in formats:
        try:
            t = datetime.strptime(time_str, fmt)
            remind_at = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if remind_at <= now:
                remind_at += timedelta(days=1)
            return remind_at
        except ValueError:
            continue

    return None


# ══════════════════════════════════════════════════════════
#  TODO PARSER
# ══════════════════════════════════════════════════════════

def parse_todo(text: str) -> Optional[dict]:
    """
    Parses: "add to my list: buy milk"
            "todo: call the doctor"
            "add task: finish report"
    Returns: {"task": str, "category": str} or None
    """
    lower = text.lower().strip()
    patterns = [
        r'(?:add\s+to\s+(?:my\s+)?(?:list|todo|tasks?)|todo:|task:|add\s+task:?)\s*[:\-]?\s*(.+)',
    ]
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            task = m.group(1).strip()
            category = _guess_category(task)
            return {"task": task, "category": category}
    return None


def parse_show_todos(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "show my list", "my todos", "my tasks", "show tasks",
        "todo list", "task list", "what's on my list"
    ])


def _guess_category(task: str) -> str:
    lower = task.lower()
    if any(w in lower for w in ["buy", "shop", "grocery", "market", "milk", "vegetables"]):
        return "shopping"
    if any(w in lower for w in ["doctor", "medicine", "hospital", "health", "gym", "exercise"]):
        return "health"
    if any(w in lower for w in ["work", "office", "meeting", "call", "email", "report", "project"]):
        return "work"
    if any(w in lower for w in ["family", "mom", "dad", "amma", "nanna", "birthday", "wedding"]):
        return "family"
    return "general"


# ══════════════════════════════════════════════════════════
#  NOTE PARSER
# ══════════════════════════════════════════════════════════

def parse_note(text: str) -> Optional[dict]:
    """
    Parses: "note: meeting at 3pm"
            "save note: my password is ..."
            "remember this: ..."
    Returns: {"title": str, "content": str} or None
    """
    lower = text.lower().strip()
    m = re.search(
        r'(?:save\s+note|note:|remember\s+this|jot\s+this\s+down)[:\-]?\s*(.+)',
        lower, re.IGNORECASE
    )
    if m:
        content = text[m.start(1):].strip()   # Preserve original case
        title = (content[:30] + "...") if len(content) > 30 else content
        return {"title": title, "content": content}
    return None


# ══════════════════════════════════════════════════════════
#  BIRTHDAY PARSER
# ══════════════════════════════════════════════════════════

def parse_birthday(text: str) -> Optional[dict]:
    """
    Parses: "dad's birthday is March 15"
            "Krishna birthday is on 5th June 1965"
    Returns: {"name": str, "dob": str (YYYY-MM-DD), "relation": str} or None
    """
    lower = text.lower()
    m = re.search(r"(.+?)(?:'s)?\s+birthday\s+(?:is\s+)?(?:on\s+)?(.+)", lower)
    if not m:
        return None

    raw_name = m.group(1).strip()
    date_str = m.group(2).strip()

    dob = _parse_date_string(date_str)
    if not dob:
        return None

    return {"name": raw_name.title(), "dob": dob, "relation": ""}


def _parse_date_string(date_str: str) -> Optional[str]:
    """Returns YYYY-MM-DD or None."""
    date_str = date_str.strip()
    formats = [
        "%B %d",       # March 15
        "%B %dst",     # March 1st
        "%B %dnd",     # June 2nd
        "%B %drd",
        "%B %dth",
        "%d %B",       # 15 March
        "%B %d %Y",    # March 15 1990
        "%d/%m/%Y",    # 15/03/1990
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]
    # Remove ordinal suffixes
    clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str, flags=re.IGNORECASE)

    for fmt in formats:
        try:
            d = datetime.strptime(clean.strip(), fmt)
            year = d.year if d.year != 1900 else datetime.now().year - 25
            return f"{year}-{d.month:02d}-{d.day:02d}"
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════
#  STATIC QUERIES
# ══════════════════════════════════════════════════════════

def is_hindu_calendar_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "rahu kalam", "gulika", "pooja time", "auspicious",
        "muhurta", "shubh", "brahma muhurta"
    ])


def is_cricket_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "cricket", "ipl", "test match", "odi", "t20",
        "wicket", "batting", "bowling", "score"
    ])


def is_weather_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "weather", "temperature", "rain", "forecast",
        "climate", "hot", "cold today", "humidity"
    ])


def is_news_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "news", "headlines", "latest news", "what happened",
        "current events", "today's news"
    ])


def is_crypto_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "bitcoin", "btc", "ethereum", "eth", "crypto",
        "dogecoin", "doge", "coin price"
    ])


def is_stock_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in [
        "stock", "share price", "nse", "bse", "sensex",
        "nifty", "reliance", "tcs", "infosys"
    ])


def is_currency_query(text: str) -> tuple[bool, str, str, float]:
    """Returns (is_query, from_currency, to_currency, amount)"""
    lower = text.lower()
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(usd|dollar|euros?|gbp|eur|jpy|aud|cad|sgd)\s+(?:to|in|into)\s*(inr|rupee|rs|usd|euro|gbp)',
        r'(?:convert|exchange|rate)\s+(?:from\s+)?(usd|dollar|euros?|gbp|eur|inr|jpy|aud)\s+(?:to\s+)?(inr|usd|euros?|gbp|rupee|rs)',
        r'(usd|dollar|euro|gbp|inr|jpy|aud)\s+(?:to|vs|against)\s+(inr|usd|euro|gbp|rupee|rs|jpy|aud)',
    ]
    currency_map = {
        "dollar": "USD", "usd": "USD", "euro": "EUR", "euros": "EUR", "eur": "EUR",
        "gbp": "GBP", "pound": "GBP", "jpy": "JPY", "yen": "JPY",
        "aud": "AUD", "cad": "CAD", "sgd": "SGD",
        "inr": "INR", "rupee": "INR", "rs": "INR",
    }
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            groups = m.groups()
            amount = 1.0
            if len(groups) == 3 and groups[0].replace('.', '').isdigit():
                amount = float(groups[0])
                from_c = currency_map.get(groups[1], groups[1].upper())
                to_c   = currency_map.get(groups[2], groups[2].upper())
            else:
                from_c = currency_map.get(groups[-2], (groups[-2] or "USD").upper())
                to_c   = currency_map.get(groups[-1], (groups[-1] or "INR").upper())
            return True, from_c, to_c, amount

    if any(w in lower for w in ["exchange rate", "currency", "conversion", "convert money"]):
        return True, "USD", "INR", 1.0

    return False, "", "", 0.0


def is_flight_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["flight", "airline", "landing", "departure", "gate", "delayed"])


def is_url(text: str) -> Optional[str]:
    """Returns URL if message is asking to summarize a URL."""
    m = re.search(r'https?://[^\s]+', text)
    if m and any(w in text.lower() for w in ["summarize", "summary", "explain", "what is this", "read"]):
        return m.group()
    return None


def is_play_music_command(text: str) -> Optional[str]:
    """Returns query string if user is asking to play music, else None."""
    lower = text.lower()
    m = re.search(r'\b(?:play|listen to|put on|queue)\s+(.+)', lower)
    if m:
        return m.group(1).strip()
    return None


def get_hindu_calendar() -> str:
    """Static Rahu Kalam / Gulika times by weekday."""
    day = datetime.now().weekday()
    rahu = {
        0: "7:30-9:00 AM",  1: "3:00-4:30 PM",
        2: "12:00-1:30 PM", 3: "1:30-3:00 PM",
        4: "10:30 AM-12:00 PM", 5: "9:00-10:30 AM", 6: "4:30-6:00 PM"
    }
    gulika = {
        0: "1:30-3:00 PM",  1: "12:00-1:30 PM",
        2: "10:30 AM-12:00 PM", 3: "9:00-10:30 AM",
        4: "7:30-9:00 AM",  5: "6:00-7:30 AM", 6: "3:00-4:30 PM"
    }
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return (
        f"Today ({day_names[day]}) — "
        f"Rahu Kalam: {rahu[day]} | Gulika Kalam: {gulika[day]} | "
        f"Brahma Muhurta: 4:24–5:12 AM | Evening Pooja: 6:00–8:00 PM"
    )

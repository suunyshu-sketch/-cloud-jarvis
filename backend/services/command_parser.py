import re
from datetime import datetime, timezone, timedelta
from typing import Optional

def parse_reminder(text: str) -> Optional[dict]:
    lower = text.lower()
    patterns = [
        r'remind me (?:at|by) (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to\s+)?(.+)',
        r'set (?:a )?reminder (?:for|at) (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to\s+)?(.+)',
        r'remind me in (\d+)\s*(hour|minute|min|hr)s?\s+(?:to\s+)?(.+)',
        r'remind me to (.+?) at (\d{1,2}(?::\d{2})?\s*(?:am|pm))',
    ]
    now = datetime.now(timezone.utc)

    m = re.search(r'remind me in (\d+)\s*(hour|minute|min|hr)s?\s+(?:to\s+)?(.+)', lower)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        task = m.group(3).strip()
        delta = timedelta(hours=amount) if 'hour' in unit or 'hr' in unit else timedelta(minutes=amount)
        return {"task": task, "remind_at": now + delta}

    m = re.search(r'remind me (?:at|by) (\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(?:to\s+)?(.+)', lower)
    if not m:
        m = re.search(r'remind me to (.+?) at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?', lower)
        if m:
            task = m.group(1).strip()
            hour = int(m.group(2))
            minute = int(m.group(3) or 0)
            ampm = m.group(4)
        else:
            return None
    else:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        task = m.group(4).strip()

    if ampm == 'pm' and hour != 12:
        hour += 12
    elif ampm == 'am' and hour == 12:
        hour = 0

    remind_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if remind_dt <= now:
        remind_dt += timedelta(days=1)
    return {"task": task, "remind_at": remind_dt}

def parse_todo(text: str) -> Optional[dict]:
    lower = text.lower().strip()
    patterns = [
        r'^todo[:\s]+(.+)',
        r'^add (?:to my )?(?:todo|list)[:\s]+(.+)',
        r'^task[:\s]+(.+)',
    ]
    for p in patterns:
        m = re.match(p, lower)
        if m:
            task = m.group(1).strip()
            cat = "work" if any(w in task for w in ["work","meeting","project","email","call"]) else \
                  "shopping" if any(w in task for w in ["buy","get","purchase","shop"]) else "general"
            return {"task": task, "category": cat}
    return None

def parse_show_todos(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in ["show my todos","my list","my tasks","show todos","show tasks","pending tasks"])

def parse_note(text: str) -> Optional[dict]:
    lower = text.lower().strip()
    m = re.match(r'^note[:\s]+(.+)', lower, re.DOTALL)
    if m:
        content = m.group(1).strip()
        title = content[:40] + ("..." if len(content) > 40 else "")
        return {"title": title, "content": content}
    m = re.match(r'^save note[:\s]+(.+)', lower, re.DOTALL)
    if m:
        content = m.group(1).strip()
        return {"title": content[:40], "content": content}
    return None

def parse_birthday(text: str) -> Optional[dict]:
    lower = text.lower()
    m = re.search(r"(.+?)(?:'s)? birthday is (?:on )?(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)", lower)
    if m:
        return {"name": m.group(1).strip().title(), "dob": m.group(2).strip()}
    return None

def is_weather_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["weather","temperature","rain","sunny","forecast","climate","hot outside","cold outside"])

def is_news_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["news","latest","what happened","current events","today's news","headlines"])

def is_cricket_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["cricket","ipl","match","score","batting","bowling","wicket","test match","odi"])

def is_crypto_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["bitcoin","btc","ethereum","eth","crypto","cryptocurrency","dogecoin","doge","nft"])

def is_currency_query(text: str):
    lower = text.lower()
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(usd|inr|eur|gbp|jpy|aud)\s+(?:to|in)\s+(usd|inr|eur|gbp|jpy|aud)',
        r'convert\s+(\d+(?:\.\d+)?)\s*(usd|inr|eur)\s+to\s+(usd|inr|eur)',
        r'(usd|inr|eur)\s+to\s+(usd|inr|eur)',
    ]
    for p in patterns:
        m = re.search(p, lower)
        if m:
            groups = m.groups()
            if len(groups) >= 3:
                try:
                    amount = float(groups[0])
                    return True, groups[1].upper(), groups[2].upper(), amount
                except (ValueError, IndexError):
                    pass
            elif len(groups) == 2:
                return True, groups[0].upper(), groups[1].upper(), 1.0
    return False, "", "", 0

def is_stock_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["stock","share price","nifty","sensex","bse","nse","equity"])

def is_url(text: str) -> Optional[str]:
    m = re.search(r'https?://[^\s]+', text)
    return m.group(0) if m else None

def is_music_request(text: str) -> bool:
    lower = text.lower()
    return any(k in lower for k in [
        "play music","play song","play some","play piano","play jazz","play lofi",
        "play bollywood","play telugu","music please","play something","put on music",
        "play calm","play sad","play happy","play devotional","play classical"
    ])

def is_hindu_calendar_query(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ["hindu calendar","panchang","tithi","nakshatra","festival today"])

def get_hindu_calendar() -> str:
    now = datetime.now(timezone.utc)
    return f"Today is {now.strftime('%A, %B %d, %Y')}. For detailed panchang and tithi information, visit drikpanchang.com"

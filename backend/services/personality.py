import json
import re
from datetime import datetime, timezone
from typing import Tuple, Optional
from backend.db.connection import get_pool
from backend.config import config

_EMOTION_MAP = {
    "happy":    ["happy","joy","excited","great","amazing","wonderful","yay","awesome","love it","so good"],
    "sad":      ["sad","crying","cry","upset","unhappy","miserable","heartbroken","hurt","pain","miss you"],
    "stressed": ["stressed","stress","pressure","overwhelmed","too much","exhausted","tired","burden","deadline"],
    "anxious":  ["anxious","anxiety","worried","worry","nervous","scared","fear","panic","tense"],
    "angry":    ["angry","mad","furious","annoyed","frustrated","irritated","hate","rage","fed up"],
    "excited":  ["excited","can't wait","thrilled","pumped","hype","omg","wow","finally","yes yes"],
    "bored":    ["bored","boring","nothing to do","no work","free","idle","timepass","dull"],
    "grateful": ["thank","thanks","grateful","appreciate","thankful","blessed","means a lot"],
    "anxious":  ["anxious","nervous","tense","uneasy","worried"],
}

_HINDI_EMOTIONS = {
    "happy": ["khush","mast","badhiya","zabardast","maja aa gaya"],
    "sad":   ["dukhi","rona","udaas","takleef"],
    "stressed": ["tension","pareshaan","thak gaya"],
}

_TELUGU_EMOTIONS = {
    "happy": ["santosham","chala baagundi","superr"],
    "sad":   ["dukhanga","baadhaga"],
    "stressed": ["stress","kashtam"],
}

def detect_emotion(text: str) -> Tuple[str, str]:
    lower = text.lower()
    scores = {}

    for emotion, keywords in _EMOTION_MAP.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[emotion] = score

    for emotion, keywords in _HINDI_EMOTIONS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[emotion] = scores.get(emotion, 0) + score

    for emotion, keywords in _TELUGU_EMOTIONS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[emotion] = scores.get(emotion, 0) + score

    if not scores:
        return "neutral", "low"

    dominant = max(scores, key=scores.get)
    intensity = "high" if scores[dominant] >= 3 else "medium" if scores[dominant] >= 2 else "low"
    return dominant, intensity

async def save_emotion(person: str, emotion: str, intensity: str, context: str = "") -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO emotional_history (person, emotion, intensity, context) VALUES ($1,$2,$3,$4)",
                person, emotion, intensity, context[:200]
            )
    except Exception as e:
        print(f"save_emotion error: {e}")

async def get_emotional_patterns(person: str) -> dict:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT emotion, COUNT(*) as count FROM emotional_history
                   WHERE person=$1 AND created_at > NOW() - INTERVAL '30 days'
                   GROUP BY emotion ORDER BY count DESC LIMIT 5""",
                person
            )
            return {r["emotion"]: r["count"] for r in rows}
    except Exception:
        return {}

async def get_emotional_trend(person: str) -> str:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT emotion, intensity FROM emotional_history
                   WHERE person=$1 ORDER BY created_at DESC LIMIT 10""",
                person
            )
            if not rows:
                return ""
            emotions = [r["emotion"] for r in rows]
            negative = ["sad","stressed","anxious","angry"]
            neg_count = sum(1 for e in emotions if e in negative)
            if neg_count >= 6:
                return f"{person} has been frequently stressed/sad lately — be extra supportive"
            pos_count = sum(1 for e in emotions if e in ["happy","excited","grateful"])
            if pos_count >= 6:
                return f"{person} has been in a great mood lately — match the positive energy"
            return ""
    except Exception:
        return ""

async def get_personality_profile(person: str) -> dict:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT profile_json, prompt_additions FROM personality_profiles WHERE person=$1", person
            )
            if row:
                profile = row["profile_json"] or {}
                if isinstance(profile, str):
                    profile = json.loads(profile)
                profile["prompt_additions"] = row["prompt_additions"] or ""
                return profile
            return {}
    except Exception:
        return {}

async def update_personality_profile(person: str, updates: dict, prompt_additions: str = "") -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT profile_json FROM personality_profiles WHERE person=$1", person
            )
            if existing:
                current = existing["profile_json"] or {}
                if isinstance(current, str):
                    current = json.loads(current)
                current.update(updates)
                await conn.execute(
                    "UPDATE personality_profiles SET profile_json=$1, prompt_additions=$2, updated_at=NOW() WHERE person=$3",
                    json.dumps(current), prompt_additions, person
                )
            else:
                await conn.execute(
                    "INSERT INTO personality_profiles (person, profile_json, prompt_additions) VALUES ($1,$2,$3)",
                    person, json.dumps(updates), prompt_additions
                )
    except Exception as e:
        print(f"update_personality_profile error: {e}")

async def get_recent_insights(person: str, limit: int = 5) -> list:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT insight FROM conversation_insights WHERE person=$1 ORDER BY created_at DESC LIMIT $2",
                person, limit
            )
            return [r["insight"] for r in rows]
    except Exception:
        return []

async def save_insight(person: str, insight: str) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO conversation_insights (person, insight, week_of) VALUES ($1,$2,CURRENT_DATE)",
                person, insight[:300]
            )
    except Exception as e:
        print(f"save_insight error: {e}")

async def should_check_in(person: str) -> bool:
    try:
        trend = await get_emotional_trend(person)
        return "stressed" in trend or "sad" in trend
    except Exception:
        return False

async def get_old_insight_to_surface(person: str) -> str:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT insight FROM conversation_insights
                   WHERE person=$1 AND created_at < NOW() - INTERVAL '7 days'
                   ORDER BY created_at DESC LIMIT 1""",
                person
            )
            return row["insight"] if row else ""
    except Exception:
        return ""

async def auto_save_insights(user_text: str, reply: str, person: str, emotion: str, intensity: str) -> None:
    try:
        await save_emotion(person, emotion, intensity, user_text[:100])
        fact_triggers = ["my name is","i am from","i work at","i study","i live in",
                         "i like","i love","i hate","my favourite","i prefer"]
        lower = user_text.lower()
        if any(t in lower for t in fact_triggers):
            from backend.services import memory_service
            key = re.sub(r'[^a-z\s]','', lower[:50]).strip()
            await memory_service.save_fact(key, user_text[:150], person, 0.7)
    except Exception as e:
        print(f"auto_save_insights error: {e}")

async def extract_facts_background(text: str, person: str) -> None:
    try:
        from backend.services import memory_service
        patterns = [
            (r"my name is (\w+)", "name"),
            (r"i(?:'m| am) from ([A-Za-z\s]+)", "from"),
            (r"i(?:'m| am) (\d+) years old", "age"),
            (r"i (?:work|study) at ([A-Za-z\s]+)", "workplace"),
            (r"i (?:like|love) ([A-Za-z\s,]+)", "likes"),
        ]
        for pattern, key in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                await memory_service.save_fact(f"{person}_{key}", m.group(1).strip(), person, 0.8)
    except Exception as e:
        print(f"extract_facts_background error: {e}")

async def analyze_and_update_personality(person: str, device_id: str) -> None:
    try:
        patterns = await get_emotional_patterns(person)
        trend = await get_emotional_trend(person)
        updates = {
            "emotion_patterns": patterns,
            "last_analyzed": datetime.now(timezone.utc).isoformat(),
        }
        prompt_addition = ""
        if "stressed" in patterns and patterns.get("stressed", 0) > 3:
            prompt_addition += f" {person} has been stressed lately — be extra supportive and gentle."
        if "happy" in patterns and patterns.get("happy", 0) > 5:
            prompt_addition += f" {person} is generally in a good mood — match their energy."
        await update_personality_profile(person, updates, prompt_addition)
    except Exception as e:
        print(f"analyze_and_update_personality error: {e}")

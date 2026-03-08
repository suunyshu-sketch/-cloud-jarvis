"""
JARVIS — Path A: Deep Personality, Emotion, and Insight Engine
"""
import asyncio
import json
import re
import random
from datetime import datetime, timedelta, timezone
from backend.db.connection import get_pool
from backend import config

# ══════════════════════════════════════════════════════════
#  EMOTION DETECTION
# ══════════════════════════════════════════════════════════

EMOTION_BANKS = {
    "sad": [
        "sad","unhappy","depressed","crying","tears","heartbroken","hurt","lonely",
        "miss","lost","empty","numb","hopeless","disappointed","gutted","devastated",
        "low","down","not okay","not fine","breaking","broken","struggling",
        "chala sad","sad ga","badhaga","dukkham","dukha","rona","dil dukha","bura lag"
    ],
    "angry": [
        "angry","furious","mad","irritated","frustrated","pissed","annoyed","hate",
        "sick of","fed up","done with","can't stand","idiots","stupid","nonsense",
        "gussa","bahut gussa","krodham","kopam","kodiga","chira","irritating"
    ],
    "happy": [
        "happy","excited","amazing","love","great","awesome","brilliant","ecstatic",
        "thrilled","over the moon","finally","yes","won","got it","nailed","proud",
        "khush","bahut khush","anandanga","super","fantastic","yesss","let's go"
    ],
    "anxious": [
        "worried","scared","nervous","anxious","tense","fear","afraid","panic",
        "stressed","overwhelmed","can't sleep","overthinking","what if","pressure",
        "deadline","tension","ghabra","dar lag","bhayam","tension ga","pressure lo"
    ],
    "tired": [
        "tired","exhausted","drained","sleepy","fatigue","no energy","burn out",
        "worn out","can't anymore","done","too much","over it",
        "thak gaya","bahut thaka","antla pade","nidra vastuundi","chala tired"
    ],
    "bored": [
        "bored","boring","nothing to do","dull","same old","meh","whatever",
        "not interested","time pass","killing time","bore ga","bore aavutundi"
    ],
    "lonely": [
        "lonely","alone","no one","nobody","missing","miss you","wish you were",
        "by myself","isolated","left out","forgotten","ignored"
    ],
    "proud": [
        "proud","achieved","accomplished","did it","made it","success","cleared",
        "passed","selected","got the job","got admission","rank","first",
        "proud ga","bahut proud"
    ],
    "confused": [
        "confused","don't understand","what is","no idea","lost","unclear",
        "make sense","explain","how does","why is","ardam kaatledu","samajh nahi"
    ],
}


def detect_emotion(text: str) -> tuple[str, str]:
    """Returns (emotion, intensity) — 'neutral'/'low' if nothing detected."""
    lower = text.lower()
    scores = {}
    for emotion, words in EMOTION_BANKS.items():
        hits = sum(1 for w in words if w in lower)
        if hits:
            scores[emotion] = hits

    if not scores:
        return "neutral", "low"

    top = max(scores, key=scores.get)
    intensity = "high" if scores[top] >= 3 else "medium" if scores[top] == 2 else "low"
    return top, intensity


# ══════════════════════════════════════════════════════════
#  EMOTIONAL HISTORY
# ══════════════════════════════════════════════════════════

async def save_emotional_event(
    person: str, device_id: str,
    emotion: str, intensity: str, context: str
) -> None:
    if emotion == "neutral":
        return
    try:
        pool = get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO emotional_history
                   (person, device_id, emotion, intensity, context,
                    time_of_day, day_of_week, timestamp)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                person, device_id, emotion, intensity, context[:200],
                now.strftime("%H:%M"), now.strftime("%A"), now
            )
    except Exception as e:
        print(f"save_emotional_event error: {e}")


async def get_emotional_patterns(person: str) -> dict | None:
    try:
        from collections import Counter
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT emotion, intensity, context, time_of_day, day_of_week
                   FROM emotional_history WHERE person=$1
                   ORDER BY id DESC LIMIT 60""",
                person
            )
        if not rows:
            return None

        emotion_counts = Counter(r["emotion"] for r in rows)
        high_intensity = [r for r in rows if r["intensity"] == "high"]
        recent_emotions = [r["emotion"] for r in rows[:5]]

        return {
            "most_common_emotion": emotion_counts.most_common(1)[0][0],
            "recent_mood": recent_emotions[0] if recent_emotions else "neutral",
            "last_5": recent_emotions,
            "emotion_counts": dict(emotion_counts),
            "high_intensity": [r["context"] for r in high_intensity[:3]],
        }
    except Exception as e:
        print(f"get_emotional_patterns error: {e}")
        return None


async def should_check_in(person: str) -> dict | None:
    """
    Returns a dict with emotion + context if person was recently distressed.
    Triggers proactive check-in when they next say hello.
    """
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT emotion, context FROM emotional_history
                   WHERE person=$1
                     AND emotion IN ('sad','anxious','angry')
                     AND intensity IN ('high','medium')
                     AND timestamp > NOW() - INTERVAL '20 hours'
                   ORDER BY id DESC LIMIT 1""",
                person
            )
        return {"emotion": row["emotion"], "context": row["context"]} if row else None
    except:
        return None


# ══════════════════════════════════════════════════════════
#  CONVERSATION INSIGHTS
# ══════════════════════════════════════════════════════════

async def save_insight(
    person: str, insight: str,
    insight_type: str = "general", confidence: str = "medium"
) -> None:
    if not insight or len(insight) < 15:
        return
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO conversation_insights
                   (person, insight, insight_type, confidence, created_at)
                   VALUES ($1,$2,$3,$4,NOW())""",
                person, insight[:500], insight_type, confidence
            )
    except Exception as e:
        print(f"save_insight error: {e}")


async def get_recent_insights(person: str, limit: int = 5) -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT insight, insight_type FROM conversation_insights
                   WHERE person=$1 ORDER BY id DESC LIMIT $2""",
                person, limit
            )
        return [r["insight"] for r in rows]
    except:
        return []


async def get_old_insight_to_surface(person: str) -> str | None:
    """20% chance: surface a random old insight for the 'I remember...' effect."""
    if random.random() > 0.20:
        return None
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT insight FROM conversation_insights
                   WHERE person=$1
                     AND created_at < NOW() - INTERVAL '3 days'
                     AND insight_type IN ('emotional','observation','personal')
                   ORDER BY RANDOM() LIMIT 1""",
                person
            )
        return row["insight"] if row else None
    except:
        return None


# ══════════════════════════════════════════════════════════
#  DEEP PERSONALITY PROFILES
# ══════════════════════════════════════════════════════════

async def get_personality_profile(person: str) -> dict | None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT raw_profile, behavioral_patterns, communication_style,
                          emotional_triggers, topics_they_love, topics_to_avoid,
                          how_they_deflect, inside_knowledge
                   FROM personality_profiles WHERE person=$1""",
                person
            )
        if not row:
            return None
        return {
            "raw_profile":          row["raw_profile"],
            "behavioral_patterns":  row["behavioral_patterns"],
            "communication_style":  row["communication_style"],
            "emotional_triggers":   row["emotional_triggers"],
            "topics_they_love":     row["topics_they_love"],
            "topics_to_avoid":      row["topics_to_avoid"],
            "how_they_deflect":     row["how_they_deflect"],
            "inside_knowledge":     row["inside_knowledge"],
        }
    except:
        return None


async def save_personality_profile(person: str, profile: dict) -> None:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO personality_profiles
                   (person, raw_profile, behavioral_patterns, communication_style,
                    emotional_triggers, topics_they_love, topics_to_avoid,
                    how_they_deflect, inside_knowledge, last_updated)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW())
                   ON CONFLICT (person) DO UPDATE SET
                     raw_profile=$2, behavioral_patterns=$3, communication_style=$4,
                     emotional_triggers=$5, topics_they_love=$6, topics_to_avoid=$7,
                     how_they_deflect=$8, inside_knowledge=$9, last_updated=NOW()""",
                person,
                profile.get("raw_profile", ""),
                profile.get("behavioral_patterns", ""),
                profile.get("communication_style", ""),
                profile.get("emotional_triggers", ""),
                profile.get("topics_they_love", ""),
                profile.get("topics_to_avoid", ""),
                profile.get("how_they_deflect", ""),
                profile.get("inside_knowledge", ""),
            )
    except Exception as e:
        print(f"save_personality_profile error: {e}")


async def analyze_and_update_personality(person: str, device_id: str) -> None:
    """
    LLM-based deep personality analysis.
    Runs every 10 messages as a background task — never blocks the main flow.
    """
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        pool = get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content, timestamp FROM memories
                   WHERE device_id=$1 ORDER BY id DESC LIMIT 50""",
                device_id
            )

        if len(rows) < 5:
            return

        existing = await get_personality_profile(person)
        existing_str = json.dumps(existing) if existing else "No profile yet."
        convo = "\n".join([
            f"{r['role'].upper()} [{str(r['timestamp'])[:16]}]: {r['content']}"
            for r in reversed(rows)
        ])

        prompt = f"""You are analyzing conversations to build a DEEP human psychological profile.
This is NOT about facts. This is about understanding who this person REALLY is.

Person: {person}
Existing profile: {existing_str}

Conversations:
{convo[:4000]}

Return ONLY valid JSON with these exact keys:
{{
  "raw_profile": "2-3 sentence description of who this person is at their core",
  "behavioral_patterns": "How they actually behave",
  "communication_style": "How they talk — formal/casual, short/long messages",
  "emotional_triggers": "What makes them genuinely happy, stressed, sad",
  "topics_they_love": "Topics they get animated about",
  "topics_to_avoid": "Topics they go quiet on or seem uncomfortable with",
  "how_they_deflect": "How they avoid serious topics",
  "inside_knowledge": "Specific things only someone who knows them well would know"
}}"""

        resp = client.chat.completions.create(
            model=config.MODEL_FAST,
            messages=[
                {"role": "system", "content": "You are a psychological analyst. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600, temperature=0.3
        )

        raw = re.sub(r'```json|```', '', resp.choices[0].message.content.strip()).strip()
        profile = json.loads(raw)
        await save_personality_profile(person, profile)
        await save_insight(
            person,
            f"Profile updated: {profile.get('raw_profile','')}",
            "personality", "high"
        )
        print(f"🧠  Personality profile updated for {person}")

    except Exception as e:
        print(f"analyze_and_update_personality error: {e}")


async def auto_save_insights(
    user_text: str, reply: str,
    person: str, emotion: str, intensity: str
) -> None:
    """Silently extract and persist behavioral observations from every message."""
    try:
        if emotion != "neutral":
            await save_emotional_event(person, "", emotion, intensity, user_text[:200])

        if len(user_text) < 20:
            return

        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=config.MODEL_FAST,
            messages=[
                {"role": "system", "content": (
                    "You extract ONE behavioral observation about a person from their message. "
                    "Look for: how they communicate, what they care about, personality quirks. "
                    "Return ONE insight sentence or 'NONE'."
                )},
                {"role": "user", "content": f"Person: {person}\nMessage: {user_text}\nEmotion: {emotion}"}
            ],
            max_tokens=80, temperature=0.3
        )
        insight = resp.choices[0].message.content.strip()
        if insight and insight.upper() != "NONE" and len(insight) > 15:
            itype = "emotional" if emotion != "neutral" else "observation"
            await save_insight(person, insight, itype,
                               intensity if emotion != "neutral" else "low")
    except:
        pass


async def extract_facts_background(text: str, person: str) -> None:
    """Auto-extract personal facts when the user self-discloses."""
    try:
        from groq import Groq
        from backend.services.memory_service import save_fact
        client = Groq(api_key=config.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=config.MODEL_FAST,
            messages=[
                {"role": "system", "content": (
                    "Extract user facts as JSON {key:value}. "
                    "Keys: name,city,job,hobby,age,preference. "
                    "Only clearly stated facts. Return {} if nothing. Raw JSON only."
                )},
                {"role": "user", "content": text}
            ],
            max_tokens=100
        )
        raw = re.sub(r'```json|```', '', resp.choices[0].message.content.strip()).strip()
        extracted = json.loads(raw)
        for k, v in extracted.items():
            if v:
                await save_fact(f"{person}_{k}", str(v), person)
    except:
        pass

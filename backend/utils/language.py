"""
JARVIS — Language Detection & Instruction Builder
Detects Telugu, Hindi, and English from text + transliteration.
"""
import re

# Telugu Unicode block
_TELUGU_RE = re.compile(r'[\u0C00-\u0C7F]')
# Hindi / Devanagari block
_HINDI_RE   = re.compile(r'[\u0900-\u097F]')

# Common Telugu transliteration words (Roman-script Telugu)
_TELUGU_TRANSLIT = {
    "nenu", "nenu", "meeru", "miru", "ela", "undi", "cheyyi", "cheyandi",
    "ela undi", "baagundi", "ledu", "chala", "super", "antu", "antav",
    "chestanu", "chesanu", "telugu", "okka", "rendu", "moodu", "naaku",
    "maku", "maaku", "naku", "manchi", "cheddhu", "pillalu", "pillaadu",
    "akka", "anna", "nanna", "amma", "thambhi", "chelli", "ayya", "gaaru",
    "garu", "babu", "baabu", "em", "emi", "enti", "evaru", "enduku",
    "cheppu", "cheppandi", "marchipoma", "gurinchi", "kosam", "vallu",
    "vaallu", "okate", "okadu", "aavida", "ayana", "medam", "saaviri",
    "sampada", "ikkada", "akkada", "ippudu", "appudu", "rojullu",
    "chustanu", "chestam", "cheyyali", "vaddu", "vachhu", "pothanu",
    "badhaga", "dukkham", "chala sad", "sad ga", "kopanga", "gussa",
    "happy ga", "anandanga", "bore ga", "tired ga", "thak gaya"
}

# Common Hindi transliteration words
_HINDI_TRANSLIT = {
    "kya", "kyun", "kaise", "kab", "kaun", "kahan", "kitna", "kitne",
    "hai", "hain", "tha", "thi", "the", "hoga", "hogi", "honge",
    "mujhe", "tumhe", "usse", "hume", "aap", "tum", "main", "woh",
    "yeh", "jo", "jab", "tab", "aur", "lekin", "par", "magar",
    "nahi", "nahi", "nahin", "haan", "bilkul", "zaroor", "abhi",
    "bahut", "thoda", "sirf", "kaafi", "accha", "theek", "sahi",
    "karo", "karna", "karoge", "bolo", "sunao", "batao",
    "bhai", "yaar", "dost", "bhaiya", "didi", "aunty", "uncle",
    "ghabra", "dar lag", "bahut gussa", "bahut khush", "thak gaya",
    "bahut thaka", "bore ho", "kuch nahi", "samajh nahi"
}


def detect_language(text: str) -> str:
    """
    Returns 'telugu', 'hindi', or 'english'.
    Checks Unicode script first, then transliteration word banks.
    """
    if not text:
        return "english"

    lower = text.lower()

    # Script detection (strongest signal)
    tel_chars = len(_TELUGU_RE.findall(text))
    hin_chars = len(_HINDI_RE.findall(text))

    if tel_chars >= 2:
        return "telugu"
    if hin_chars >= 2:
        return "hindi"

    # Transliteration detection (word bank)
    words = set(re.findall(r'\b\w+\b', lower))
    tel_hits = len(words & _TELUGU_TRANSLIT)
    hin_hits = len(words & _HINDI_TRANSLIT)

    # Also check multi-word phrases
    for phrase in _TELUGU_TRANSLIT:
        if " " in phrase and phrase in lower:
            tel_hits += 2
    for phrase in _HINDI_TRANSLIT:
        if " " in phrase and phrase in lower:
            hin_hits += 2

    if tel_hits > hin_hits and tel_hits >= 1:
        return "telugu"
    if hin_hits > tel_hits and hin_hits >= 1:
        return "hindi"

    return "english"


_EXPLICIT_PATTERNS = {
    "telugu": [
        r'\b(speak|reply|respond|talk|write|answer)\s+(in\s+)?telugu\b',
        r'\btelugu\s+(lo|లో|maat[ao]|talk)\b',
        r'\btelugu\s+(lo\s+)?cheppu\b',
    ],
    "hindi": [
        r'\b(speak|reply|respond|talk|write|answer)\s+(in\s+)?hindi\b',
        r'\bhindi\s+(mein|me|main)\b',
        r'\bhindi\s+(bolo|bolna|boliye)\b',
    ],
    "english": [
        r'\b(speak|reply|respond|talk|write|answer)\s+(in\s+)?english\b',
        r'\bswitch\s+to\s+english\b',
        r'\benglish\s+(mein|lo)?\b',
    ],
}


def detect_lang_change(text: str) -> str | None:
    """
    Returns 'telugu', 'hindi', 'english', or None if no explicit switch found.
    """
    lower = text.lower()
    for lang, patterns in _EXPLICIT_PATTERNS.items():
        for p in patterns:
            if re.search(p, lower):
                return lang
    return None


def get_lang_instruction(lang: str) -> str:
    """Return the system-prompt instruction for the given language."""
    if lang == "telugu":
        return (
            "CRITICAL LANGUAGE RULE: The user communicates in Telugu. "
            "You MUST reply ONLY in Telugu language using Telugu script (తెలుగు లిపి). "
            "Even if the user typed in Roman letters (transliteration), reply in Telugu script. "
            "Do NOT reply in English unless absolutely necessary for technical terms."
        )
    if lang == "hindi":
        return (
            "CRITICAL LANGUAGE RULE: The user communicates in Hindi. "
            "You MUST reply ONLY in Hindi language using Devanagari script (हिंदी). "
            "Even if the user typed in Roman letters (transliteration), reply in Devanagari. "
            "Do NOT reply in English unless absolutely necessary for technical terms."
        )
    return "Reply in clear, natural English."

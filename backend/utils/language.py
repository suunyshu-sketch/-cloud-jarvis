import re
from typing import Optional

_TELUGU_RE = re.compile(r'[\u0C00-\u0C7F]')
_HINDI_RE   = re.compile(r'[\u0900-\u097F]')

_TELUGU_TRANSLIT = {
    "nenu","meeru","mee","memu","meeru","cheppandi","cheyandi","kaadu","avunu",
    "ledu","undi","unte","okka","anni","chala","baaga","manchidi","cheddhu",
    "ela","ekkada","enduku","emiti","ikkada","akkada","vastanu","vellanu",
    "telvadu","telugu","anduke","anthe","ayindi","chesanu","chestanu","chudu",
    "pani","pandu","nanna","amma","akka","anna","bava","thammudu","cheluva"
}

_HINDI_TRANSLIT = {
    "mein","main","hai","hain","nahi","kya","kaise","kyun","kab","kahan",
    "theek","acha","bahut","bhai","yaar","dost","abhi","phir","sab","kuch",
    "iska","uska","mera","tera","humara","tumhara","aap","tum","woh","yeh",
    "karein","karo","karna","chahiye","chahta","hoga","tha","thi","the",
    "matlab","samajh","bolna","sunna","dekhna","jana","aana","khana"
}

def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 2:
        return "english"

    tel_chars = len(_TELUGU_RE.findall(text))
    hin_chars = len(_HINDI_RE.findall(text))

    if tel_chars >= 2:
        return "telugu"
    if hin_chars >= 2:
        return "hindi"

    words = set(re.findall(r'\b\w+\b', text.lower()))
    tel_hits = len(words & _TELUGU_TRANSLIT)
    hin_hits = len(words & _HINDI_TRANSLIT)

    if tel_hits >= 3:
        return "telugu"
    if hin_hits >= 3:
        return "hindi"

    return "english"

def detect_lang_change(text: str) -> Optional[str]:
    lower = text.lower()
    if any(p in lower for p in ["speak telugu","reply in telugu","telugulo","telugu lo"]):
        return "telugu"
    if any(p in lower for p in ["speak hindi","reply in hindi","hindi mein","hindi me"]):
        return "hindi"
    if any(p in lower for p in ["speak english","reply in english","english lo"]):
        return "english"
    return None

def get_lang_instruction(lang: str) -> str:
    if lang == "telugu":
        return "Respond in Telugu (use Telugu script). Mix English only for technical terms."
    if lang == "hindi":
        return "Respond in Hindi (use Hindi script). Mix English only for technical terms."
    return "Respond in English only."

import re
import html

def sanitize_input(text: str, max_length: int = 2000) -> str:
    if not text:
        return ""
    text = text[:max_length]
    text = html.escape(text)
    text = re.sub(r'[<>]', '', text)
    return text.strip()

def strip_code_for_tts(text: str) -> str:
    text = re.sub(r'```[\s\S]*?```', ' [code block] ', text)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'[*_#\[\]{}]', '', text)
    return text[:300].strip()

def truncate(text: str, limit: int = 500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."

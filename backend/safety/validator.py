import re
from typing import Tuple

_BLOCKED_PATTERNS = [
    r'DROP\s+TABLE', r'DELETE\s+FROM\s+j_users', r'DELETE\s+FROM\s+j_sessions',
    r'TRUNCATE\s+TABLE', r'ALTER\s+TABLE.*DROP',
    r'os\.system', r'subprocess', r'eval\s*\(', r'exec\s*\(',
    r'__import__', r'open\s*\(.*["\']w["\']',
    r'ignore\s+previous\s+instructions',
    r'ignore\s+all\s+instructions',
    r'you\s+are\s+now\s+.*\s+ai',
    r'jailbreak', r'DAN\s+mode',
    r'<script', r'javascript:',
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]

def validate_input(text: str) -> Tuple[bool, str]:
    if not text:
        return True, ""
    if len(text) > 2000:
        return False, "Message too long (max 2000 characters)"
    for pattern in _COMPILED:
        if pattern.search(text):
            return False, "Message contains blocked content"
    return True, ""

def validate_ai_output(text: str) -> Tuple[bool, str]:
    if not text:
        return True, ""
    sql_patterns = [r'DROP\s+TABLE', r'DELETE\s+FROM', r'TRUNCATE', r'ALTER\s+TABLE']
    for p in sql_patterns:
        if re.search(p, text, re.IGNORECASE):
            return False, "AI output contains unsafe SQL"
    return True, ""

def sanitize_for_prompt(text: str) -> str:
    text = re.sub(r'ignore\s+(all\s+)?(previous\s+)?instructions?', '[filtered]', text, flags=re.IGNORECASE)
    text = re.sub(r'you\s+are\s+now', '[filtered]', text, flags=re.IGNORECASE)
    return text

import json
import os
from typing import Optional, Tuple

_family_data = None

def _load_family():
    global _family_data
    if _family_data is None:
        path = os.path.join(os.path.dirname(__file__), "../../config/family.json")
        with open(path) as f:
            _family_data = json.load(f)
    return _family_data

def get_family_info() -> dict:
    d = _load_family()
    return {"name": d["family_name"], "religion": d["religion"], "location": d["location"]}

def get_all_members() -> list:
    return _load_family()["members"]

def resolve_person(username: str) -> Tuple[str, Optional[dict]]:
    if not username:
        return "Guest", None
    members = get_all_members()
    for m in members:
        if m["key"].lower() == username.lower():
            return m["display"], m
    return username.title(), None

def is_admin(username: str) -> bool:
    _, member = resolve_person(username)
    return member is not None and member.get("role") == "admin"

def get_tone_descriptions() -> dict:
    return {
        "best_friend":    "Talk like Lucky's closest friend — casual, direct, funny, no filter. Use bhai, yaar, dude naturally.",
        "respectful_warm":"Be warm and respectful like talking to a wise elder. Formal but caring.",
        "gentle_caring":  "Be gentle, nurturing, patient. Like a caring family assistant.",
        "sibling_playful":"Playful sibling energy — tease lightly, be fun, supportive.",
        "sibling_casual": "Casual bro energy — chill, funny, direct.",
    }

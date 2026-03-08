"""
JARVIS — Family Data Utilities
Single source of truth loaded from config/family.json.
All code that needs family info imports from here — never hardcoded elsewhere.
"""
import json
import os
from typing import Optional, Tuple
from functools import lru_cache

_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "family.json"
)


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(os.path.abspath(_CONFIG_PATH), "r", encoding="utf-8") as f:
        return json.load(f)


def get_family_info() -> dict:
    return _load()["family"]


def get_all_members() -> list:
    return _load()["members"]


def get_admin_keys() -> list:
    return [k.lower() for k in _load()["admin_keys"]]


def get_female_keys() -> list:
    return [k.lower() for k in _load()["female_keys"]]


def get_tone_descriptions() -> dict:
    return _load()["tone_descriptions"]


def is_admin(name: str) -> bool:
    if not name:
        return False
    return name.strip().lower() in get_admin_keys()


def resolve_person(raw_name: str) -> Tuple[str, Optional[dict]]:
    """
    Case-insensitive + alias resolution.
    Returns (display_name, member_dict | None).
    """
    if not raw_name:
        return raw_name, None

    key = raw_name.strip().lower()
    members = get_all_members()

    # Direct key match
    for m in members:
        if m["key"] == key:
            return m["display"], m

    # Alias match
    for m in members:
        if key in [a.lower() for a in m.get("aliases", [])]:
            return m["display"], m

    # Partial / substring match
    for m in members:
        if m["key"] in key or key in m["key"]:
            return m["display"], m
        if any(a in key or key in a for a in m.get("aliases", [])):
            return m["display"], m

    return raw_name, None


def get_member(key: str) -> Optional[dict]:
    """Return a member dict by key or alias."""
    _, member = resolve_person(key)
    return member


def build_static_facts() -> dict:
    """Build the family facts for the facts table (seeded once)."""
    info = get_family_info()
    members = get_all_members()
    females = [m["display"] for m in members if m["gender"] == "female"]
    males   = [m["display"] for m in members if m["gender"] == "male"]
    admin   = next((m for m in members if m["role"] == "admin"), None)

    facts = {
        "family_surname":  info["surname"],
        "family_religion": info["religion"],
        "family_caste":    info["caste"],
        "family_location": info["location"],
        "females_in_family": ", ".join(females),
        "males_in_family":   ", ".join(males),
    }
    if admin:
        facts["admin_name"]      = admin["display"]
        facts["admin_full_name"] = admin["full_name"]
        facts["admin_role"]      = "Admin, Owner, Developer of JARVIS"

    for m in members:
        facts[f"{m['key']}_full_name"] = m["full_name"]
        facts[f"{m['key']}_role"]      = m["role"]

    return facts

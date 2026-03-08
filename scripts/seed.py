"""
scripts/seed.py
─────────────────
One-time script to seed family users into the DB.
Run: python scripts/seed.py

IMPORTANT: Change passwords after first deployment!
Default passwords are: username + "@jarvis"  (e.g. lucky@jarvis)
"""
import asyncio
import os
import sys

# Allow importing from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from backend.db.connection import init_pool, get_pool, close_pool
from backend.services.auth_service import hash_password

FAMILY_USERS = [
    {"username": "lucky",      "password": "lucky@jarvis",     "display": "Lucky",        "role": "admin",   "family_member": "Lucky",        "approved": True},
    {"username": "krishna",    "password": "krishna@jarvis",   "display": "Krishna",      "role": "father",  "family_member": "Krishna",      "approved": True},
    {"username": "sangeetha",  "password": "sangeetha@jarvis", "display": "Sangeetha",    "role": "mother",  "family_member": "Sangeetha",    "approved": True},
    {"username": "thapaswini", "password": "thapu@jarvis",     "display": "Thapaswini",   "role": "sister",  "family_member": "Thapaswini",   "approved": True},
    {"username": "dhruva",     "password": "dhruva@jarvis",    "display": "Dhruva Kumar", "role": "brother", "family_member": "Dhruva Kumar", "approved": True},
    {"username": "prajwal",    "password": "prajwal@jarvis",   "display": "Prajwal",      "role": "brother", "family_member": "Prajwal",      "approved": True},
]

FAMILY_FACTS = {
    "family_surname": "Battini",
    "family_religion": "Hindu",
    "family_caste": "Goud",
    "family_location": "Hyderabad, Telangana, India",
    "admin_name": "Lucky (Lakshmi Narayana)",
    "father": "Krishna Battini",
    "mother": "Sangeetha Battini",
    "children": "Lucky, Thapaswini, Dhruva Kumar, Prajwal",
    "Lucky_full_name": "Battini Lakshmi Narayana Goud",
    "Lucky_role": "Admin, Owner, Developer of JARVIS",
}


async def seed():
    await init_pool()
    pool = get_pool()

    print("Seeding family users...")
    async with pool.acquire() as conn:
        for u in FAMILY_USERS:
            await conn.execute(
                """INSERT INTO users
                   (username, password_hash, display_name, role, family_member, approved, login_count)
                   VALUES ($1,$2,$3,$4,$5,$6,0)
                   ON CONFLICT (username) DO UPDATE SET
                     password_hash=$2, display_name=$3, role=$4,
                     family_member=$5, approved=$6""",
                u["username"],
                hash_password(u["password"]),
                u["display"],
                u["role"],
                u["family_member"],
                u["approved"],
            )
            print(f"  ✅ {u['username']} ({u['role']})")

    print("\nSeeding family facts...")
    async with pool.acquire() as conn:
        for k, v in FAMILY_FACTS.items():
            await conn.execute(
                """INSERT INTO facts (key, value, updated, person)
                   VALUES ($1,$2,NOW(),'family')
                   ON CONFLICT (key) DO NOTHING""",
                k, v,
            )
            print(f"  ✅ {k}")

    await close_pool()
    print("\n✅ Seeding complete!")
    print("\n⚠️  IMPORTANT: Change default passwords after first login!")
    print("   Default format: username@jarvis  (e.g. lucky@jarvis)")


if __name__ == "__main__":
    asyncio.run(seed())

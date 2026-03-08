"""
JARVIS — Database Seeder
Seeds family users, static facts, and family birthdays.
Run ONCE: python -m backend.db.seed
Safe to re-run (uses ON CONFLICT DO NOTHING / DO UPDATE).
"""
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Allow running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend import config
from backend.db.connection import init_pool, get_pool
from backend.services.auth_service import hash_password
from backend.utils.family import get_all_members, build_static_facts

# ── Family Default Passwords ──────────────────────────────
# These should be changed via /admin/change-password after first login.
# Do NOT store real passwords here — treat this as initial bootstrap only.
FAMILY_PASSWORDS = {
    "lucky":     "lucky@jarvis",
    "krishna":   "krishna@jarvis",
    "sangeetha": "sangeetha@jarvis",
    "thapaswini": "thapu@jarvis",
    "dhruva":    "dhruva@jarvis",
    "prajwal":   "prajwal@jarvis",
}


async def seed_users():
    pool = get_pool()
    members = get_all_members()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        for m in members:
            key = m["key"]
            default_pass = FAMILY_PASSWORDS.get(key, f"{key}@jarvis2025")
            await conn.execute(
                """INSERT INTO users
                   (username, password_hash, display_name, role,
                    family_member, approved, created_at, login_count)
                   VALUES ($1, $2, $3, $4, $5, TRUE, $6, 0)
                   ON CONFLICT (username) DO UPDATE
                     SET display_name=$3, role=$4, family_member=$5, approved=TRUE""",
                key,
                hash_password(default_pass),
                m["display"],
                m["role"],
                m["display"],
                now
            )
            print(f"  ✅  Seeded user: {key} ({m['display']}) role={m['role']}")

    print("✅  Family users seeded.")


async def seed_facts():
    pool = get_pool()
    facts = build_static_facts()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        for k, v in facts.items():
            await conn.execute(
                """INSERT INTO facts (key, value, updated, person)
                   VALUES ($1, $2, $3, 'family')
                   ON CONFLICT (key) DO NOTHING""",
                k, v, now
            )

    print(f"✅  {len(facts)} static facts seeded.")


async def run_migrations():
    """Run the SQL migration files in order."""
    pool = get_pool()
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))

    async with pool.acquire() as conn:
        for fname in files:
            path = os.path.join(migrations_dir, fname)
            sql = open(path, "r").read()
            try:
                await conn.execute(sql)
                print(f"  ✅  Migration applied: {fname}")
            except Exception as e:
                print(f"  ⚠️  Migration {fname}: {e}")

    print("✅  All migrations applied.")


async def main():
    config.validate()
    print("🔌  Connecting to database...")
    await init_pool()

    print("\n📋  Running migrations...")
    await run_migrations()

    print("\n👨‍👩‍👧  Seeding family users...")
    await seed_users()

    print("\n🧠  Seeding static facts...")
    await seed_facts()

    print("\n🎉  Seed complete! JARVIS database is ready.")


if __name__ == "__main__":
    asyncio.run(main())

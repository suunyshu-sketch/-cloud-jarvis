"""
JARVIS v3 — Database Seeder
Run this in Google Colab to seed the database.
"""
import asyncio
import asyncpg
import ssl
import json
import bcrypt
import os

async def seed():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise ValueError("Set DATABASE_URL environment variable first!")

    from urllib.parse import urlparse
    p = urlparse(db_url)
    host     = p.hostname
    port     = p.port or 6543
    database = p.path.lstrip("/").split("?")[0]
    user     = p.username
    password = p.password

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode    = ssl.CERT_NONE

    pool = await asyncpg.create_pool(
        host=host, port=port, database=database,
        user=user, password=password,
        ssl=ssl_ctx, statement_cache_size=0
    )

    # Load family config
    with open("config/family.json") as f:
        family = json.load(f)

    passwords = {
        "lucky":      "lucky@jarvis",
        "krishna":    "krishna@jarvis",
        "sangeetha":  "sangeetha@jarvis",
        "thapaswini": "thapu@jarvis",
        "dhruva":     "dhruva@jarvis",
        "prajwal":    "prajwal@jarvis",
    }

    async with pool.acquire() as conn:
        for m in family["members"]:
            key = m["key"]
            pw  = passwords.get(key, f"{key}@jarvis")
            hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

            await conn.execute("""
                INSERT INTO j_users (username, password_hash, display_name, role, family_member, approved)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                ON CONFLICT (username) DO UPDATE
                  SET password_hash=$2, display_name=$3, role=$4, family_member=$5, approved=TRUE
            """, key, hashed, m["display"], m["role"], m["display"])
            print(f"  ✅  {key} ({m['display']}) seeded")

    await pool.close()
    print("\n✅  Database seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed())

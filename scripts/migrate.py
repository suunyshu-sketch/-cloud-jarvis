"""
scripts/migrate.py
───────────────────
Run all SQL migrations in order.
Usage: python scripts/migrate.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from backend.db.connection import init_pool, get_pool, close_pool

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "db", "migrations")


async def run_migrations():
    await init_pool()
    pool = get_pool()

    # Create migrations tracking table
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                run_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

    migration_files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")
    )

    for filename in migration_files:
        async with pool.acquire() as conn:
            already_run = await conn.fetchval(
                "SELECT filename FROM _migrations WHERE filename=$1", filename
            )
            if already_run:
                print(f"  ⏭  {filename} (already applied)")
                continue

            print(f"  ⚡ Running {filename}...")
            sql_path = os.path.join(MIGRATIONS_DIR, filename)
            with open(sql_path, "r") as f:
                sql = f.read()

            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO _migrations (filename) VALUES ($1)", filename
            )
            print(f"  ✅ {filename} applied")

    await close_pool()
    print("\n✅ All migrations complete!")


if __name__ == "__main__":
    asyncio.run(run_migrations())

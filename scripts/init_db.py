#!/usr/bin/env python3
"""Initialize the database schema for Pi5 telemetry hub."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from asyncpg import create_pool


def load_dotenv_database_url(env_path: Path) -> str | None:
    """Load DATABASE_URL from a local .env file if present."""
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "DATABASE_URL":
            parsed = value.strip().strip('"').strip("'")
            return parsed or None
    return None


async def init_database(database_url: str, sql_file: Path) -> None:
    """Initialize the database with the schema."""
    print(f"Connecting to database...")
    pool = await create_pool(database_url, min_size=1, max_size=2)

    if not sql_file.exists():
        print(f"Error: SQL file not found: {sql_file}")
        sys.exit(1)

    sql = sql_file.read_text(encoding="utf-8")
    print(f"Executing schema from {sql_file}...")

    async with pool.acquire() as conn:
        await conn.execute(sql)

    await pool.close()
    print("Database initialized successfully!")


async def check_connection(database_url: str) -> bool:
    """Check database connection."""
    try:
        pool = await create_pool(database_url, min_size=1, max_size=1)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        await pool.close()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


def main() -> None:
    default_database_url = os.getenv("DATABASE_URL")
    if not default_database_url:
        default_database_url = load_dotenv_database_url(Path(__file__).parent.parent / ".env")
    if not default_database_url:
        default_database_url = "postgresql://postgres:postgres@localhost:5432/telemetry"

    parser = argparse.ArgumentParser(description="Initialize Pi5 telemetry hub database")
    parser.add_argument(
        "--database-url",
        default=default_database_url,
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check connection, do not initialize",
    )
    args = parser.parse_args()

    sql_file = Path(__file__).parent.parent / "sql" / "init.sql"

    if args.check_only:
        success = asyncio.run(check_connection(args.database_url))
        sys.exit(0 if success else 1)
    else:
        asyncio.run(init_database(args.database_url, sql_file))


if __name__ == "__main__":
    main()

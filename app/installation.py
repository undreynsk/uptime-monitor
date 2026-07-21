""" AM 18/Jul/26
Setup and deployment actions for the project.

Usage:
    uv run python -m app.installation           create tables (refuses if they exist)
    uv run python -m app.installation --force   drop and recreate all tables

WE DO NOT NEED ASYNCH IN THIS FILE.
Please note that we are using asyncio here, but do not need it actually. 
This is because we have the notation for asyncio in config.py "sqlite+aiosqlite:///...",
but for synchronous approach we must use the notation "sqlite:///...". We do not want to support 
two notations, so just used the asynchronous approach in this script.
"""

import argparse
import asyncio
import sys

from sqlalchemy import inspect

from app.database import engine
from app.models import Base


def _existing_tables(sync_conn) -> set[str]:
    return set(inspect(sync_conn).get_table_names())


async def init_tables(force: bool) -> int:
    async with engine.begin() as conn:
        existing = await conn.run_sync(_existing_tables)
        expected = set(Base.metadata.tables)

        print(f"Checking if the following tables exist: {', '.join(sorted(expected))}\n"
            f"Found these tables: {', '.join(sorted(existing)) or '(none)'}")

        # AM 19/Jul/26 - looking for crossing in table names. 
        # If there are other tables exist, we don't care about them
        found = sorted(existing & expected)

        if found:
            if force:
                # AM 18/Jul/26 - explicit destructive path, only reachable via --force
                await conn.run_sync(Base.metadata.drop_all)
                print("Existing tables dropped (--force), all data erased.")
            else:
                print(
                    f"Tables already exist: {', '.join(found)}. "
                    "Use --force to drop and recreate them (ALL DATA WILL BE LOST)."
                )
                return 1

        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the project database.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="drop and recreate all tables (ALL DATA WILL BE LOST)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(init_tables(force=args.force)))


if __name__ == "__main__":
    main()

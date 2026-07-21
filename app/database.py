import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(settings.database_url)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

if engine.dialect.name == "sqlite":
    # AM 18/Jul/26 - SQLite ignores foreign keys (and ON DELETE CASCADE)
    # unless explicitly enabled for every new connection
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def ensure_db_exists() -> None:
    """Fail-fast guard: the application never creates the database itself.

    A relative DATABASE_URL is resolved against the current working
    directory, so starting the server from a wrong folder must be a loud
    error instead of silently creating a new empty database.
    """
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, ":memory:"):
        return
    
    db_path = Path(url.database)
    hint = (
        "Run 'uv run python -m app.installation' to create it "
        f"(current working directory: {Path.cwd()})."
    )
    if not db_path.exists():
        raise RuntimeError(f"Database file not found: {db_path.resolve()}. {hint}")
    
    # AM 18/Jul/26 - the file may exist but be empty or foreign,
    # so also verify that our main table is present
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sites'"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError(
            f"Database {db_path.resolve()} is not initialized "
            f"(table 'sites' is missing). {hint}"
        )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session

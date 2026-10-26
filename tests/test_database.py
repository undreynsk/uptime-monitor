"""Tests for the fail-fast database guard (ensure_db_exists).

Run: uv run pytest -v
"""

import sqlite3

import pytest

from app.config import settings
from app.database import ensure_db_exists


def _use_db_url(monkeypatch, url: str) -> None:
    monkeypatch.setattr(settings, "database_url", url)


# AM 15/Sep/26 - a non-SQLite URL (Postgres) skips the file check and must not raise
def test_non_sqlite_backend_is_skipped(monkeypatch):
    _use_db_url(monkeypatch, "postgresql+asyncpg://user:secret@localhost/monitor")
    ensure_db_exists()


# AM 15/Sep/26 - an in-memory SQLite URL has no file to check, so the guard must not raise
def test_in_memory_sqlite_is_skipped(monkeypatch):
    _use_db_url(monkeypatch, "sqlite+aiosqlite:///:memory:")
    ensure_db_exists()


# AM 15/Sep/26 - a path to a non-existent database file raises "Database file not found"
def test_missing_file_raises(monkeypatch, tmp_path):
    db_file = tmp_path / "missing.db"
    _use_db_url(monkeypatch, f"sqlite+aiosqlite:///{db_file.as_posix()}")
    with pytest.raises(RuntimeError, match="Database file not found"):
        ensure_db_exists()


# AM 15/Sep/26 - an existing file without the "sites" table raises "not initialized"
def test_file_without_our_tables_raises(monkeypatch, tmp_path):
    # AM 20/Jul/26 - an existing but empty file must not pass the guard
    db_file = tmp_path / "empty.db"
    db_file.touch()
    _use_db_url(monkeypatch, f"sqlite+aiosqlite:///{db_file.as_posix()}")
    with pytest.raises(RuntimeError, match="not initialized"):
        ensure_db_exists()


# AM 15/Sep/26 - a file that has the "sites" table passes the guard without an error
def test_initialized_db_passes(monkeypatch, tmp_path):
    db_file = tmp_path / "good.db"
    connection = sqlite3.connect(db_file)
    try:
        connection.execute("CREATE TABLE sites (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()
    _use_db_url(monkeypatch, f"sqlite+aiosqlite:///{db_file.as_posix()}")
    ensure_db_exists()

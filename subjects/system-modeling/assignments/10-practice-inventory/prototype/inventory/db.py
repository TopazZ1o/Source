"""Database connection: foreign keys are switched on in every connection."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def connect(path: str | Path, busy_timeout: float = 5.0) -> sqlite3.Connection:
    """Open a connection. Transactions are controlled manually (BEGIN IMMEDIATE ... COMMIT)."""
    conn = sqlite3.connect(str(path), timeout=busy_timeout, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("foreign key enforcement could not be enabled")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

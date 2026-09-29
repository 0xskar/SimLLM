from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = 1


def open_connection(db_path: Path) -> sqlite3.Connection:
    """Open a connection with WAL mode enabled, row access by name.

    `check_same_thread=False` is required because FastAPI runs sync route
    handlers in threadpool threads while async routes (and the tick clock)
    run on the event loop thread — the same connection is legitimately used
    from more than one thread over its lifetime. Actual concurrent access is
    serialized by the application (single AppState-owned connection, one
    tick-processing path at a time), not by sqlite3 itself.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

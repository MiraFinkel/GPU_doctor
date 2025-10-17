from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List

_DB_PATH = Path(__file__).parents[1] / "gpu_logs.db"
_SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Run schema.sql the first time the DB is created."""
    with _SCHEMA_FILE.open(encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Apply schema if gpu_log table is absent."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='gpu_log';"
    ).fetchone()
    if row is None:
        _apply_schema(conn)


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _open_conn()
    try:
        _ensure_schema(conn)  # <-- new line
        yield conn
    finally:
        conn.close()


def insert_log(records: List[Dict[str, Any]]) -> None:
    """Bulk-insert GPU log rows.

    Each record is a flat dict whose keys exactly match gpu_log columns.
    """
    if not records:
        return

    cols = list(records[0].keys())
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO gpu_log ({', '.join(cols)}) VALUES ({placeholders})"

    with get_conn() as conn:
        conn.executemany(sql, [tuple(r[c] for c in cols) for r in records])
        conn.commit()

def prune_older_than(days: int = 7) -> None:
    """Delete rows older than <days> to keep the DB size bounded."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM gpu_log WHERE ts < datetime('now', ?)",
            (f"-{days} days",),
        )
        conn.commit()

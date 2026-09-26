# ai-generated: 100% - Claude Code (spec-kit implement) wrote this from research.md R7
"""SQLite storage: one row per ticket, the full ticket as JSON plus state/priority columns for filters."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def init() -> None:
    global _conn
    path = os.environ.get("SVCDESK_DB", "/data/svcdesk.db")
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    _conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    _conn.execute(
        "CREATE TABLE IF NOT EXISTS tickets ("
        " id TEXT PRIMARY KEY, state TEXT NOT NULL, priority TEXT NOT NULL,"
        " created_at TEXT NOT NULL, doc TEXT NOT NULL)"
    )
    _conn.execute(
        "CREATE TABLE IF NOT EXISTS ticket_history ("
        " seq INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, doc TEXT NOT NULL)"
    )


@contextmanager
def locked():
    """Hold the store lock for a read-modify-write sequence."""
    with _lock:
        yield


def insert(ticket: dict) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO tickets (id, state, priority, created_at, doc) VALUES (?, ?, ?, ?, ?)",
            (ticket["id"], ticket["state"], ticket["priority"], ticket["created_at"], json.dumps(ticket)),
        )


def get(ticket_id: str) -> dict | None:
    with _lock:
        row = _conn.execute("SELECT doc FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return json.loads(row[0]) if row else None


def list_tickets(state: str | None = None, priority: str | None = None) -> list[dict]:
    query, params = "SELECT doc FROM tickets WHERE 1 = 1", []
    if state is not None:
        query += " AND state = ?"
        params.append(state)
    if priority is not None:
        query += " AND priority = ?"
        params.append(priority)
    with _lock:
        rows = _conn.execute(query + " ORDER BY created_at, id", params).fetchall()
    return [json.loads(row[0]) for row in rows]


def update(ticket: dict) -> None:
    with _lock:
        _conn.execute(
            "UPDATE tickets SET state = ?, priority = ?, doc = ? WHERE id = ?",
            (ticket["state"], ticket["priority"], json.dumps(ticket), ticket["id"]),
        )


def append_history(entry: dict) -> None:
    with _lock:
        _conn.execute("INSERT INTO ticket_history (ticket_id, doc) VALUES (?, ?)", (entry["ticket_id"], json.dumps(entry)))


def history(ticket_id: str) -> list[dict]:
    with _lock:
        rows = _conn.execute("SELECT doc FROM ticket_history WHERE ticket_id = ? ORDER BY seq", (ticket_id,)).fetchall()
    return [json.loads(row[0]) for row in rows]

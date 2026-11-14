# ai-generated: 80% - Claude wrote the test cases for semgrep/rules.yml from my store.py and clock.py; I ran them with Semgrep 1.178.0 and own them
import datetime as dt
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone

from . import clock

_lock = threading.RLock()
_conn = sqlite3.connect(":memory:", check_same_thread=False)
other_conn = sqlite3.connect(":memory:")


@contextmanager
def locked():
    with _lock:
        yield


# --- svcdesk-store-conn-outside-lock -------------------------------------------------------------------------

def insert_without_lock(ticket):
    # ruleid: svcdesk-store-conn-outside-lock
    _conn.execute("INSERT INTO tickets (id) VALUES (?)", (ticket["id"],))


def read_without_lock(ticket_id):
    # ruleid: svcdesk-store-conn-outside-lock
    row = _conn.execute("SELECT doc FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return row


def insert_under_lock(ticket):
    with _lock:
        # ok: svcdesk-store-conn-outside-lock
        _conn.execute("INSERT INTO tickets (id) VALUES (?)", (ticket["id"],))


def read_under_nested_lock(ticket_id, state):
    with _lock:
        if state is not None:
            # ok: svcdesk-store-conn-outside-lock
            return _conn.execute("SELECT doc FROM tickets WHERE id = ?", (ticket_id,)).fetchall()
    return []


def update_under_locked_helper(ticket):
    with locked():
        # ok: svcdesk-store-conn-outside-lock
        _conn.execute("UPDATE tickets SET state = ? WHERE id = ?", (ticket["state"], ticket["id"]))


def other_connection_needs_no_lock(ticket_id):
    # ok: svcdesk-store-conn-outside-lock
    return other_conn.execute("SELECT 1 WHERE ? = ?", (ticket_id, ticket_id)).fetchone()


# --- svcdesk-wall-clock-read ---------------------------------------------------------------------------------

def stamp_with_datetime_now():
    # ruleid: svcdesk-wall-clock-read
    return datetime.now(timezone.utc)


def stamp_with_utcnow():
    # ruleid: svcdesk-wall-clock-read
    return datetime.utcnow()


def stamp_with_qualified_module():
    # ruleid: svcdesk-wall-clock-read
    return dt.datetime.now(dt.timezone.utc)


def stamp_with_today():
    # ruleid: svcdesk-wall-clock-read
    return date.today()


def stamp_with_epoch_seconds():
    # ruleid: svcdesk-wall-clock-read
    return time.time()


def now_from_the_request_clock(request):
    # ok: svcdesk-wall-clock-read
    return clock.now(request)


def duration_is_not_now():
    # ok: svcdesk-wall-clock-read
    started = time.perf_counter()
    # ok: svcdesk-wall-clock-read
    return time.monotonic() - started


def parsing_and_building_are_not_reading():
    # ok: svcdesk-wall-clock-read
    fixed = datetime.fromisoformat("2026-11-14T10:00:00+00:00")
    # ok: svcdesk-wall-clock-read
    return datetime(2026, 11, 14, tzinfo=timezone.utc) - fixed

# ai-generated: 100% - Claude Code (spec-kit implement) wrote this from research.md R5 and data-model.md
"""Priority and SLA rules. Pure functions: no HTTP, no storage.

Decisions: C3 = matrix (priority from impact and urgency only, the VIP flag has no effect) and
C1 = business (every target of every priority, P1 included, runs on the business-hours clock).
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .clock import from_iso

PRIORITY_MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}

# priority -> (acknowledge target, resolve target)
TARGETS = {
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}

ZONE = ZoneInfo("Europe/Warsaw")
OPENING = time(8, 0)
CLOSING = time(16, 0)


def priority(impact: int, urgency: int) -> str:
    return PRIORITY_MATRIX[(impact, urgency)]


def _is_business_day(day: date) -> bool:
    return day.weekday() < 5


def _next_opening(day: date) -> datetime:
    day += timedelta(days=1)
    while not _is_business_day(day):
        day += timedelta(days=1)
    return datetime.combine(day, OPENING, ZONE)


def is_business_time(instant: datetime) -> bool:
    """True inside the half-open window [08:00, 16:00) Europe/Warsaw, Monday to Friday."""
    local = instant.astimezone(ZONE)
    return _is_business_day(local.date()) and OPENING <= local.time() < CLOSING


def business_due(created_at: datetime, target: timedelta) -> datetime:
    """Consume `target` from consecutive business windows starting at `created_at`.

    Arithmetic is on local wall time inside one window; DST changes happen on Sunday nights, never inside a
    window. A target ending exactly at closing is due at 16:00 that day (the tie rule).
    """
    cursor = created_at.astimezone(ZONE)
    if not _is_business_day(cursor.date()) or cursor.time() >= CLOSING:
        cursor = _next_opening(cursor.date())
    elif cursor.time() < OPENING:
        cursor = datetime.combine(cursor.date(), OPENING, ZONE)
    remaining = target
    while True:
        available = datetime.combine(cursor.date(), CLOSING, ZONE) - cursor
        if remaining <= available:
            return (cursor + remaining).astimezone(timezone.utc)
        remaining -= available
        cursor = _next_opening(cursor.date())


def due_instants(created_at: datetime, prio: str) -> tuple[datetime, datetime]:
    ack_target, resolve_target = TARGETS[prio]
    return business_due(created_at, ack_target), business_due(created_at, resolve_target)


def _breached(event_at: datetime | None, due_at: datetime, now: datetime) -> bool:
    if event_at is None:
        return now > due_at
    return event_at > due_at


def sla_status(ticket: dict, now: datetime) -> dict:
    ack_due = from_iso(ticket["sla"]["ack_due_at"])
    resolve_due = from_iso(ticket["sla"]["resolve_due_at"])
    open_ticket = ticket["state"] not in ("resolved", "closed")
    return {
        "priority": ticket["priority"],
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": _breached(from_iso(ticket["acknowledged_at"]), ack_due, now),
        "resolve_breached": _breached(from_iso(ticket["resolved_at"]), resolve_due, now),
        "paused": open_ticket and not is_business_time(now),
    }

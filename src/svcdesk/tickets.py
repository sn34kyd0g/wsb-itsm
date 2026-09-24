# ai-generated: 100% - Claude Code (spec-kit implement) wrote this from data-model.md and research.md R2
"""Ticket validation, creation and the state machine. Pure functions: no HTTP, no storage.

Decision C2 = immutable: reopen is allowed from `resolved` only (within 7 days of resolved_at); a closed
ticket is final and follow-up work is a new ticket with related_to.
"""
import uuid
from datetime import datetime, timedelta

from . import sla
from .clock import from_iso, iso
from .errors import ApiError

REOPEN_WINDOW = timedelta(days=7)

# action -> (required state, new state, timestamp field set to now)
TRANSITIONS = {
    "ack": ("new", "acknowledged", "acknowledged_at"),
    "start": ("acknowledged", "in_progress", None),
    "resolve": ("in_progress", "resolved", "resolved_at"),
    "close": ("resolved", "closed", "closed_at"),
}
ACTIONS = (*TRANSITIONS, "reopen")


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation", message)


def _string(body: dict, key: str, *, required: bool, min_len: int = 0, max_len: int | None = None, default=None):
    if key not in body or body[key] is None:
        if required:
            raise _invalid(f"{key} is required")
        return default
    value = body[key]
    if not isinstance(value, str):
        raise _invalid(f"{key} must be a string")
    if len(value) < min_len or (max_len is not None and len(value) > max_len):
        raise _invalid(f"{key} must be {min_len}..{max_len} characters")
    return value


def _level(body: dict, key: str) -> int:
    value = body.get(key)
    if value is None:
        raise _invalid(f"{key} is required")
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 3:
        raise _invalid(f"{key} must be an integer 1..3")
    return value


def validate_create(body) -> dict:
    """Return the client-owned fields of a valid create request; server-owned and unknown fields are dropped."""
    if not isinstance(body, dict):
        raise _invalid("request body must be a JSON object")
    reporter = body.get("reporter")
    if reporter is None:
        raise _invalid("reporter is required")
    if not isinstance(reporter, dict):
        raise _invalid("reporter must be an object")
    vip = reporter.get("vip", False)
    if vip is None:
        vip = False
    if not isinstance(vip, bool):
        raise _invalid("reporter.vip must be a boolean")
    related_to = body.get("related_to")
    if related_to is not None and not isinstance(related_to, str):
        raise _invalid("related_to must be a string or null")
    return {
        "title": _string(body, "title", required=True, min_len=1, max_len=200),
        "description": _string(body, "description", required=False, min_len=0, max_len=4000, default=""),
        "reporter": {
            "name": _string(reporter, "name", required=True, min_len=1, max_len=100),
            "email": _string(reporter, "email", required=False),  # format not validated (data-model)
            "vip": vip,
        },
        "impact": _level(body, "impact"),
        "urgency": _level(body, "urgency"),
        "related_to": related_to,
    }


def new_ticket(data: dict, now: datetime) -> dict:
    prio = sla.priority(data["impact"], data["urgency"])  # C3 = matrix: reporter.vip is not consulted
    ack_due, resolve_due = sla.due_instants(now, prio)
    return {
        "id": str(uuid.uuid4()),
        "title": data["title"],
        "description": data["description"],
        "reporter": data["reporter"],
        "impact": data["impact"],
        "urgency": data["urgency"],
        "priority": prio,
        "state": "new",
        "created_at": iso(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "related_to": data["related_to"],
        "sla": {"ack_due_at": iso(ack_due), "resolve_due_at": iso(resolve_due)},
    }


def transition(ticket: dict, action: str, now: datetime) -> dict:
    """Apply `action` at `now` and return the updated ticket, or raise ApiError(409)."""
    state = ticket["state"]
    if action == "reopen":
        if state == "closed":
            raise ApiError(409, "ticket_closed", "a closed ticket cannot be reopened; create a new ticket with related_to")
        if state != "resolved":
            raise ApiError(409, "invalid_transition", f"cannot reopen a ticket in state {state}")
        if now > from_iso(ticket["resolved_at"]) + REOPEN_WINDOW:
            raise ApiError(409, "reopen_window_expired", "the 7-day reopen window has passed")
        return {**ticket, "state": "in_progress", "resolved_at": None, "closed_at": None}

    required, target, stamp = TRANSITIONS[action]
    if state != required:
        raise ApiError(409, "invalid_transition", f"cannot {action} a ticket in state {state}")
    updated = {**ticket, "state": target}
    if stamp:
        updated[stamp] = iso(now)
    return updated

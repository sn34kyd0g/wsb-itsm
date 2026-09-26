# ai-generated: 100% - Claude Code wrote this for the Lab 2 METR feature (PREDICTION.md)
"""The audit trail of a ticket: one entry per creation or state transition, oldest first.

Entries are recorded by main.py at the moment of each change and stored by store.py in their own table,
so the ticket document itself (the Lab 1 contract) does not change shape.
"""
from datetime import datetime

from .clock import iso


def entry(ticket_id: str, action: str, before: str | None, after: str, now: datetime) -> dict:
    return {"ticket_id": ticket_id, "at": iso(now), "action": action, "from_state": before, "to_state": after}


def created(ticket: dict) -> dict:
    return {"ticket_id": ticket["id"], "at": ticket["created_at"], "action": "create",
            "from_state": None, "to_state": ticket["state"]}

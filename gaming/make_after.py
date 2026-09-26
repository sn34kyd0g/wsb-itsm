# ai-generated: 100% - Claude Code wrote this generator for the gaming demonstration (METRIC-SPEC.md section 8)
"""Build gaming/after.jsonl from fixtures/events-practice.jsonl. Run from the repository root.

The story: management sets a target of "at least two production deployments a day". The team meets it with
an automated no-op deployment at 06:00 and 18:00 UTC every day (no commits: R-10 counts them anyway), and at
the same time a release manager starts holding every real successful deployment for a weekly release train
on Mondays at 10:00 UTC. Nothing is deleted, no commit is re-timed, no outcome is flipped (R-19): deployments
only move later, and new events are only added.
"""
import json
from datetime import datetime, timedelta, timezone

FROM = datetime(2026, 9, 1, tzinfo=timezone.utc)
TO = datetime(2026, 9, 22, tzinfo=timezone.utc)


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def z(instant: datetime) -> str:
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def next_release_train(instant: datetime) -> datetime:
    """The first Monday 10:00 UTC at or after `instant`."""
    candidate = instant.replace(hour=10, minute=0, second=0, microsecond=0)
    candidate += timedelta(days=(0 - candidate.weekday()) % 7)
    return candidate if candidate >= instant else candidate + timedelta(days=7)


events = [json.loads(line) for line in open("fixtures/events-practice.jsonl", encoding="utf-8") if line.strip()]
for event in events:
    if (event["type"] == "deployment" and event["environment"] == "production" and event["outcome"] == "success"
            and event["commits"] and FROM <= parse(event["at"]) < TO):
        event["at"] = z(next_release_train(parse(event["at"])))

day, n = FROM, 0
while day < TO:
    for hour in (6, 18):
        n += 1
        events.append({"event_id": f"d-noop-{n:03d}", "type": "deployment", "at": z(day.replace(hour=hour)),
                       "deployment_id": f"DEP-NOOP-{n:03d}", "environment": "production", "outcome": "success",
                       "commits": [], "unplanned": False, "caused_by": None})
    day += timedelta(days=1)

with open("gaming/after.jsonl", "w", encoding="utf-8", newline="\n") as out:
    for event in events:
        out.write(json.dumps(event, separators=(",", ":")) + "\n")

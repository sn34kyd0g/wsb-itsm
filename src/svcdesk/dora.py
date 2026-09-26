# ai-generated: 100% - Claude Code wrote this from METRIC-SPEC.md (rule ids cited inline)
"""DORA delivery metrics over a supplied event log (Lab 2, METRIC-SPEC.md). Pure functions: no HTTP, no storage.

`compute(body)` validates the request and returns the metric object; any problem raises ApiError(422).
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from itertools import combinations

from .clock import RFC3339, iso
from .errors import ApiError

SPEC_VERSION = "1.0.0"
TYPES = ("commit", "deployment", "incident")


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation", message)


# ---------------------------------------------------------------- parsing and well-formedness (section 1)

def _instant(value, where: str) -> datetime:
    if not isinstance(value, str) or not RFC3339.fullmatch(value.strip()):
        raise _invalid(f"{where} is not an RFC 3339 instant with an offset")
    try:
        parsed = datetime.fromisoformat(value.strip().upper().replace(" ", "T"))
    except ValueError:
        raise _invalid(f"{where} is not an RFC 3339 instant with an offset")
    return parsed.astimezone(timezone.utc)


def _str(event: dict, key: str, where: str, nullable: bool = False):
    value = event.get(key)
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise _invalid(f"{where}.{key} must be a non-empty string{' or null' if nullable else ''}")
    return value


def _str_list(event: dict, key: str, where: str) -> list[str]:
    value = event.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise _invalid(f"{where}.{key} must be an array of strings")
    return value


def _bool(event: dict, key: str, where: str) -> bool:
    value = event.get(key)
    if not isinstance(value, bool):
        raise _invalid(f"{where}.{key} must be a boolean")
    return value


def _parse_event(raw, index: int) -> dict:
    where = f"events[{index}]"
    if not isinstance(raw, dict):
        raise _invalid(f"{where} must be an object")
    event_id = raw.get("event_id")
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
        raise _invalid(f"{where}.event_id must be a string of 1..64 characters")
    kind = raw.get("type")
    if kind not in TYPES:
        raise _invalid(f"{where}.type must be one of {', '.join(TYPES)}")
    event = {"event_id": event_id, "type": kind, "at": _instant(raw.get("at"), f"{where}.at")}
    if kind == "commit":
        event["sha"] = _str(raw, "sha", where)
        event["branch"] = _str(raw, "branch", where)
        event["change_id"] = _str(raw, "change_id", where, nullable=True)
        event["reverts"] = _str(raw, "reverts", where, nullable=True)
        if (event["change_id"] is None) == (event["reverts"] is None):
            raise _invalid(f"{where}: a commit carries a change_id exactly when reverts is null")
    elif kind == "deployment":
        event["deployment_id"] = _str(raw, "deployment_id", where)
        event["environment"] = _str(raw, "environment", where)
        event["outcome"] = raw.get("outcome")
        if event["outcome"] not in ("success", "failure"):
            raise _invalid(f"{where}.outcome must be success or failure")
        event["commits"] = _str_list(raw, "commits", where)
        event["unplanned"] = _bool(raw, "unplanned", where)
        event["caused_by"] = _str(raw, "caused_by", where, nullable=True)
    else:
        event["incident_id"] = _str(raw, "incident_id", where)
        event["phase"] = raw.get("phase")
        if event["phase"] not in ("opened", "resolved"):
            raise _invalid(f"{where}.phase must be opened or resolved")
        event["deployments"] = _str_list(raw, "deployments", where)
    return event


def _parse_log(raw_events: list) -> tuple[dict, list, dict]:
    """Return (commits by sha, deployments, incidents by id) of a well-formed log, or raise."""
    seen: set[str] = set()
    commits: dict[str, dict] = {}
    deployments: dict[str, dict] = {}
    incidents: dict[str, dict] = {}
    for index, raw in enumerate(raw_events):
        event = _parse_event(raw, index)
        if event["event_id"] in seen:  # R-05: the first occurrence wins, later ones are ignored
            continue
        seen.add(event["event_id"])
        if event["type"] == "commit":
            if event["sha"] in commits:
                raise _invalid(f"sha {event['sha']} is not unique")
            commits[event["sha"]] = event
        elif event["type"] == "deployment":
            if event["deployment_id"] in deployments:
                raise _invalid(f"deployment_id {event['deployment_id']} is not unique")
            deployments[event["deployment_id"]] = event
        else:
            incident = incidents.setdefault(event["incident_id"], {
                "incident_id": event["incident_id"], "opened": None, "resolved": None, "deployments": set()})
            if incident[event["phase"]] is not None:
                raise _invalid(f"incident {event['incident_id']} has more than one {event['phase']} event")
            incident[event["phase"]] = event["at"]
            incident["deployments"].update(event["deployments"])

    for commit in commits.values():
        if commit["reverts"] is not None and commit["reverts"] not in commits:
            raise _invalid(f"commit {commit['sha']} reverts {commit['reverts']}, which is not in the log")
    for deployment in deployments.values():
        for sha in deployment["commits"]:
            if sha not in commits:
                raise _invalid(f"deployment {deployment['deployment_id']} carries {sha}, which is not in the log")
        if deployment["caused_by"] is not None and deployment["caused_by"] not in incidents:
            raise _invalid(f"deployment {deployment['deployment_id']} is caused_by an unknown incident")
    for incident in incidents.values():
        if incident["opened"] is None:
            raise _invalid(f"incident {incident['incident_id']} resolved but was never opened")
        for deployment_id in incident["deployments"]:
            if deployment_id not in deployments:
                raise _invalid(f"incident {incident['incident_id']} names unknown deployment {deployment_id}")
    return commits, list(deployments.values()), incidents


def _resolve_changes(commits: dict) -> dict[str, str]:
    """R-06: sha -> change_id, a revert inheriting transitively from the commit it reverts."""
    resolved: dict[str, str] = {}
    for sha in commits:
        chain, current = [], sha
        while current not in resolved and commits[current]["change_id"] is None:
            if current in chain:
                raise _invalid(f"commit {sha} is part of a revert cycle")
            chain.append(current)
            current = commits[current]["reverts"]
        change = resolved.get(current) or commits[current]["change_id"]
        for link in chain + [current]:
            resolved[link] = change
    return resolved


# ---------------------------------------------------------------- arithmetic (R-03, R-04)

def _seconds(delta) -> Decimal:
    """An exact duration in seconds, clamped to zero (R-03)."""
    value = Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / Decimal(1_000_000)
    return max(value, Decimal(0))


def _whole(value: Decimal | None) -> int | None:
    return None if value is None else int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _round6(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return float(_round6(Decimal(numerator) / Decimal(denominator)))


def _median(values: list[Decimal]) -> int | None:
    if not values:
        return None
    ordered, middle = sorted(values), len(values) // 2
    if len(ordered) % 2:
        return _whole(ordered[middle])
    return _whole((ordered[middle - 1] + ordered[middle]) / 2)


# ---------------------------------------------------------------- the endpoint body

def _window(body: dict) -> tuple[datetime, datetime]:
    window = body.get("window")
    if not isinstance(window, dict):
        raise _invalid("window is required and must be an object")
    start = _instant(window.get("from"), "window.from")
    end = _instant(window.get("to"), "window.to")
    if end <= start:
        raise _invalid("window.to must be after window.from")
    return start, end


def compute(body) -> dict:
    if not isinstance(body, dict):
        raise _invalid("request body must be a JSON object")
    start, end = _window(body)
    raw_events = body.get("events")
    if not isinstance(raw_events, list):
        raise _invalid("events is required and must be an array")
    commits, deployments, incidents = _parse_log(raw_events)
    change_of = _resolve_changes(commits)

    # R-01, R-02: production deployments in [from, to), in time order (ties by id, for order independence)
    in_window = sorted(
        (d for d in deployments if d["environment"] == "production" and start <= d["at"] < end),
        key=lambda d: (d["at"], d["deployment_id"]))
    successful = [d for d in in_window if d["outcome"] == "success"]
    failed = [d for d in in_window if d["outcome"] == "failure"]

    # R-08, R-09, R-10: one pair per sha at its first successful deployment; clamp and count negatives (E1)
    lead_times, negative_pairs, first_deploy_of_sha = [], 0, {}
    for deployment in successful:
        for sha in deployment["commits"]:
            if sha in first_deploy_of_sha:
                continue
            first_deploy_of_sha[sha] = deployment
            delta = deployment["at"] - commits[sha]["at"]
            if delta.total_seconds() < 0:
                negative_pairs += 1
            lead_times.append(_seconds(delta))
    off_main = {sha for d in in_window for sha in d["commits"] if commits[sha]["branch"] != "main"}
    without_commits = sum(1 for d in in_window if not d["commits"])

    # R-12, R-13: recovery per failed deployment via its covering incident (E5 open failures, E6 no merging)
    recovery_times, open_failures = [], 0
    for deployment in failed:
        covering = min(
            (i for i in incidents.values() if deployment["deployment_id"] in i["deployments"]),
            key=lambda i: (i["opened"], i["incident_id"].encode()), default=None)
        if covering is None or covering["resolved"] is None:
            open_failures += 1
        else:
            recovery_times.append(_seconds(covering["resolved"] - deployment["at"]))
    intervals = [(i["opened"], i["resolved"] if i["resolved"] is not None else end) for i in incidents.values()]
    overlapping = sum(1 for a, b in combinations(intervals, 2) if a[0] < b[1] and b[0] < a[1])

    rework = sum(1 for d in in_window if d["unplanned"] and d["caused_by"] is not None)  # R-15

    # R-07, R-16, R-17: ground truth per change, from the change's earliest commit anywhere in the log
    first_commit_of_change: dict[str, datetime] = {}
    for sha, commit in commits.items():
        change = change_of[sha]
        if change not in first_commit_of_change or commit["at"] < first_commit_of_change[change]:
            first_commit_of_change[change] = commit["at"]
    first_delivery_of_change: dict[str, datetime] = {}
    for deployment in successful:
        for sha in deployment["commits"]:
            first_delivery_of_change.setdefault(change_of[sha], deployment["at"])
    true_lead_times = [_seconds(at - first_commit_of_change[change])
                       for change, at in first_delivery_of_change.items()]

    days = _seconds(end - start) / Decimal(86400)
    return {
        "spec_version": SPEC_VERSION,
        "window": {"from": iso(start), "to": iso(end)},
        "deployment_frequency_per_day": float(_round6(Decimal(len(in_window)) / days)),
        "change_lead_time_seconds_p50": _median(lead_times),
        "failed_deployment_recovery_time_seconds_p50": _median(recovery_times),
        "change_fail_rate": _ratio(len(failed), len(in_window)),
        "deployment_rework_rate": _ratio(rework, len(in_window)),
        "counts": {
            "deployments": len(in_window),
            "successful_deployments": len(successful),
            "failed_deployments": len(failed),
            "recovered_failures": len(recovery_times),
            "open_failures": open_failures,
            "rework_deployments": rework,
            "lead_time_pairs": len(lead_times),
            "changes": len(set(change_of.values())),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,
            "deployments_without_commits": without_commits,
            "commits_never_on_main": len(off_main),
            "revert_chains_collapsed": sum(1 for c in commits.values() if c["reverts"] is not None),
            "overlapping_incident_pairs": overlapping,
        },
        "ground_truth": {
            "changes_delivered": len(first_delivery_of_change),
            "true_change_lead_time_seconds_p50": _median(true_lead_times),
        },
    }


def ticket_events(tickets: list[dict]) -> list[dict]:
    """Section 7: one event per lifecycle instant a ticket actually holds, ordered by (at, ticket_id)."""
    phases = (("created", "created_at", "new"), ("acknowledged", "acknowledged_at", "acknowledged"),
              ("resolved", "resolved_at", "resolved"), ("closed", "closed_at", "closed"))
    events = []
    for ticket in tickets:
        for phase, field, state in phases:
            if ticket.get(field):
                at = datetime.fromisoformat(ticket[field]).astimezone(timezone.utc)
                events.append((at, ticket["id"], {"ticket_id": ticket["id"], "at": iso(at), "phase": phase,
                                                  "priority": ticket["priority"], "state": state}))
    events.sort(key=lambda item: (item[0], item[1]))
    return [event for _, _, event in events]

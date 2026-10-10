# ai-generated: 100% - Claude Code (spec-kit implement) wrote this suite from spec.md acceptance scenarios and Lab 3 M-02 to M-07
"""Own HTTP test suite (Stretch S3). Stdlib only; talks to SVCDESK_URL.

Run: python -m tests.run (from src/). The last stdout line is ITSMLAB-TESTS: passed=<n> failed=<m>.
Decisions under test: C1 = business, C2 = immutable, C3 = matrix.
"""
import asyncio
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("SVCDESK_URL", "http://localhost:8080").rstrip("/")
TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def req(method, path, body=None, clock=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Content-Type": "application/json"}
    if clock:
        headers["X-Test-Clock"] = clock
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        text = err.read()
        try:
            return err.code, json.loads(text)
        except ValueError:
            return err.code, text


def at(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def z(instant):
    return instant.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body(impact=1, urgency=1, vip=False, **extra):
    return {"title": "Test ticket", "reporter": {"name": "Test", "email": "test@example.com", "vip": vip},
            "impact": impact, "urgency": urgency, **extra}


T1 = "2026-10-14T10:00:00Z"


def create(clock=T1, **kw):
    status, ticket = req("POST", "/tickets", body(**kw), clock=clock)
    assert status == 201, (status, ticket)
    return ticket


def act(ticket_id, action, clock):
    return req("POST", f"/tickets/{ticket_id}/{action}", clock=clock)


def drive(ticket_id, actions, start=T1, step=timedelta(minutes=5)):
    clock = at(start)
    for action in actions:
        clock += step
        status, data = act(ticket_id, action, z(clock))
        assert status == 200, (action, status, data)
    return data


def expect_error(status, data, allowed):
    assert status in allowed, (status, data)
    assert isinstance(data, dict) and isinstance(data.get("error"), dict), data


# ---- US5: operations -------------------------------------------------------------------------------

@test
def health():
    status, data = req("GET", "/health")
    assert status == 200 and data["status"] == "ok" and data["service"] == "svcdesk", (status, data)


@test
def unknown_path_404_json():
    status, data = req("GET", "/this-route-does-not-exist-9f3c")
    assert status == 404 and isinstance(data, dict), (status, data)


# ---- US1: create, read, list, priority ---------------------------------------------------------------

@test
def priority_matrix():
    expected = {(1, 1): "P1", (1, 2): "P2", (1, 3): "P3", (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
                (3, 1): "P3", (3, 2): "P4", (3, 3): "P4"}
    for (i, u), prio in expected.items():
        ticket = create(impact=i, urgency=u)
        assert ticket["priority"] == prio, ((i, u), ticket["priority"])


@test
def vip_does_not_raise_priority_c3_matrix():
    ticket = create(impact=3, urgency=3, vip=True)
    assert ticket["priority"] == "P4" and ticket["reporter"]["vip"] is True, ticket


@test
def vip_p1_stays_p1():
    assert create(impact=1, urgency=1, vip=True)["priority"] == "P1"


@test
def priority_in_body_ignored():
    assert create(impact=3, urgency=3, vip=True, priority="P1", state="closed", id="x")["priority"] == "P4"


@test
def created_ticket_shape():
    ticket = create()
    assert ticket["state"] == "new" and ticket["id"], ticket
    assert ticket["acknowledged_at"] is None and ticket["resolved_at"] is None and ticket["closed_at"] is None
    assert ticket["description"] == "" or "description" in ticket
    assert ticket["created_at"].endswith("Z"), ticket["created_at"]


@test
def validation_errors():
    no_title = body()
    del no_title["title"]
    cases = [no_title, body(title="x" * 201), body(impact=5), body(urgency="high"), body(impact=True),
             body(urgency=1.0), body(description="x" * 4001), {"title": "t", "impact": 1, "urgency": 1},
             body(reporter={"name": ""}), body(title="")]
    for case in cases:
        status, data = req("POST", "/tickets", case, clock=T1)
        expect_error(status, data, (400, 422))
    status, data = req("POST", "/tickets", raw=b"{not json", clock=T1)
    expect_error(status, data, (400, 422))


@test
def distinct_ids_and_get_by_id():
    a, b = create(), create()
    assert a["id"] != b["id"]
    status, data = req("GET", f"/tickets/{a['id']}")
    assert status == 200 and data["id"] == a["id"] and data["title"] == a["title"], (status, data)


@test
def unknown_ticket_404():
    status, data = req("GET", "/tickets/does-not-exist-9f3c")
    expect_error(status, data, (404,))


@test
def list_filters():
    p1, p4 = create(impact=1, urgency=1), create(impact=3, urgency=3)
    status, data = req("GET", "/tickets?priority=P1")
    ids = {t["id"] for t in data}
    assert status == 200 and p1["id"] in ids and p4["id"] not in ids
    status, data = req("GET", "/tickets?state=new")
    assert status == 200 and p1["id"] in {t["id"] for t in data}
    status, data = req("GET", "/tickets?priority=P9")
    assert status == 200 and data == []


# ---- US2: lifecycle, C2 = immutable -------------------------------------------------------------------

@test
def full_lifecycle_records_instants():
    ticket = create()
    tid = ticket["id"]
    status, data = act(tid, "ack", "2026-10-14T10:05:00Z")
    assert status == 200 and data["state"] == "acknowledged" and at(data["acknowledged_at"]) == at("2026-10-14T10:05:00Z")
    status, data = act(tid, "start", "2026-10-14T10:10:00Z")
    assert status == 200 and data["state"] == "in_progress"
    status, data = act(tid, "resolve", "2026-10-14T11:00:00Z")
    assert status == 200 and data["state"] == "resolved" and at(data["resolved_at"]) == at("2026-10-14T11:00:00Z")
    status, data = act(tid, "close", "2026-10-14T12:00:00Z")
    assert status == 200 and data["state"] == "closed" and at(data["closed_at"]) == at("2026-10-14T12:00:00Z")


@test
def illegal_transitions_409():
    new = create()["id"]
    for action in ("start", "resolve", "close", "reopen"):
        status, data = act(new, action, T1)
        expect_error(status, data, (409,))
    acked = create()["id"]
    drive(acked, ["ack"])
    for action in ("ack", "resolve", "close"):
        status, data = act(acked, action, T1)
        expect_error(status, data, (409,))
    status, data = req("GET", f"/tickets/{acked}")
    assert data["state"] == "acknowledged"


@test
def reopen_resolved_window():
    resolved_at = at(T1) + timedelta(minutes=15)
    for offset, expected in ((timedelta(days=6), 200), (timedelta(days=7), 200),
                             (timedelta(days=7, seconds=1), 409)):
        tid = create()["id"]
        drive(tid, ["ack", "start", "resolve"])
        status, data = act(tid, "reopen", z(resolved_at + offset))
        assert status == expected, (offset, status, data)
        if status == 200:
            assert data["state"] == "in_progress" and data["resolved_at"] is None and data["closed_at"] is None


@test
def reopen_closed_refused_c2_immutable():
    tid = create()["id"]
    data = drive(tid, ["ack", "start", "resolve", "close"])
    status, data = act(tid, "reopen", z(at(data["closed_at"]) + timedelta(days=1)))
    expect_error(status, data, (409,))
    status, data = act(tid, "reopen", z(at(T1) + timedelta(minutes=21)))
    expect_error(status, data, (409,))
    follow_up = create(related_to=tid)
    assert follow_up["related_to"] == tid


@test
def action_on_unknown_ticket_404():
    status, data = act("does-not-exist-9f3c", "ack", T1)
    expect_error(status, data, (404,))


# ---- US3: SLA, C1 = business --------------------------------------------------------------------------

VECTORS = [
    ("T1", 1, 1, "2026-10-14T10:00:00Z", "2026-10-14T10:15:00Z", "2026-10-14T14:00:00Z"),
    ("T2", 1, 3, "2026-10-16T13:30:00Z", "2026-10-19T09:30:00Z", "2026-10-21T13:30:00Z"),
    ("T3", 1, 1, "2026-10-16T15:00:00Z", "2026-10-19T06:15:00Z", "2026-10-19T10:00:00Z"),
    ("T4", 1, 2, "2026-10-17T10:00:00Z", "2026-10-19T07:00:00Z", "2026-10-19T14:00:00Z"),
    ("T5", 3, 3, "2027-01-14T14:30:00Z", "2027-01-15T14:30:00Z", "2027-01-27T14:30:00Z"),
    ("T6", 1, 1, "2027-01-15T15:50:00Z", "2027-01-18T07:15:00Z", "2027-01-18T11:00:00Z"),
    ("T7", 2, 1, "2026-10-14T10:00:00Z", "2026-10-14T11:00:00Z", "2026-10-15T10:00:00Z"),
    ("T8", 1, 3, "2026-10-23T13:00:00Z", "2026-10-26T10:00:00Z", "2026-10-28T14:00:00Z"),
]


def make_vector_test(name, impact, urgency, created, ack_due, resolve_due):
    def vector():
        ticket = create(clock=created, impact=impact, urgency=urgency)
        assert at(ticket["sla"]["ack_due_at"]) == at(ack_due), (name, ticket["sla"])
        assert at(ticket["sla"]["resolve_due_at"]) == at(resolve_due), (name, ticket["sla"])
    vector.__name__ = f"sla_vector_{name}"
    return vector


for _vector in VECTORS:
    test(make_vector_test(*_vector))


def sla(tid, clock):
    status, data = req("GET", f"/tickets/{tid}/sla", clock=clock)
    assert status == 200, (status, data)
    return data


@test
def breach_and_pause_t2():
    tid = create(clock="2026-10-16T13:30:00Z", impact=1, urgency=3)["id"]
    late = sla(tid, "2026-10-19T09:31:00Z")
    assert late["ack_breached"] is True and late["resolve_breached"] is False, late
    assert sla(tid, "2026-10-19T09:30:00Z")["ack_breached"] is False  # equality is not a breach
    assert sla(tid, "2026-10-19T09:00:00Z")["ack_breached"] is False
    assert sla(tid, "2026-10-17T10:00:00Z")["paused"] is True
    assert sla(tid, "2026-10-19T09:00:00Z")["paused"] is False


@test
def ack_in_time_not_breached_later():
    tid = create(clock="2026-10-16T13:30:00Z", impact=1, urgency=3)["id"]
    assert act(tid, "ack", "2026-10-16T13:45:00Z")[0] == 200
    assert sla(tid, "2026-10-19T12:00:00Z")["ack_breached"] is False


@test
def p1_friday_evening_paused_on_saturday():
    tid = create(clock="2026-10-16T15:00:00Z", impact=1, urgency=1)["id"]
    data = sla(tid, "2026-10-17T10:00:00Z")
    assert data["paused"] is True and not data["ack_breached"] and not data["resolve_breached"], data
    assert data["priority"] == "P1"


@test
def resolved_ticket_not_paused():
    tid = create()["id"]
    drive(tid, ["ack", "start", "resolve"])
    assert sla(tid, "2026-10-17T10:00:00Z")["paused"] is False


# ---- US4: test clock ---------------------------------------------------------------------------------

@test
def test_clock_sets_created_at():
    assert at(create(clock=T1)["created_at"]) == at(T1)


@test
def malformed_clock_rejected():
    for bad in ("yesterday", "2026-10-14T10:00:00", "20261014T100000Z", "2026-W42-3T10:00:00Z",
                "2026-10-14T10:00Z"):
        status, data = req("POST", "/tickets", body(), clock=bad)
        expect_error(status, data, (400, 422))
    assert at(create(clock="2026-10-14T12:00:00+02:00")["created_at"]) == at(T1)


@test
def malformed_clock_rejected_on_reads():
    tid = create()["id"]
    for path in ("/tickets", f"/tickets/{tid}", f"/tickets/{tid}/sla"):
        status, data = req("GET", path, clock="yesterday")
        expect_error(status, data, (400, 422))


@test
def long_email_accepted():
    status, data = req("POST", "/tickets", {**body(), "reporter": {"name": "Test", "email": "a" * 400}}, clock=T1)
    assert status == 201 and len(data["reporter"]["email"]) == 400, (status, data)


@test
def earlier_clock_is_accepted():
    tid = create(clock="2026-10-20T10:00:00Z")["id"]
    status, data = act(tid, "ack", "2026-10-01T10:00:00Z")
    assert status == 200 and at(data["acknowledged_at"]) == at("2026-10-01T10:00:00Z"), (status, data)


# ---- Lab 2: DORA metrics (METRIC-SPEC.md) ------------------------------------------------------------

WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}


def commit(sha, when, change="CHG-1", reverts=None, branch="main"):
    return {"event_id": f"c-{sha}", "type": "commit", "at": when, "sha": sha, "branch": branch,
            "change_id": None if reverts else change, "reverts": reverts}


def deploy(dep, when, commits, outcome="success", env="production", unplanned=False, caused_by=None):
    return {"event_id": f"d-{dep}", "type": "deployment", "at": when, "deployment_id": dep, "environment": env,
            "outcome": outcome, "commits": commits, "unplanned": unplanned, "caused_by": caused_by}


def incident(inc, phase, when, deployments):
    return {"event_id": f"i-{inc}-{phase}", "type": "incident", "at": when, "incident_id": inc, "phase": phase,
            "deployments": deployments}


def metrics(events, window=WINDOW):
    status, data = req("POST", "/dora/metrics", {"window": window, "events": events})
    assert status == 200, (status, data)
    return data


@test
def dora_empty_log():
    data = metrics([])
    assert data["deployment_frequency_per_day"] == 0.0 and data["change_lead_time_seconds_p50"] is None, data
    assert data["change_fail_rate"] is None and data["counts"]["deployments"] == 0, data


@test
def dora_negative_lead_time_clamped_and_counted():
    data = metrics([commit("a", "2026-09-02T10:05:00Z"), deploy("D1", "2026-09-02T10:00:00Z", ["a"])])
    assert data["change_lead_time_seconds_p50"] == 0 and data["anomalies"]["negative_lead_time_pairs"] == 1, data


@test
def dora_revert_of_revert_is_one_change():
    data = metrics([commit("a", "2026-09-02T08:00:00Z"), commit("b", "2026-09-02T09:00:00Z", reverts="a"),
                    commit("c", "2026-09-02T09:30:00Z", reverts="b"), deploy("D1", "2026-09-02T10:00:00Z", ["a", "b", "c"])])
    assert data["counts"]["changes"] == 1 and data["anomalies"]["revert_chains_collapsed"] == 2, data
    assert data["ground_truth"]["true_change_lead_time_seconds_p50"] == 7200, data


@test
def dora_branch_is_ignored_and_empty_deployments_count():
    data = metrics([commit("h", "2026-09-02T09:00:00Z", branch="hotfix/1"), deploy("D1", "2026-09-02T10:00:00Z", ["h"]),
                    deploy("D2", "2026-09-03T10:00:00Z", [], outcome="failure")])
    assert data["counts"]["lead_time_pairs"] == 1 and data["anomalies"]["commits_never_on_main"] == 1, data
    assert data["anomalies"]["deployments_without_commits"] == 1 and data["change_fail_rate"] == 0.5, data


@test
def dora_open_failure_and_overlapping_incidents():
    data = metrics([deploy("D1", "2026-09-02T10:00:00Z", [], outcome="failure"),
                    deploy("D2", "2026-09-02T11:00:00Z", [], outcome="failure"),
                    incident("I1", "opened", "2026-09-02T10:10:00Z", ["D1"]),
                    incident("I2", "opened", "2026-09-02T11:10:00Z", ["D2"]),
                    incident("I2", "resolved", "2026-09-02T12:00:00Z", ["D2"])])
    assert data["counts"]["open_failures"] == 1 and data["counts"]["recovered_failures"] == 1, data
    assert data["failed_deployment_recovery_time_seconds_p50"] == 3600, data
    assert data["anomalies"]["overlapping_incident_pairs"] == 1, data


@test
def dora_window_and_environment_filter():
    data = metrics([deploy("D1", "2026-09-22T00:00:00Z", []), deploy("D2", "2026-09-01T00:00:00Z", []),
                    deploy("D3", "2026-09-05T00:00:00Z", [], env="staging")])
    assert data["counts"]["deployments"] == 1, data


@test
def dora_rejects_bad_requests():
    expect_error(*req("POST", "/dora/metrics", {"events": []}), (400, 422))
    expect_error(*req("POST", "/dora/metrics", {"window": {"from": WINDOW["to"], "to": WINDOW["from"]}, "events": []}), (400, 422))
    expect_error(*req("POST", "/dora/metrics", {"window": WINDOW, "events": {}}), (400, 422))
    expect_error(*req("POST", "/dora/metrics", {"window": WINDOW, "events": [commit("b", "2026-09-02T09:00:00Z", reverts="zz")]}), (400, 422))


@test
def dora_ticket_events_stream():
    tid = create(clock="2026-10-14T10:00:00Z")["id"]
    drive(tid, ["ack", "start", "resolve"], start="2026-10-14T10:00:00Z")
    status, data = req("GET", "/dora/ticket-events")
    assert status == 200 and isinstance(data, list), (status, data)
    mine = [e for e in data if e["ticket_id"] == tid]
    assert [e["phase"] for e in mine] == ["created", "acknowledged", "resolved"], mine
    assert [e["state"] for e in mine] == ["new", "acknowledged", "resolved"], mine
    keys = [(at(e["at"]), e["ticket_id"]) for e in data]
    assert keys == sorted(keys), "stream not ordered by (at, ticket_id)"


# ---- Lab 2 METR feature: GET /tickets/{id}/history ----------------------------------------------------

@test
def history_records_every_transition():
    tid = create(clock="2026-10-14T10:00:00Z")["id"]
    drive(tid, ["ack", "start", "resolve", "reopen"], start="2026-10-14T10:00:00Z")
    status, data = req("GET", f"/tickets/{tid}/history")
    assert status == 200, (status, data)
    assert [e["action"] for e in data] == ["create", "ack", "start", "resolve", "reopen"], data
    assert [(e["from_state"], e["to_state"]) for e in data] == [
        (None, "new"), ("new", "acknowledged"), ("acknowledged", "in_progress"),
        ("in_progress", "resolved"), ("resolved", "in_progress")], data
    assert [at(e["at"]) for e in data] == [at("2026-10-14T10:00:00Z") + timedelta(minutes=5 * i) for i in range(5)], data


@test
def history_skips_rejected_transitions():
    tid = create()["id"]
    status, _ = act(tid, "close", T1)
    assert status == 409
    status, data = req("GET", f"/tickets/{tid}/history")
    assert status == 200 and [e["action"] for e in data] == ["create"], (status, data)


@test
def history_of_unknown_ticket_is_404():
    expect_error(*req("GET", "/tickets/does-not-exist-7a1/history"), (404,))


# ---- Lab 3: /kb/search and /metrics against the running stack (kb-index is the real course image) -----

def get_text(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode()


@test
def kb_search_refuses_bad_q():
    for path in ("/kb/search", "/kb/search?q=", "/kb/search?q=" + "x" * 201):
        expect_error(*req("GET", path), (400,))


@test
def kb_search_upstream_failure_is_502():
    status, data = req("GET", "/kb/search?q=force-error-own-suite")
    expect_error(status, data, (502,))
    assert data["error"]["code"] == "upstream_unavailable", data


@test
def kb_search_passes_hits_through():
    for _ in range(3):  # kb-index fails a small share of ordinary searches on purpose
        status, data = req("GET", "/kb/search?q=vpn%20drops")
        if status != 502:
            break
    assert status == 200, (status, data)
    assert data["query"] == "vpn drops" and isinstance(data["hits"], list) and data["hits"], data


@test
def metrics_exposes_histogram_with_route_templates():
    req("GET", "/tickets/own-suite-raw-id-9f3")
    req("GET", "/kb/search")
    status, ctype, text = get_text("/metrics")
    assert status == 200 and ctype.startswith("text/plain") and "version=0.0.4" in ctype, (status, ctype)
    assert "# TYPE http_server_request_duration_seconds histogram" in text
    assert 'http_route="/tickets/{ticket_id}"' in text and "own-suite-raw-id-9f3" not in text
    line = re.search(r'^http_server_request_duration_seconds_count\{(.*)\} ', text, re.M)
    assert line and sorted(re.findall(r'(\w+)="', line.group(1))) == [
        "http_request_method", "http_response_status_code", "http_route"], line
    assert any(l.startswith("http_server_request_duration_seconds_count{") and 'http_route="/kb/search"' in l
               and 'http_response_status_code="400"' in l for l in text.splitlines()), "no /kb/search 400 counted"


# ---- Lab 3: /kb/search in-process, against a fake upstream (needs the service's own dependencies) -----

def in_process(handler, path):
    """Runs one request through the app with kb-index replaced by handler; returns status, body, upstream calls."""
    import httpx
    from svcdesk import kb
    from svcdesk.main import app

    calls = []

    def recording(request):
        calls.append(request)
        return handler(request)

    async def run():
        kb.client = httpx.AsyncClient(transport=httpx.MockTransport(recording))
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://svcdesk") as c:
                resp = await c.get(path)
                return resp.status_code, resp.json()
        finally:
            await kb.close_client()

    status, data = asyncio.run(run())
    return status, data, calls


def fake_hits(request):
    import httpx
    return httpx.Response(200, json={"query": "x", "hits": [{"id": "KE-1", "title": "t", "score": 0.5}]})


def raising(exc_name):
    def handler(request):
        import httpx
        raise getattr(httpx, exc_name)("fake", request=request)
    return handler


try:
    import httpx  # noqa: F401
    import svcdesk.main  # noqa: F401
    HAVE_APP = True
except ImportError:
    HAVE_APP = False

if HAVE_APP:
    @test
    def fake_upstream_one_call_encoded_hits_unchanged():
        status, data, calls = in_process(fake_hits, "/kb/search?q=vpn%20drops%2Fx")
        assert status == 200, (status, data)
        assert data == {"query": "vpn drops/x", "hits": [{"id": "KE-1", "title": "t", "score": 0.5}]}, data
        assert len(calls) == 1, calls
        assert calls[0].method == "GET" and calls[0].url.raw_path == b"/search?q=vpn%20drops%2Fx", calls[0].url

    @test
    def fake_upstream_non_200_timeout_and_connect_error_are_502():
        import httpx
        handlers = [lambda r: httpx.Response(503, json={"error": {"code": "index_unavailable"}}),
                    raising("ReadTimeout"), raising("ConnectError")]
        for handler in handlers:
            status, data, calls = in_process(handler, "/kb/search?q=itsmlab")
            assert status == 502 and data["error"]["code"] == "upstream_unavailable", (status, data)
            assert len(calls) == 1, calls

    @test
    def fake_upstream_not_called_for_bad_q():
        status, data, calls = in_process(fake_hits, "/kb/search?q=" + "y" * 201)
        assert status == 400 and isinstance(data.get("error"), dict) and calls == [], (status, data, calls)


# ---- runner ------------------------------------------------------------------------------------------

def wait_for_health(seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if req("GET", "/health")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(1)
    raise SystemExit(f"svcdesk at {BASE} did not become healthy within {seconds} s")


def main():
    wait_for_health()
    passed = failed = 0
    for fn in TESTS:
        try:
            fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc(file=sys.stdout)
    print(f"ITSMLAB-TESTS: passed={passed} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

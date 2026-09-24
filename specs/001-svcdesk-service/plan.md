<!-- ai-generated: 90% - Claude Code (spec-kit /speckit-plan) drafted; decisions C1/C2/C3 and stack confirmed by me -->
# Implementation Plan: svcdesk - service desk ticketing service (Lab 1)

**Branch**: `001-svcdesk-service` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-svcdesk-service/spec.md`

## Summary

Build `svcdesk`, a JSON-over-HTTP ticketing service on port 8080 that validates and stores tickets, computes
priority from the impact/urgency matrix only (C3 = matrix), enforces the ticket lifecycle with reopen allowed
from `resolved` only (C2 = immutable), and computes every SLA target of every priority on the business-hours
clock (C1 = business), with a per-request test clock. It is a single Python/FastAPI service with SQLite in a
named volume, shipped as a compose project, plus a stdlib-only own-test suite in the compose `tests` profile.

## Technical Context

**Language/Version**: Python 3.13 (`python:3.13-slim` image)

**Primary Dependencies**: FastAPI 0.141.1, uvicorn 0.52.4, tzdata 2026.4 (all pinned, installed at build
time)

**Storage**: SQLite (stdlib `sqlite3`) at `SVCDESK_DB` = `/data/svcdesk.db` on the named volume
`svcdesk-data`

**Testing**: stdlib HTTP test runner `src/tests/run.py` run through `docker compose --profile tests`
(Stretch S3); the course checker `.\itsmlab.ps1 verify 1` as the acceptance gate

**Target Platform**: Linux container (Docker Compose); developer host Windows 11

**Project Type**: web service (single HTTP API, no UI)

**Performance Goals**: every request answered well within the checker's 10 s limit; `/health` within 120 s
of `docker compose up`

**Constraints**: no network at run time; no host-path bind mounts; one uvicorn worker (SQLite + a process
lock); peak RAM about 0.4 GB for the whole lab

**Scale/Scope**: about 400 users; at most 100 tickets per checker run; 10 endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.1.

| principle | gate | pre-design | post-design |
|---|---|---|---|
| I. Spec-first, receipt before code | spec committed (`376b49a`); `specs` receipt obtained before any `src/` commit | PASS (receipt is the user's next step; this plan writes only under `specs/`) | PASS |
| II. Checker contract is done | compose contract (service `svcdesk`, 8080, `SVCDESK_TEST_CLOCK`, named volume, deps at build time); `verify 1` exit 0 | PASS | PASS: research R10, quickstart §7 |
| III. Decisions match behaviour | `DECISIONS.md` front matter = business / immutable / matrix, and the design implements exactly these | PASS | PASS: data-model priority (no VIP rule), state machine (no reopen from closed), SLA (business clock only) |
| IV. Deterministic time, durable state | single clock abstraction honouring `X-Test-Clock`; data under `/data` | PASS | PASS: `svcdesk/clock.py` (R4), SQLite on the volume (R7) |
| V. AI disclosure, no personal data | `ai-generated` header on every `.md` in `specs/` and every `.py` in `src/` incl. `__init__.py`; synthetic test data only | PASS | PASS: every generated artifact has the header; tests use `Test`/`example.com` names |
| Tech constraints | pinned deps, healthcheck, LF endings, YAGNI | PASS | PASS: 3 dependencies, no ORM, no validation library beyond the framework |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-svcdesk-service/
├── spec.md              # feature specification (/speckit-specify)
├── plan.md              # this file
├── research.md          # Phase 0: decisions R1-R10
├── data-model.md        # Phase 1: ticket, reporter, state machine, SLA status
├── quickstart.md        # Phase 1: validation guide
├── contracts/
│   └── openapi.yaml     # Phase 1: HTTP contract (restates docs/API.md with C1/C2/C3)
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
Dockerfile                 # from Dockerfile.example (python:3.13-slim, uvicorn svcdesk.main:app on 8080)
requirements.txt           # fastapi==0.141.1, uvicorn==0.52.4, tzdata==2026.4
docker-compose.yml         # healthcheck enabled; tests profile enabled (S3)
src/
├── svcdesk/
│   ├── __init__.py
│   ├── main.py            # FastAPI app, routes, error handlers (ApiError, 404/405, bad JSON)
│   ├── errors.py          # ApiError(status, code, message)
│   ├── clock.py           # now(request): X-Test-Clock or UTC now (the only clock)
│   ├── sla.py             # priority matrix, targets, business_due(), is_business_time(), sla_status()
│   ├── tickets.py         # validate_create(), new_ticket(), transition() state machine + reopen window
│   └── store.py           # SQLite: init, insert, get, list(state, priority), update (under a lock)
└── tests/
    ├── __init__.py
    └── run.py             # stdlib HTTP suite against SVCDESK_URL; last line ITSMLAB-TESTS: ...
```

**Structure Decision**: a single-project web service under `src/svcdesk/` as `Dockerfile.example` expects
(`svcdesk.main:app` with `--app-dir /app/src`). Domain rules (`sla.py`, `tickets.py`) are pure functions with
no HTTP or storage imports, so they can be checked directly; `main.py` only wires HTTP to them and to
`store.py`. Own tests live in `src/tests/` so the same image runs them (`python -m tests.run`).

## Complexity Tracking

No constitution violations to justify.

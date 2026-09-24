---

description: "Task list for svcdesk Lab 1 implementation"
---
<!-- ai-generated: 90% - Claude Code (spec-kit /speckit-tasks) generated from plan.md, spec.md, data-model.md, research.md -->

# Tasks: svcdesk - service desk ticketing service (Lab 1)

**Input**: Design documents from `specs/001-svcdesk-service/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: Included. The plan (research R9) commits to an own HTTP test suite for Stretch S3 in
`src/tests/run.py`; each story adds its cases there. The acceptance gate is `.\itsmlab.ps1 verify 1`.

**Decisions in force**: C1 = business, C2 = immutable, C3 = matrix (source of truth: `DECISIONS.md`).

**Disclosure rule (constitution V)**: every new `.py` file, including empty `__init__.py`, starts with
`# ai-generated: <n>% - <how>` in its first ten lines.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1..US5 from spec.md)

## Phase 0: Gate (constitution I)

- [X] T001 Confirm the `specs` receipt exists for the commit containing `specs/001-svcdesk-service/spec.md` (`.\itsmlab.ps1 submit 1 --kind specs`, issue form, bot comment); do not create any file under `src/` other than `src/README.md` before it

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T002 Create `requirements.txt` in the repository root with exactly `fastapi==0.141.1`, `uvicorn==0.52.4`, `tzdata==2026.4`
- [X] T003 [P] Copy `Dockerfile.example` to `Dockerfile` (python:3.13-slim, `COPY requirements.txt`, `pip install --no-cache-dir`, `COPY src/ /app/src/`, `ENV SVCDESK_DB=/data/svcdesk.db`, `CMD uvicorn svcdesk.main:app --app-dir /app/src --host 0.0.0.0 --port 8080`, one worker)
- [X] T004 [P] Create packages with disclosure headers: `src/svcdesk/__init__.py` and `src/tests/__init__.py` (one comment line each)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain core, storage, errors and app skeleton used by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Implement `ApiError(Exception)` with `status: int`, `code: str`, `message: str` in `src/svcdesk/errors.py`
- [X] T006 [P] Implement the clock in `src/svcdesk/clock.py`: `utc_now() -> datetime` (aware UTC), `now(request) -> datetime` (for now returns `utc_now()`; US4 adds the header), and `iso(dt) -> str` returning UTC RFC 3339 with `Z` suffix (e.g. `2026-10-14T10:00:00Z`), `iso(None) -> None`; no other module may call `datetime.now`
- [X] T007 [P] Implement SLA domain in `src/svcdesk/sla.py`: `PRIORITY_MATRIX` = {(1,1):P1,(1,2):P2,(1,3):P3,(2,1):P2,(2,2):P3,(2,3):P4,(3,1):P3,(3,2):P4,(3,3):P4}; `priority(impact, urgency)` using the matrix only (no VIP rule, C3 = matrix); `TARGETS` = P1 15 min / 4 h, P2 1 h / 8 h, P3 4 h / 24 h, P4 8 h / 72 h; `ZONE = ZoneInfo("Europe/Warsaw")`
- [X] T008 Implement `is_business_time(instant)` and `business_due(created_at, target)` in `src/svcdesk/sla.py` per research R5: window Mon-Fri "[08:00:00, 16:00:00) Europe/Warsaw"; start at `created_at` or the next opening; consume `remaining` from consecutive windows; if `remaining <= available` return `cursor + remaining` (tie rule: ending exactly at 16:00:00 is due 16:00:00 that day); return UTC; add `due_instants(created_at, priority) -> (ack_due, resolve_due)` using `business_due` for every priority incl. P1 (C1 = business) (depends on T007)
- [X] T009 [P] Implement SQLite storage in `src/svcdesk/store.py` per data-model "Storage mapping": path from env `SVCDESK_DB` (default `/data/svcdesk.db`, create parent dir), table `tickets(id TEXT PRIMARY KEY, state TEXT, priority TEXT, created_at TEXT, doc TEXT)`, one connection `check_same_thread=False` guarded by `threading.Lock`; functions `init()`, `insert(ticket)`, `get(id) -> dict | None`, `list(state=None, priority=None) -> list[dict]`, `update(ticket)` (writes `doc`, `state`, `priority` in one statement), and `locked()` context manager for read-modify-write
- [X] T010 Create the app skeleton in `src/svcdesk/main.py`: FastAPI app, `store.init()` on startup, exception handlers returning `{"error": {"code", "message"}}` for `ApiError`, Starlette `HTTPException` (404 -> `not_found`, 405 -> `method_not_allowed`) and malformed JSON bodies (422 `validation`); `GET /health` -> 200 `{"status": "ok", "service": "svcdesk"}` (depends on T005, T006, T009)

**Checkpoint**: `docker compose up --build --wait svcdesk` starts and `/health` answers; `business_due` reproduces T1-T8

---

## Phase 3: User Story 1 - Register a ticket with a computed priority (Priority: P1) 🎯 MVP

**Goal**: create, read and list tickets with validated input and matrix priority

**Independent Test**: create all nine impact/urgency combinations and invalid requests; read back by id; list with `state` and `priority` filters

### Implementation for User Story 1

- [X] T011 [US1] Implement `validate_create(body) -> dict` in `src/svcdesk/tickets.py` raising `ApiError(422, "validation", msg)`: body must be a JSON object; `title` "required, 1..200 characters" (string); `description` "optional, 0..4000 characters, default `""`"; `reporter` "required object" with `name` "required, 1..100 characters", `email` "optional, default null" (string or null), `vip` "optional, default false" (bool only); `impact`/`urgency` "required, 1..3; not bool, not string, not float" (`isinstance(x, int) and not isinstance(x, bool)`); `related_to` "optional, default null, not validated" (string or null); read only these keys so server-owned and unknown fields are ignored
- [X] T012 [US1] Implement `new_ticket(data, now) -> dict` in `src/svcdesk/tickets.py`: `id = str(uuid4())`, `priority = sla.priority(impact, urgency)` (vip stored, no effect), `state = "new"`, `created_at = iso(now)`, `acknowledged_at`/`resolved_at`/`closed_at` = null, `sla = {"ack_due_at", "resolve_due_at"}` from `sla.due_instants` (depends on T011, T008)
- [X] T013 [US1] Add endpoints in `src/svcdesk/main.py`: `POST /tickets` (parse JSON, validate, `new_ticket(..., clock.now(request))`, `store.insert`, 201), `GET /tickets/{id}` (200 or 404 `not_found`), `GET /tickets?state=&priority=` (exact match, all results, 200 array; unknown values give `[]`) (depends on T012)
- [X] T014 [US1] Create the runner in `src/tests/run.py`: stdlib `urllib` + `json`; base URL from env `SVCDESK_URL` (default `http://localhost:8080`); wait up to 60 s for `/health`; `req(method, path, body=None, clock=None)` helper sending `X-Test-Clock`; a `@test` registry; print each result; last line `ITSMLAB-TESTS: passed=<n> failed=<m>`; exit 1 if any failure; synthetic data only (`Test`, `test@example.com`)
- [X] T015 [US1] Add US1 cases to `src/tests/run.py`: nine matrix cells; VIP (3,3) -> `P4`; VIP (1,1) -> `P1`; body `priority: "P1"` ignored; missing title, 201-char title, `impact: 5`, `urgency: "high"`, `impact: true` -> 400/422 with `error`; distinct ids; get by id; unknown id 404 with `error`; list filters `state=new` and `priority=P1` (depends on T013, T014)

**Checkpoint**: US1 works alone; CHECKS 2.05-2.23 and 2.46-2.48 pass

---

## Phase 4: User Story 2 - Drive a ticket through its lifecycle (Priority: P1)

**Goal**: ack/start/resolve/close/reopen with 409 on any other transition; reopen from `resolved` only within 7 days (C2 = immutable)

**Independent Test**: fresh tickets through every legal transition and representative illegal ones

### Implementation for User Story 2

- [X] T016 [US2] Implement `transition(ticket, action, now) -> dict` in `src/svcdesk/tickets.py` per data-model state machine: ack new->acknowledged (`acknowledged_at = now`), start acknowledged->in_progress, resolve in_progress->resolved (`resolved_at = now`), close resolved->closed (`closed_at = now`), reopen resolved->in_progress only if `now <= resolved_at + 7 days` (clears `resolved_at` and `closed_at`; `sla` unchanged); refusals `ApiError(409, ...)`: closed + reopen -> `ticket_closed` (regardless of age), resolved too late -> `reopen_window_expired`, anything else -> `invalid_transition`; never compare `now` with stored instants except for the reopen window
- [X] T017 [US2] Add `POST /tickets/{id}/{action}` for `ack`, `start`, `resolve`, `close`, `reopen` in `src/svcdesk/main.py`: inside `store.locked()` get (404 `not_found`), `transition`, `store.update`, 200 full ticket (depends on T016)
- [X] T018 [US2] Add US2 cases to `src/tests/run.py`: full path ack/start/resolve/close with timestamps equal to the clocks; ack twice 409; start on new 409; resolve on new and on acknowledged 409; close on new 409; reopen new 409; reopen resolved after 6 days 200 `in_progress` with `resolved_at` null; reopen resolved after 7 days + 1 s 409; reopen exactly at 7 days 200; reopen closed after 1 day 409 (C2); new ticket with `related_to` = closed id created; action on unknown id 404 (depends on T017)

**Checkpoint**: CHECKS 2.24-2.35 and 2.49 pass; 2.35 observes C2 = immutable

---

## Phase 5: User Story 3 - Know which tickets are late (Priority: P1)

**Goal**: SLA view with due instants, breach and pause, all on the business clock (C1 = business)

**Independent Test**: create tickets at T1-T8 and query `/sla` at chosen instants

### Implementation for User Story 3

- [X] T019 [US3] Implement `sla_status(ticket, now) -> dict` in `src/svcdesk/sla.py` per data-model "SLA status": `ack_breached` = (`acknowledged_at` null and `now > ack_due_at`) or `acknowledged_at > ack_due_at`; `resolve_breached` likewise with `resolved_at`; equality is not a breach; `paused` = state not in {resolved, closed} and not `is_business_time(now)`; compare parsed instants, never strings
- [X] T020 [US3] Add `GET /tickets/{id}/sla` in `src/svcdesk/main.py` returning `{priority, ack_due_at, resolve_due_at, ack_breached, resolve_breached, paused}` (404 if unknown) (depends on T019)
- [X] T021 [US3] Add US3 cases to `src/tests/run.py`: the eight vectors T1-T8 (business column from spec.md User Story 3) on the ticket's `sla` block; T2 unacknowledged at 2026-10-19T09:31:00Z -> `ack_breached` true, `resolve_breached` false; at 2026-10-19T09:00:00Z -> false; T2 acknowledged 2026-10-16T13:45:00Z read at 2026-10-19T12:00:00Z -> false; T2 `paused` true at 2026-10-17T10:00:00Z, false at 2026-10-19T09:00:00Z; resolved ticket never paused; equality at due instant not breached (depends on T020)

**Checkpoint**: CHECKS 2.36-2.45 pass; 2.41 observes C1 = business

---

## Phase 6: User Story 4 - Reproducible time for testing (Priority: P2)

**Goal**: per-request `X-Test-Clock` when `SVCDESK_TEST_CLOCK` is `1`/`true`

**Independent Test**: create with a clock and check `created_at`; malformed clock refused

### Implementation for User Story 4

- [X] T022 [US4] Extend `now(request)` in `src/svcdesk/clock.py`: read `SVCDESK_TEST_CLOCK` once at import (`"1"`/`"true"`, case-insensitive); if enabled and header `X-Test-Clock` present, parse with `datetime.fromisoformat`; parse error or naive value -> `ApiError(422, "invalid_clock", ...)`; convert to UTC; if disabled, ignore the header; ensure `POST /tickets` resolves the clock before or independently of body validation so `X-Test-Clock: yesterday` with a valid body answers 422
- [X] T023 [US4] Add US4 cases to `src/tests/run.py`: `created_at` equals the T1 clock as an instant; `X-Test-Clock: yesterday` on a valid create -> 400/422; naive `2026-10-14T10:00:00` -> 400/422; action with a clock earlier than stored timestamps succeeds and records it (depends on T022)

**Checkpoint**: CHECKS 2.03-2.04 pass

---

## Phase 7: User Story 5 - Operate the service (Priority: P2)

**Goal**: one-command start, health within 120 s, tickets survive restart, JSON 404

**Independent Test**: start, create, restart, read back

### Implementation for User Story 5

- [X] T024 [US5] In `docker-compose.yml` uncomment the Python healthcheck for `svcdesk` (interval 5s, timeout 3s, retries 20, start_period 5s); keep `SVCDESK_TEST_CLOCK: "1"`, port `8080:8080`, named volume `svcdesk-data:/data`, no bind mounts
- [X] T025 [US5] In `docker-compose.yml` uncomment and adapt the `tests` service: `build: .`, `profiles: ["tests"]`, `working_dir: /app/src`, `depends_on: svcdesk: condition: service_healthy`, `SVCDESK_URL: http://svcdesk:8080`, `command: ["python", "-m", "tests.run"]` (depends on T024, T014)
- [X] T026 [US5] Add US5 cases to `src/tests/run.py`: `/health` body `status == "ok"` and `service == "svcdesk"`; unknown path 404 with JSON body; list returns an array (depends on T014)
- [X] T027 [US5] Verify persistence manually per quickstart §5 (create, `docker compose restart svcdesk`, `GET /tickets` still lists it) and record the result in `specs/001-svcdesk-service/quickstart.md` if anything differs

**Checkpoint**: `docker compose --profile tests run --rm --build tests` exits 0 with `ITSMLAB-TESTS: passed=<n> failed=0`, n >= 10

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T028 [P] Fill `DECISIONS.md`: replace `??` in the `ai-generated` line with a number and a how; write all five labels (Decision, Rejected alternative, Reason, Service owner as a role, Customer outcome; >= 20 characters each) for C1 = business, C2 = immutable, C3 = matrix, consistent with spec.md "Resolved requirement conflicts"
- [X] T029 [P] Remove the Sync Impact Report comment from `.specify/memory/constitution.md` (keep the `ai-generated` line)
- [X] T030 Check every `.py` under `src/` and every `.md` under `specs/` has the `ai-generated:` header in its first ten lines (`src/svcdesk/*.py`, `src/tests/*.py`)
- [X] T031 Run `.\itsmlab.ps1 verify 1` until exit 0 with observations `C1=business C2=immutable C3=matrix`; fix failures in the owning module (`src/svcdesk/*.py`)
- [X] T032 Run `/speckit-converge`, then save its comparison (>= 400 characters, at least three ids within R-01..R-25) to `specs/001-svcdesk-service/converge.md` with an `ai-generated` header (Stretch S1)
- [ ] T033 Commit, push, re-run `.\itsmlab.ps1 verify 1` on the clean tree (no `(dirty)`), tag `lab1/v1`, push the tag, and file the submission receipt (`.\itsmlab.ps1 submit 1 --kind submission --tag lab1/v1`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Gate (Phase 0)**: blocks every task that creates a file under `src/` (T004 onward)
- **Setup (Phase 1)**: T002-T003 may run before the gate (root files); T004 after it
- **Foundational (Phase 2)**: depends on Setup; blocks all user stories
- **US1 (Phase 3)**: after Foundational; T014 (runner) is shared by later test tasks
- **US2, US3, US4**: after Foundational; each needs T013 only for its tests (tickets must be creatable) and edits `main.py`/`tickets.py`/`sla.py`, so run them sequentially in the order listed
- **US5 (Phase 7)**: T024 anytime after T010; T025-T026 after T014
- **Polish**: T028-T029 anytime; T031-T033 after all stories

### Within Each User Story

- Domain function (`tickets.py`/`sla.py`/`clock.py`) -> endpoint (`main.py`) -> test cases (`run.py`)

### Parallel Opportunities

- T003 and T004 in parallel after T002
- T005, T006, T007, T009 in parallel (different files); then T008, then T010
- T024 (compose) in parallel with any US1-US4 task
- T028 and T029 in parallel with any implementation task

---

## Parallel Example: Foundational

```text
Task: "Implement ApiError in src/svcdesk/errors.py"            (T005)
Task: "Implement the clock in src/svcdesk/clock.py"             (T006)
Task: "Implement priority matrix and targets in src/svcdesk/sla.py" (T007)
Task: "Implement SQLite storage in src/svcdesk/store.py"        (T009)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Gate T001, then Setup and Foundational
2. Phase 3 (US1): create/get/list with priority and SLA due instants
3. **STOP and VALIDATE**: run `src/tests/run.py` and `.\itsmlab.ps1 verify 1` (US1 checks green)

### Incremental Delivery

1. US1 -> US2 (lifecycle, C2) -> US3 (SLA view, C1) -> US4 (test clock) -> US5 (operations)
2. After each story: own tests plus `verify 1`; commit after each story
3. Polish: DECISIONS.md, converge report, clean-tree verify, tag and submit

---

## Notes

- Stretch: S3 (own tests, T014/T025) and S1 (converge report, T032) give the required two of three; S2
  (agent config) is not planned
- Commit after each phase; never move a pushed tag - a new attempt gets a new tag (`lab1/v2`)

## Phase 9: Convergence

- [X] T034 Resolve the clock with `clock.now(request)` in `GET /tickets` and `GET /tickets/{id}` in `src/svcdesk/main.py` so a malformed `X-Test-Clock` answers 422 on every `/tickets` endpoint, and add a case to `src/tests/run.py` per FR-023 / plan: research R4 (partial)
- [X] T035 Restrict `parse_instant` in `src/svcdesk/clock.py` to RFC 3339 date-time (`YYYY-MM-DD[T ]HH:MM:SS[.frac](Z|±HH:MM)`, e.g. a regex check before `fromisoformat`) so ISO basic/week forms such as `20261014T100000Z` are refused, and add a case to `src/tests/run.py` per FR-023 (partial)
- [X] T036 Remove the unspecified 320-character limit on `reporter.email` in `src/svcdesk/tickets.py` (data-model: "optional, default null; format not validated") per FR-004 (unrequested)

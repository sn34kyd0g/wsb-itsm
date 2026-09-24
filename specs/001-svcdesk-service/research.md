<!-- ai-generated: 90% - Claude Code (spec-kit /speckit-plan) drafted; stack follows Dockerfile.example and the constitution -->
# Research: svcdesk (Lab 1)

All Technical Context items were resolvable from the constitution, `Dockerfile.example`, `docs/API.md` and
`docs/CHECKS.md`; no NEEDS CLARIFICATION remained. Each decision below records what was chosen and why.

## R1. Language and web framework

- **Decision**: Python 3.13 on `python:3.13-slim`, FastAPI 0.141.1 served by uvicorn 0.52.4 (single worker),
  versions pinned in `requirements.txt` together with `tzdata==2026.4` (R6).
- **Rationale**: the constitution's default stack; `Dockerfile.example` already targets it and names these
  versions as current in September 2026; FastAPI gives routing, JSON responses and exception handlers with
  little code.
- **Alternatives considered**: Flask (no async, similar effort, no advantage); stdlib `http.server` (fewer
  dependencies but manual routing, error handling and threading - more code for the same contract); Go
  (single static binary, but no reuse of the course skeleton).

## R2. Request validation

- **Decision**: validate the raw JSON body with a small hand-written function (`svcdesk/tickets.py`), not
  Pydantic models. It checks types strictly (`isinstance(x, int) and not isinstance(x, bool)` for impact and
  urgency), lengths, and reads only known fields, so server-owned and unknown fields are ignored for free.
  Failures raise one `ApiError(422, "validation", message)`.
- **Rationale**: the contract needs a specific error body (`{"error": {"code", "message"}}`), must reject
  `"1"`, `true` and `1.0` for impact/urgency, and must ignore rather than reject extra fields. A dozen lines
  of explicit checks are easier to audit against FR-004..FR-006 than Pydantic strict-mode configuration plus
  a custom `RequestValidationError` handler.
- **Alternatives considered**: Pydantic `StrictInt` models with `extra="ignore"` and a handler that rewrites
  422 bodies - works, but hides the rules in type annotations and needs care around nested `reporter`
  defaults.

## R3. Error responses and unknown paths

- **Decision**: one `ApiError(status, code, message)` exception and handler returning
  `{"error": {"code", "message"}}`; a handler for Starlette's `HTTPException` maps framework 404/405 to the
  same shape (`not_found`, `method_not_allowed`); a handler for malformed JSON bodies returns 422
  `validation`.
- **Rationale**: FR-003, FR-005, FR-013 all require a top-level `error` object; one shape everywhere keeps
  clients simple. Codes follow API.md §6 recommendations.

## R4. Clock abstraction and test clock

- **Decision**: `svcdesk/clock.py` exposes `now(request) -> datetime` (aware, UTC). If test-clock mode is on
  (`SVCDESK_TEST_CLOCK` in `{"1", "true"}`, read once at start-up) and `X-Test-Clock` is present, it parses
  the header with `datetime.fromisoformat`; a parse error or a naive result raises `ApiError(422,
  "invalid_clock")`. Otherwise it returns `datetime.now(timezone.utc)`. It is used as a FastAPI dependency on
  every `/tickets...` endpoint; no other module calls the system clock.
- **Rationale**: constitution Principle IV (single injectable clock); FR-023/FR-024. `fromisoformat` in
  Python 3.11+ accepts `Z` and RFC 3339 offsets; requiring an offset rejects `yesterday` and naive values.
- **Alternatives considered**: a middleware setting a context variable - more indirection for no gain.

## R5. Business-hours SLA calculation (C1 = business)

- **Decision**: pure functions in `svcdesk/sla.py` using `zoneinfo.ZoneInfo("Europe/Warsaw")`:
  1. convert `created_at` to local time;
  2. if outside [08:00, 16:00) Mon-Fri, move to the next opening (08:00 today if before opening, else 08:00
     of the next weekday);
  3. loop: `available = 16:00 today - cursor`; if `remaining <= available` the due instant is
     `cursor + remaining` (so a target ending exactly at closing is due 16:00 that day - the tie rule);
     otherwise subtract `available` and jump to 08:00 of the next weekday;
  4. convert to UTC.
  Every priority, P1 included, uses this function; there is no wall-clock branch.
- **Rationale**: FR-017/FR-018. Arithmetic is done on local wall time within one business window; DST
  transitions happen on Sundays at night, never inside a window, so attaching the zone to each local instant
  gives the correct UTC offset (T8 checks this). Hand-verified against all eight vectors T1-T8 (business
  column).
- **Alternatives considered**: minute-by-minute stepping (simple but slow for 72 h targets); a
  business-calendar library (a runtime dependency for ~30 lines of logic, and none handles the tie rule
  explicitly).

## R6. Time zone data

- **Decision**: pin the PyPI `tzdata==2026.4` package in `requirements.txt`, in addition to the system tz
  database of `python:3.13-slim`.
- **Rationale**: `zoneinfo` falls back to the `tzdata` package when no system database exists. On the
  developer's Windows machine `ZoneInfo("Europe/Warsaw")` failed without it (verified while planning), so
  pinning it makes local runs and unit checks behave like the container. It is installed at build time, so
  no network is needed at run time.
- **Alternatives considered**: system tz database only - works in the image but breaks local runs on
  Windows.
- **Verification**: a scratch implementation of R5 reproduced all eight vectors T1-T8 (business column)
  exactly.

## R7. Storage and persistence

- **Decision**: SQLite via the stdlib `sqlite3`, file at `SVCDESK_DB` (default `/data/svcdesk.db`, a named
  volume). One table `tickets(id TEXT PRIMARY KEY, state TEXT, priority TEXT, created_at TEXT, doc TEXT)`
  where `doc` is the ticket JSON; `state` and `priority` are duplicated as columns for list filters. One
  connection with `check_same_thread=False` guarded by a `threading.Lock`; each action is read-modify-write
  inside the lock.
- **Rationale**: FR-027 (survives restart) with zero extra dependencies; volumes are tiny (≤ 100 tickets per
  checker run); a JSON document column avoids schema migrations while the model is still evolving in later
  labs.
- **Alternatives considered**: in-memory dict (fails FR-027); SQLAlchemy/ORM (YAGNI); one column per field
  (more code, no benefit at this scale).

## R8. Identifiers and timestamps

- **Decision**: `uuid.uuid4()` strings for ids; instants serialised as UTC ISO 8601 with a `Z` suffix,
  keeping sub-second precision only if the source clock had it (the checker sends whole seconds).
- **Rationale**: FR-007, FR-008; UUID is API.md's recommendation.

## R9. Own tests (Stretch S3)

- **Decision**: a stdlib-only runner `src/tests/run.py` (urllib + json), run by the compose `tests` profile
  against `SVCDESK_URL`. It waits for `/health`, runs at least 25 HTTP tests (matrix, validation, lifecycle,
  reopen window incl. C2, the eight SLA vectors, breach/pause, test clock) and prints
  `ITSMLAB-TESTS: passed=<n> failed=<m>` as its last line, exiting non-zero on any failure.
- **Rationale**: no test framework dependency, runs in the same image, satisfies S3 and doubles as a local
  regression suite; constitution section "Development Workflow".
- **Alternatives considered**: pytest + httpx (two more pinned dependencies and output parsing for the
  summary line).

## R10. Compose and image

- **Decision**: copy `Dockerfile.example` to `Dockerfile` unchanged except the module path it already uses
  (`svcdesk.main:app`); enable the Python healthcheck in `docker-compose.yml`; add the `tests` service under
  `profiles: ["tests"]` with `depends_on: condition: service_healthy`.
- **Rationale**: FR-025/FR-026; `up --wait` then waits on real readiness.

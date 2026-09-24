<!-- ai-generated: 90% - Claude Code (spec-kit /speckit-specify) drafted from docs/REQUIREMENTS.md and docs/API.md; decisions C1/C2/C3 chosen by me -->
# Feature Specification: svcdesk - service desk ticketing service (Lab 1)

**Feature Branch**: `001-svcdesk-service`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Przeczytaj @docs/REQUIREMENTS.md oraz @docs/API.md. Zbuduj specyfikację
serwisu svcdesk, w której trzy sprzeczne pary wymagań są rozwiązane tak: C1=business, C2=immutable,
C3=matrix."

## Context

The internal IT service desk (about 400 people, three offices) replaces a spreadsheet and inboxes with a
small ticketing service that desk agents, monitoring and future integrations call over HTTP. The service
computes priority, keeps the SLA clocks and refuses operations that would make reports wrong.

Sources: `docs/REQUIREMENTS.md` (R-01..R-25, what the desk wants) and `docs/API.md` (the enforced interface
contract: exact paths, field names, status codes, test clock). Where the two differ in precision, API.md
governs. This specification references requirement ids throughout.

### Resolved requirement conflicts

REQUIREMENTS.md contains three pairs of requirements that cannot both hold. Each is resolved by rejecting
the minimal conflicting part of one requirement and keeping everything else.

| id | conflicting pair | resolution | kept | rejected (minimal part) |
|---|---|---|---|---|
| C1 | R-13 (SLA clocks pause outside business hours) vs R-14 (P1 counted around the clock) | `business` | R-13 for every priority; the P1 target lengths of R-12/R-14 (15 min, 4 h) | the "around the clock" part of R-14: P1 targets are counted in business time, like every other priority |
| C2 | R-09 (a closed ticket is immutable) vs R-10 (reopen a resolved **or closed** ticket within 7 days) | `immutable` | R-09 in full; R-10 and R-11 for resolved tickets | "or closed" in R-10: a closed ticket can never be reopened; follow-up work is a new ticket with `related_to` |
| C3 | R-05 (priority from the matrix and nothing else) vs R-06 (VIP tickets never below P2) | `matrix` | R-04 and R-05 in full; the VIP flag is still recorded (R-03) | R-06: the VIP flag does not change priority |

These three values MUST match the front matter of `DECISIONS.md` and what the running service exhibits
(constitution Principle III).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register a ticket with a computed priority (Priority: P1)

A desk agent, a monitoring system or an integration reports an incident: a title, an optional description, a
reporter (name, optional e-mail, optional VIP flag), an impact and an urgency. The service validates the
report, assigns an identifier, computes the priority from the impact/urgency matrix, sets the state to `new`,
records the creation instant and returns the full ticket including its two SLA due instants. Tickets can be
read back one by one and listed with filters.

**Why this priority**: without registering and reading tickets nothing else in the desk works; this alone
replaces the spreadsheet.

**Independent Test**: create tickets for all nine impact/urgency combinations and a few invalid requests;
read each ticket back and list them by state and priority.

**Acceptance Scenarios**:

1. **Given** the service is running, **When** a client sends a valid ticket with impact 2 and urgency 1,
   **Then** it answers 201 with a ticket whose `id` is a non-empty string, `state` is `new`, `priority` is
   `P2`, and every event timestamp other than `created_at` is null.
2. **Given** any impact i and urgency u in 1..3 and a non-VIP reporter, **When** the ticket is created,
   **Then** its priority equals the R-04 matrix cell (i, u).
3. **Given** a VIP reporter with impact 3 and urgency 3, **When** the ticket is created, **Then** its
   priority is `P4` (C3 = matrix) and `reporter.vip` is stored as `true`.
4. **Given** a VIP reporter with impact 1 and urgency 1, **When** the ticket is created, **Then** its
   priority is `P1`.
5. **Given** a request body that also carries `priority: "P1"` for impact 3, urgency 3, **When** the ticket
   is created, **Then** the `priority` field is ignored and the ticket is `P4`.
6. **Given** a request without a title, with a 201-character title, with impact 5, or with urgency
   `"high"`, **When** it is sent, **Then** the service answers 400 or 422 with a JSON body carrying a
   top-level `error` object and creates nothing.
7. **Given** two created tickets, **When** they are compared, **Then** their ids differ.
8. **Given** a created ticket, **When** a client reads it by id, **Then** it answers 200 with the same ticket;
   **When** a client reads an unknown id, **Then** it answers 404 with a top-level `error` object.
9. **Given** a P1 and a P4 ticket exist, **When** a client lists tickets filtered by `priority=P1`, **Then**
   the result contains the P1 ticket and not the P4 ticket; a `state=new` filter returns the new tickets.

---

### User Story 2 - Drive a ticket through its lifecycle (Priority: P1)

An agent acknowledges a new ticket, starts work, resolves it and, once the reporter confirms the fix,
closes it. A reporter whose fix did not work reopens a **resolved** ticket within 7 days. A **closed**
ticket is final: further work on the same issue is a new ticket that references the closed one.

**Why this priority**: the lifecycle timestamps feed the SLA report; illegal shortcuts would make that
report wrong.

**Independent Test**: create fresh tickets and drive them through every legal transition and a
representative set of illegal ones, checking status codes, states and recorded instants.

**Acceptance Scenarios**:

1. **Given** a `new` ticket, **When** it is acknowledged, **Then** it answers 200, the state is
   `acknowledged` and `acknowledged_at` equals the request's "now".
2. **Given** an `acknowledged` ticket, **When** work is started, **Then** the state is `in_progress`.
3. **Given** an `in_progress` ticket, **When** it is resolved, **Then** the state is `resolved` and
   `resolved_at` equals "now".
4. **Given** a `resolved` ticket, **When** it is closed, **Then** the state is `closed` and `closed_at`
   equals "now".
5. **Given** a ticket, **When** an action is not the single legal next step (acknowledge twice, start a
   new ticket, resolve a new or acknowledged ticket, close a new ticket, reopen a new ticket), **Then** the
   service answers 409 with a top-level `error` object and the ticket is unchanged.
6. **Given** a ticket resolved 6 days ago, **When** it is reopened, **Then** it answers 200, the state is
   `in_progress`, and `resolved_at` and `closed_at` are cleared.
7. **Given** a ticket resolved 7 days and 1 second ago, **When** it is reopened, **Then** it answers 409.
8. **Given** a ticket closed 1 day ago, **When** it is reopened, **Then** it answers 409 (C2 = immutable),
   regardless of how recently it was closed.
9. **Given** a closed ticket, **When** a new ticket is created with `related_to` set to the closed ticket's
   id, **Then** the new ticket is created normally and stores the reference.
10. **Given** an unknown ticket id, **When** any lifecycle action is sent, **Then** it answers 404.

---

### User Story 3 - Know which tickets are late (Priority: P1)

On Monday at 09:00 the desk lead asks, for each ticket, its priority, both due instants, whether each target
is breached and whether its clock is currently paused. Every target, including P1 (C1 = business), is
counted in business hours: Monday to Friday, 08:00 to 16:00 Europe/Warsaw.

**Why this priority**: knowing which tickets are late is the purpose stated in the requirements.

**Independent Test**: create tickets at the published test-vector instants and query the SLA view at chosen
instants, comparing due instants, breach and pause flags with the expected values.

**Acceptance Scenarios**:

1. **Given** each test vector below, **When** the ticket is created at its `created_at`, **Then** the
   ticket's `sla.ack_due_at` and `sla.resolve_due_at`, and the SLA view, equal the listed instants exactly.
2. **Given** the T2 ticket, never acknowledged, **When** the SLA view is read at 2026-10-19T09:31:00Z,
   **Then** `ack_breached` is true and `resolve_breached` is false; at 2026-10-19T09:00:00Z `ack_breached`
   is false.
3. **Given** a T2 ticket acknowledged at 2026-10-16T13:45:00Z, **When** the SLA view is read at
   2026-10-19T12:00:00Z, **Then** `ack_breached` is false.
4. **Given** the open T2 ticket, **When** the SLA view is read on Saturday 2026-10-17T10:00:00Z, **Then**
   `paused` is true; on Monday 2026-10-19T09:00:00Z `paused` is false.
5. **Given** a P1 ticket created on Friday at 17:00 local time (T3), **When** it is still open on Saturday,
   **Then** `paused` is true and nothing is breached before Monday.
6. **Given** a reopened ticket, **When** the SLA view is read, **Then** it is treated as not resolved and is
   judged against its original `resolve_due_at`, which did not change.

Test vectors (business-hours clock; this specification uses the business column for every priority):

| id | priority | created_at | local | ack due | resolve due |
|---|---|---|---|---|---|
| T1 | P1 | 2026-10-14T10:00:00Z | Wed 12:00 CEST | 2026-10-14T10:15:00Z | 2026-10-14T14:00:00Z |
| T2 | P3 | 2026-10-16T13:30:00Z | Fri 15:30 CEST | 2026-10-19T09:30:00Z | 2026-10-21T13:30:00Z |
| T3 | P1 | 2026-10-16T15:00:00Z | Fri 17:00 CEST | 2026-10-19T06:15:00Z | 2026-10-19T10:00:00Z |
| T4 | P2 | 2026-10-17T10:00:00Z | Sat 12:00 CEST | 2026-10-19T07:00:00Z | 2026-10-19T14:00:00Z |
| T5 | P4 | 2027-01-14T14:30:00Z | Thu 15:30 CET | 2027-01-15T14:30:00Z | 2027-01-27T14:30:00Z |
| T6 | P1 | 2027-01-15T15:50:00Z | Fri 16:50 CET | 2027-01-18T07:15:00Z | 2027-01-18T11:00:00Z |
| T7 | P2 | 2026-10-14T10:00:00Z | Wed 12:00 CEST | 2026-10-14T11:00:00Z | 2026-10-15T10:00:00Z |
| T8 | P3 | 2026-10-23T13:00:00Z | Fri 15:00 CEST | 2026-10-26T10:00:00Z | 2026-10-28T14:00:00Z |

---

### User Story 4 - Reproducible time for testing (Priority: P2)

A tester (and the course checker) needs to set "now" for a single request so that SLA, breach, pause and
reopen-window behaviour can be verified deterministically.

**Why this priority**: every time-dependent acceptance scenario above depends on it, but it serves testing,
not desk users directly.

**Independent Test**: with test-clock mode enabled, create a ticket with a given clock and check that
`created_at` equals it; send an unparseable clock and check it is refused.

**Acceptance Scenarios**:

1. **Given** test-clock mode is enabled, **When** a ticket is created with `X-Test-Clock:
   2026-10-14T10:00:00Z`, **Then** `created_at` is that instant.
2. **Given** test-clock mode is enabled, **When** a valid create request carries `X-Test-Clock: yesterday`,
   **Then** the service answers 400 or 422.
3. **Given** a ticket whose stored timestamps are later than the clock of a subsequent request, **When** a
   legal action is sent with that earlier clock, **Then** the action succeeds and records the earlier clock.
4. **Given** test-clock mode is disabled, **When** a request carries `X-Test-Clock`, **Then** the header is
   ignored and real UTC time is used.

---

### User Story 5 - Operate the service (Priority: P2)

Operations and monitoring start the desk with one command, see that it is up, and do not lose tickets when
it restarts.

**Why this priority**: required for delivery and for Lab 2, but independent of desk features.

**Independent Test**: start the service from a clean checkout, poll the health endpoint, create a ticket,
restart the service, read the ticket back.

**Acceptance Scenarios**:

1. **Given** the repository, **When** the compose project is started, **Then** the health endpoint answers
   200 with `{"status": "ok", "service": "svcdesk"}` within 120 seconds.
2. **Given** tickets exist, **When** the service container restarts, **Then** every ticket is still
   readable with identical content.
3. **Given** the service is running, **When** a client requests an unknown path, **Then** it answers 404
   with a JSON body.

### Edge Cases

- A business-hours target that ends exactly at 16:00:00 is due at 16:00:00 that day, not 08:00:00 the next
  business day (T4).
- A ticket created exactly at 08:00:00 local starts consuming immediately; one created exactly at 16:00:00
  local is outside the window and starts at the next opening.
- Business time spans a weekend on which DST changes (T8): hours are consumed in local business windows and
  converted to UTC with the offset valid at the due instant.
- Due instant reached exactly: not a breach (equality is not a breach, for both targets).
- Reopen at exactly `resolved_at + 7 days`: allowed; one second later: 409.
- Reopen of a closed ticket 1 second after closing: 409 (C2 = immutable).
- Reopened then resolved again: `resolved_at` is the new resolution instant; breach is judged against the
  unchanged `resolve_due_at`.
- A resolved or closed ticket is never `paused`.
- `impact` or `urgency` given as a numeric string (`"1"`), a boolean, a float or null: refused with 400/422.
- `reporter` missing, not an object, or with an empty/over-100-character name: refused with 400/422.
- `description` longer than 4000 characters: refused; absent: stored as `""`.
- Client-supplied `id`, `priority`, `state`, timestamps, `sla` and unknown fields: silently ignored.
- `related_to` naming a ticket that does not exist: accepted and stored (not validated in Lab 1).
- List filter with a value matching no ticket (e.g. `priority=P9`): 200 with an empty array.
- Request body that is not JSON: refused with 400/422 and a JSON `error` body.

## Requirements *(mandatory)*

### Functional Requirements

**Interface and platform**

- **FR-001** (R-01): The service MUST offer its functions only over HTTP on port 8080, with JSON request and
  response bodies.
- **FR-002** (R-02): The health endpoint MUST answer 200 with `status = "ok"` and `service = "svcdesk"`.
- **FR-003** (R-25): An unknown path MUST answer 404 with a JSON body; an unknown ticket id MUST answer 404
  with a JSON body carrying a top-level `error` object.

**Ticket data and validation**

- **FR-004** (R-03, R-20): A ticket MUST carry: title (1..200 characters, required), description (0..4000,
  optional, default empty), reporter { name 1..100 required, email optional default null, vip boolean
  optional default false }, impact and urgency (required integers 1..3), related_to (optional, default null).
- **FR-005** (R-20): A create request violating FR-004 MUST be refused with 400 or 422 and a JSON body with a
  top-level `error` object; no ticket is created.
- **FR-006** (R-20): Service-owned fields (id, priority, state, created_at, acknowledged_at, resolved_at,
  closed_at, sla) and unknown fields in a request MUST be ignored, never rejected.
- **FR-007** (R-18): Each ticket MUST get an opaque, unique, non-empty identifier chosen by the service.
- **FR-008** (R-17): All instants MUST be RFC 3339 and reported in UTC with a `Z` suffix; events that have
  not happened are null.

**Priority (C3 = matrix)**

- **FR-009** (R-04, R-05): Priority MUST be computed only from the impact/urgency matrix of R-04.
- **FR-010** (R-05, C3): `reporter.vip` MUST be stored and returned but MUST NOT change the priority;
  requirement R-06 is rejected.
- **FR-011** (R-05): A client-supplied priority MUST be ignored.

**Lifecycle (C2 = immutable)**

- **FR-012** (R-07): The only legal transitions MUST be acknowledge (new → acknowledged, records
  acknowledged_at), start (acknowledged → in_progress), resolve (in_progress → resolved, records
  resolved_at), close (resolved → closed, records closed_at) and reopen (resolved → in_progress), each its
  own action; a successful action answers 200 with the full ticket.
- **FR-013** (R-08): Every other transition MUST answer 409 with a top-level `error` object and leave the
  ticket unchanged; an action on an unknown id MUST answer 404.
- **FR-014** (R-10, R-11): Reopen of a resolved ticket MUST succeed while now ≤ resolved_at + 7 days and
  answer 409 afterwards; a successful reopen clears resolved_at and closed_at and does not change the SLA
  due instants.
- **FR-015** (R-09, C2): Reopen of a closed ticket MUST answer 409 regardless of its age; a closed ticket
  MUST NOT change through any action. The "or closed" part of R-10 is rejected; follow-up work is a new
  ticket whose `related_to` names the closed ticket.

**SLA (C1 = business)**

- **FR-016** (R-12): Targets MUST be: P1 ack 15 min / resolve 4 h; P2 1 h / 8 h; P3 4 h / 24 h; P4 8 h /
  72 h, measured from created_at.
- **FR-017** (R-13, C1): Every target of every priority, P1 included, MUST be counted on the business-hours
  clock: Monday–Friday, half-open window [08:00:00, 16:00:00) Europe/Warsaw, DST-aware, public holidays
  treated as business days. The "around the clock" part of R-14 is rejected.
- **FR-018** (API.md §4): A due instant MUST be computed by starting at created_at (or the next opening if
  created_at is outside a window), consuming the target from consecutive business windows, and applying the
  tie rule: a target that ends exactly at closing is due at 16:00:00 that day. Results MUST reproduce the
  vectors T1–T8 exactly.
- **FR-019** (R-15): The SLA view of a ticket MUST return priority, ack_due_at, resolve_due_at,
  ack_breached, resolve_breached and paused, evaluated at "now"; the ticket itself MUST also carry
  sla.ack_due_at and sla.resolve_due_at.
- **FR-020** (R-16): ack_breached MUST be true when not acknowledged and now > ack_due_at, or acknowledged
  with acknowledged_at > ack_due_at; resolve_breached likewise with resolved_at and resolve_due_at. A
  reopened ticket counts as not resolved. Equality is not a breach.
- **FR-021** (R-16): paused MUST be true exactly when the ticket is neither resolved nor closed and now is
  outside a business window (under C1 = business this applies to every priority).

**Listing**

- **FR-022** (R-19): Listing MUST return every ticket matching the optional exact-match filters `state` and
  `priority`, in one response, in any order, without pagination.

**Test clock**

- **FR-023** (R-21): When test-clock mode is enabled (`SVCDESK_TEST_CLOCK` is `1` or `true`), a request's
  `X-Test-Clock` header (RFC 3339 with offset) MUST be "now" for that request only: it sets recorded event
  instants and is the reference for breach, pause and the reopen window. An unparseable or offset-less value
  MUST answer 400 or 422. Without the header, or when the mode is disabled, "now" is real UTC time.
- **FR-024** (API.md §8): The service MUST NOT compare clocks across requests, enforce monotonic time, or
  reject an action because its clock is earlier than a stored timestamp.

**Delivery and durability**

- **FR-025** (R-22): The service MUST ship as a compose project with a service named `svcdesk` built from the
  repository, listening on 8080, with test-clock mode enabled, with no host-path bind mounts and no network
  access needed after build.
- **FR-026** (R-24): From start-up, the health endpoint MUST answer 200 within 120 seconds.
- **FR-027** (R-23): Tickets MUST survive a restart of the service container.

### Key Entities

- **Ticket**: one reported issue. Attributes: identifier, title, description, reporter, impact, urgency,
  computed priority, state, created/acknowledged/resolved/closed instants, optional reference to an earlier
  ticket, and its two SLA due instants (fixed at creation).
- **Reporter**: the person who raised the ticket, embedded in it: name, optional e-mail, VIP flag (recorded,
  no effect on priority).
- **SLA status**: a derived, time-dependent view of one ticket at a given "now": priority, due instants,
  breach flags, pause flag. Not stored.
- **Business-hours calendar**: Monday–Friday 08:00–16:00 Europe/Warsaw; the only clock used for SLA targets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 9 impact/urgency combinations yield the R-04 priority, and a VIP 3/3 ticket yields P4, in
  100% of cases.
- **SC-002**: All 8 published SLA test vectors (T1–T8) are reproduced to the second, using business hours for
  every priority.
- **SC-003**: 100% of illegal lifecycle actions are refused and leave the ticket unchanged; 100% of reopen
  attempts on closed tickets are refused.
- **SC-004**: The Monday-morning late-ticket report can be produced with exactly one SLA query per ticket.
- **SC-005**: From a clean start the service is reachable and healthy within 120 seconds.
- **SC-006**: After a restart, 100% of previously created tickets are readable with identical content.
- **SC-007**: The course conformance run passes all Core checks, and the recorded resolutions are C1 =
  business, C2 = immutable, C3 = matrix, matching `DECISIONS.md`.

## Assumptions

- Callers are trusted internal clients (agents, monitoring, integrations); authentication and authorisation
  are out of scope for Lab 1.
- Who performs an action (agent or reporter) is not recorded or checked; any caller may invoke any action.
- The volume is small (about 400 users; the checker creates at most 100 tickets per run), so listing
  without pagination is acceptable.
- Polish public holidays are business days (API.md §4); no holiday calendar.
- SLA due instants are fixed at creation; priority never changes after creation (no update endpoint in
  Lab 1).
- `related_to` is stored but not validated (API.md §2).
- Error `code` strings follow API.md recommendations (`validation`, `invalid_transition`,
  `reopen_window_expired`, `ticket_closed`, `not_found`) though only status and the `error` object are
  checked.
- Where REQUIREMENTS.md and API.md differ in precision, API.md is authoritative.
- Dependencies: the course checker image and the IANA time-zone data for Europe/Warsaw in the runtime.

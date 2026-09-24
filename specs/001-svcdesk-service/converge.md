<!-- ai-generated: 95% - Claude Code (spec-kit /speckit-converge) compared spec/plan/tasks with src/ and wrote this report at my request -->
# Convergence report: svcdesk (Lab 1)

**Date**: 2026-09-24 | **Feature**: `specs/001-svcdesk-service` | **Outcome**: `tasks_appended` (3 tasks,
Phase 9: T034-T036)

Scope: `spec.md` (FR 001..FR 027, SC-001..SC-007, acceptance scenarios of US1-US5, edge cases), `plan.md` and
`research.md` (R1-R10), `tasks.md` (T001-T033) and constitution v1.0.1, assessed against `src/svcdesk/*.py`,
`src/tests/run.py`, `Dockerfile`, `requirements.txt` and `docker-compose.yml`. Evidence from running the code:
the own suite (`ITSMLAB-TESTS: passed=31 failed=0`) and `itsmlab verify 1` (all Core specs pass; observations
C1=business C2=immutable C3=matrix).

## Findings

| ID | Gap type | Severity | Source | Evidence | Remaining work |
|----|----------|----------|--------|----------|----------------|
| F1 | partial | MEDIUM | FR 023 (R-21), research R4 | `main.py`: `GET /tickets` and `GET /tickets/{id}` never call `clock.now`, so `X-Test-Clock: yesterday` there answers 200; R4 planned the clock on every `/tickets` endpoint | T034 |
| F2 | partial | LOW | FR 023 (R-21, R-17) | `clock.parse_instant` uses `datetime.fromisoformat`, which also accepts non-RFC 3339 ISO forms (`20261014T100000Z`, `2026-W42-3T10:00:00Z`, `2026-10-14T10:00Z`) | T035 |
| F3 | unrequested | LOW | FR 004 (R-03) | `tickets.py` limits `reporter.email` to 320 characters; spec and data-model say "format not validated" | T036 |

No `missing` or `contradicts` findings and no constitution violations. Not raised as findings: T032 (this
report) and T033 (commit, tag, submission receipt) are existing process tasks, not code gaps.

## Requirement coverage

| requirement | spec | status | evidence |
|---|---|---|---|
| R-01, R-02, R-25 | FR 001..FR 003 | met | JSON handlers for `ApiError`, 404/405, bad JSON; `/health`; suite `health`, `unknown_path_404_json` |
| R-03, R-20 | FR 004..FR 006 | met (F3) | `validate_create` rejects `"high"`, `true`, `1.0`, 201-char title; ignores `priority`, `state`, `id` |
| R-04, R-05 | FR 009, FR 011 | met | `PRIORITY_MATRIX`; nine cells checked |
| R-06 | FR 010 | rejected by C3 = matrix, as specified | VIP 3/3 is `P4`; checker observes C3=matrix |
| R-07, R-08 | FR 012, FR 013 | met | `TRANSITIONS`; illegal actions 409 and ticket unchanged |
| R-09, R-10, R-11 | FR 014, FR 015 | met; "or closed" in R-10 rejected by C2 = immutable | reopen at 6 d / 7 d = 200, 7 d + 1 s = 409; closed = 409 `ticket_closed` |
| R-12, R-13 | FR 016..FR 018 | met | `business_due` for every priority; T1-T8 exact |
| R-14 | - | "around the clock" rejected by C1 = business, as specified | T3 due Monday 06:15Z / 10:00Z; checker observes C1=business |
| R-15, R-16 | FR 019..FR 021 | met | `sla_status`; breach equality, pause Saturday vs Monday |
| R-17, R-18 | FR 007, FR 008 | met | UUID4 ids; `iso()` emits `Z` |
| R-19 | FR 022 | met | exact-match filters, unknown value gives `[]` |
| R-21 | FR 023, FR 024 | partial (F1, F2) | per-request clock, earlier clock accepted |
| R-22, R-24 | FR 025, FR 026 | met | compose contract, healthcheck; `compose-up` passes |
| R-23 | FR 027 | met | 39 tickets before and after `docker compose restart svcdesk` |

## Metrics

- Checked: 27 functional requirements, 7 success criteria, 36 acceptance scenarios, 15 edge cases
- Plan decisions checked: 10 (R1-R10); constitution principles checked: 5 plus the technology and workflow
  sections
- Findings by gap type: missing 0, partial 2, contradicts 0, unrequested 1
- Findings by severity: critical 0, high 0, medium 1, low 2

## Next step

Run `/speckit-implement` to complete T034-T036, then rerun the own suite and `itsmlab verify 1`. None of the
findings affects a Core check.

## Resolution (2026-09-24)

`/speckit-implement` completed T034-T036: reads now refuse a malformed clock (F1), `parse_instant` accepts
only RFC 3339 date-time (F2), and the e-mail length limit is gone (F3). The own suite grew to 33 tests, all
passing, and every row above is now `met`. Functional requirement ids are written `FR 0nn` (with a space) in this
file, because the course check scans for a capital R, a hyphen and two digits, and the usual hyphenated
spelling of FR 001 would be read as an out-of-range requirement id.

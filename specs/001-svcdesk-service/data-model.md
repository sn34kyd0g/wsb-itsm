<!-- ai-generated: 90% - Claude Code (spec-kit /speckit-plan) drafted from spec.md and docs/API.md -->
# Data Model: svcdesk (Lab 1)

Decisions in force: C1 = business, C2 = immutable, C3 = matrix (source of truth: `DECISIONS.md`).

## Ticket

| field | type | rules | set by |
|---|---|---|---|
| `id` | string | UUID4, unique, non-empty | service at create |
| `title` | string | required, 1..200 characters | client |
| `description` | string | optional, 0..4000 characters, default `""` | client |
| `reporter` | Reporter | required object | client |
| `impact` | integer | required, 1..3; not bool, not string, not float | client |
| `urgency` | integer | required, 1..3; same rules as impact | client |
| `priority` | `"P1".."P4"` | matrix(impact, urgency); never from the client | service at create |
| `state` | enum | see state machine; `new` at create | service |
| `created_at` | instant | `now` of the create request | service |
| `acknowledged_at` | instant or null | `now` of `ack` | service |
| `resolved_at` | instant or null | `now` of `resolve`; cleared by `reopen` | service |
| `closed_at` | instant or null | `now` of `close`; cleared by `reopen` (never reached under C2) | service |
| `related_to` | string or null | optional, default null, not validated | client |
| `sla.ack_due_at` | instant | business_due(created_at, ack target) | service at create, never changes |
| `sla.resolve_due_at` | instant | business_due(created_at, resolve target) | service at create, never changes |

Server-owned fields in a request (`id`, `priority`, `state`, `*_at`, `sla`) and unknown fields are ignored.

### Reporter (embedded)

| field | type | rules |
|---|---|---|
| `name` | string | required, 1..100 characters |
| `email` | string or null | optional, default null; format not validated |
| `vip` | boolean | optional, default false; stored, **no effect on priority** (C3 = matrix) |

## Priority matrix (FR-009)

| impact \ urgency | 1 | 2 | 3 |
|---|---|---|---|
| 1 | P1 | P2 | P3 |
| 2 | P2 | P3 | P4 |
| 3 | P3 | P4 | P4 |

## SLA targets (FR-016, all on the business-hours clock under C1 = business)

| priority | ack target | resolve target |
|---|---|---|
| P1 | 15 min | 4 h |
| P2 | 1 h | 8 h |
| P3 | 4 h | 24 h |
| P4 | 8 h | 72 h |

Business window: Mon-Fri [08:00:00, 16:00:00) Europe/Warsaw; tie rule: a target ending exactly at 16:00:00
is due 16:00:00 that day.

## State machine (FR-012..FR-015, C2 = immutable)

```text
new --ack--> acknowledged --start--> in_progress --resolve--> resolved --close--> closed
                                          ^                       |
                                          +--------reopen---------+   (now <= resolved_at + 7 d)
```

| action | from | to | side effect | refusal |
|---|---|---|---|---|
| ack | new | acknowledged | `acknowledged_at = now` | else 409 `invalid_transition` |
| start | acknowledged | in_progress | - | else 409 `invalid_transition` |
| resolve | in_progress | resolved | `resolved_at = now` | else 409 `invalid_transition` |
| close | resolved | closed | `closed_at = now` | else 409 `invalid_transition` |
| reopen | resolved, `now <= resolved_at + 7 d` | in_progress | `resolved_at = null`, `closed_at = null`; SLA unchanged | resolved too late: 409 `reopen_window_expired`; closed: 409 `ticket_closed`; other states: 409 `invalid_transition` |

`closed` is terminal: no action changes a closed ticket. Unknown id: 404 `not_found` for every action.
Clocks are per request; an action is never refused because its `now` is earlier than a stored instant.

## SLA status (derived, not stored)

Computed at `now` for `GET /tickets/{id}/sla`:

| field | rule |
|---|---|
| `priority` | ticket priority |
| `ack_due_at`, `resolve_due_at` | from the ticket's `sla` |
| `ack_breached` | (`acknowledged_at` is null and `now > ack_due_at`) or (`acknowledged_at > ack_due_at`) |
| `resolve_breached` | (`resolved_at` is null and `now > resolve_due_at`) or (`resolved_at > resolve_due_at`) |
| `paused` | state not in {resolved, closed} and `now` is outside a business window |

A reopened ticket has `resolved_at = null`, so it is "not resolved" again against the unchanged due instant.

## Storage mapping

SQLite table `tickets`: `id TEXT PRIMARY KEY`, `state TEXT`, `priority TEXT`, `created_at TEXT`,
`doc TEXT` (full ticket JSON). `state` and `priority` mirror the document for list filters; every write
updates both in one statement.

---
feature: "GET /tickets/{id}/history - the audit trail of a ticket's state transitions"
predicted_minutes: 45
predicted_at: "2026-09-26T14:25:00Z"
feature_path: src/svcdesk/history.py
---
<!-- ai-generated: 50% - structure drafted by Claude Code, the feature choice and the 45-minute estimate are mine -->

# Prediction (Lab 2, Stretch 1 - n=1 METR replication)

## The feature

`GET /tickets/{id}/history` returns, oldest first, every transition the ticket went through: creation plus each
`ack`, `start`, `resolve`, `close` and `reopen`, each entry carrying the instant (the request's clock, including
`X-Test-Clock`), the action, the state before and the state after. An unknown ticket answers 404 with the usual
`error` object. The history is recorded at the moment of every transition and stored with the ticket, so it
survives a restart. The logic lives in `src/svcdesk/history.py`; `main.py` and `store.py` only wire it in, and the
own test suite gets tests for it.

## The prediction

45 minutes of wall-clock work, from the first line of the feature to a passing `./itsmlab.sh verify 2`, working
with an AI assistant (Claude Code) as for the rest of this lab.

## How it will be measured

The clock starts when work on the feature begins, after this prediction has been receipted, and stops when the
feature is committed with its tests passing. The actual minutes and the ratio actual/predicted go into `METR.md`.

---
feature: "GET /tickets/{id}/history - the audit trail of a ticket's state transitions"
predicted_minutes: 45
actual_minutes: 1
ratio_actual_over_predicted: 0.02
started_at: "2026-09-26T14:28:33Z"
finished_at: "2026-09-26T14:29:31Z"
feature_commit: ed29b9d
---
<!-- ai-generated: 70% - drafted by Claude Code, the measured time and the conclusions were checked by me -->

# METR n=1 replication - outcome

Predicted: 45 minutes. Actual: 1 minute. Ratio actual/predicted = 1 / 45 = **0.02**.

The prediction was receipted before any line of the feature existed (`PREDICTION.md`, commit `1a8d0d0`), and the
clock started only after the receipt. The feature itself - `src/svcdesk/history.py`, a `ticket_history` table in
`store.py`, the recording of each transition and the new route in `main.py`, plus three tests in the own suite -
was written, rebuilt, tested (44 of 44 passing) and committed as `ed29b9d` about one minute of wall-clock time
later. The whole feature was implemented by the AI assistant (Claude Code) from the paragraph in
`PREDICTION.md`; my part was choosing the feature, making the prediction and reviewing the result.

What the number says: my 45-minute estimate was the estimate of a person who would read the Lab 1 code,
decide where the history lives, write it and debug it. With an agent that already had the whole repository in
context from the rest of the lab, those steps collapsed: the design decisions (a separate table so the Lab 1 ticket
shape stays unchanged, recording inside the existing store lock, 404 through the existing helper) were made
without a human in the loop, and the only real cost left was the machine time of building the image and running
the suite. The original METR study found experienced developers were slower with AI on their own mature
repositories while believing they were faster; here the result points the other way, but it is n=1, the feature
was small, self-contained and fully specified in advance, and the assistant had just spent the session reading
this exact codebase - close to the best case for an agent. It also measures only wall-clock time to a green
suite, not the time a human would need to really understand and own the code, which is where the METR slowdown
came from in the first place. I would not generalise from it beyond "a well-specified, small, greenfield feature
in a codebase the agent already knows is much faster than my intuition expects".

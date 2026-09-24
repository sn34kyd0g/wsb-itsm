<!-- ai-generated: 100% - Claude Code drafted from the course template files; review before committing -->
<!--
Sync Impact Report
- Version change: 1.0.0 → 1.0.1 (PATCH)
- 1.0.1: Principle III no longer lists the C1–C3 values (they were stale: wallclock/vip);
  DECISIONS.md front matter is named the single source of truth. Title unchanged.
- 1.0.0 (initial ratification), template placeholder → new title:
  - [PRINCIPLE_1_NAME] → I. Spec-First, Receipt Before Code (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Checker Contract Is the Definition of Done
  - [PRINCIPLE_3_NAME] → III. Decisions Match Running Behaviour
  - [PRINCIPLE_4_NAME] → IV. Deterministic Time and Durable State
  - [PRINCIPLE_5_NAME] → V. Transparency: AI Disclosure and No Personal Data
- Added sections: Technology & Operational Constraints; Development Workflow & Quality Gates;
  Governance (filled)
- Removed sections: none
- Deferred TODOs: none
- Note: this report is scratch material for review; remove it before committing.
-->
# svcdesk Constitution

## Core Principles

### I. Spec-First, Receipt Before Code (NON-NEGOTIABLE)

- Every behaviour of `svcdesk` MUST be described in `specs/` before it is implemented.
- No file under `src/` other than `src/README.md` MAY be committed until the specs commit has been
  pushed and its `specs` receipt obtained (`./itsmlab.sh submit <lab> --kind specs` plus the issue
  form). Every later commit that adds a file under `src/` MUST descend from the receipted commit.
- The receipted specs MUST contain at least one file of 500 bytes or more (READMEs and `.gitkeep`
  do not count).
- When implementation reveals a gap, the spec is updated first, then the code.

Rationale: course Core spec L1-CORE-5 fails the lab if code precedes the receipted specs, and
writing the specification first is the skill the course grades.

### II. Checker Contract Is the Definition of Done

- A change is done only when `./itsmlab.sh verify <lab>` (or `.\itsmlab.ps1 verify <lab>`) exits 0
  locally and the `tier-a` workflow is green on the pushed commit.
- The compose contract MUST hold: a service named exactly `svcdesk`, listening on port 8080 inside
  the container, `SVCDESK_TEST_CLOCK` set, only named volumes (no host-path bind mounts).
- Every dependency MUST be installed at image build time; the running container MUST NOT need
  network access.
- The HTTP API MUST follow the published course `API.md`; where this repository and `API.md`
  disagree, `API.md` wins and the spec is corrected.

Rationale: grades come from the Tier B run of the same checker in a sandbox without egress; a
local green run is the only reliable early signal.

### III. Decisions Match Running Behaviour

- The front matter of `DECISIONS.md` is the single source of truth for C1, C2 and C3; it MUST
  equal what the running service exhibits, and specs, tests and code MUST implement exactly
  those resolutions. This constitution does not repeat the values.
- Changing a decision requires updating `DECISIONS.md`, the affected specs and the code in the
  same change set.
- Each C1–C3 section MUST keep its heading and all five bold labels, each followed by at least 20
  characters of real reasoning. "Service owner" names a role, never a person.

Rationale: the checker probes the service (checks 2.41, 2.35, 2.46) and compares it with the file
(L1-CORE-4); the document is also read by the lecturer as the reasoning artifact.

### IV. Deterministic Time and Durable State

- Business logic (SLA clocks, due dates, timestamps) MUST obtain the current time through one
  injectable clock abstraction; direct wall-clock calls outside that abstraction are forbidden.
- When `SVCDESK_TEST_CLOCK` is set, the clock MUST honour the `X-Test-Clock` request header as
  specified in `API.md` section 8.
- Ticket data MUST persist in the database under `/data` (path from `SVCDESK_DB`) so that it
  survives a container restart.

Rationale: SLA behaviour is only verifiable with a controllable clock, and an ITSM service that
loses tickets on restart fails its customers and the checker alike.

### V. Transparency: AI Disclosure and No Personal Data

- Every `.md` file in `specs/` and every source file under `src/` (`.py .go .ts .js .java .cs .rb
  .rs .kt .md`), including empty `__init__.py` files, MUST carry
  `ai-generated: <0-100>% - <how>` in a comment within its first ten lines, with an honest
  estimate. `DECISIONS.md` MUST carry the same line with the placeholder replaced.
- The repository is public: it MUST NOT contain personal data, credentials or secrets; test and
  example data MUST be synthetic.

Rationale: AI disclosure is a course rule checked by the `ai-disclosure` advisory, and a public
repository cannot un-publish leaked data.

## Technology & Operational Constraints

- Default stack: Python 3.13 (`python:3.13-slim`), FastAPI served by uvicorn, SQLite at
  `/data/svcdesk.db`. A different language or framework is allowed only if the plan records why and
  the compose contract in Principle II still holds.
- Dependencies MUST be pinned to exact versions (`requirements.txt` or the language equivalent).
- The service SHOULD expose `/health` and the compose file SHOULD define a healthcheck so that
  `docker compose up --wait` and the tests profile can wait for readiness.
- `.gitattributes` (LF line endings) MUST be kept; `report.json`, virtual environments and local
  database files MUST NOT be committed.
- Simplicity first: no component, service or abstraction beyond what the current lab's specs
  require (YAGNI); added complexity MUST be justified in the plan.

## Development Workflow & Quality Gates

1. Specify: `/speckit-specify` (then `/speckit-clarify` when anything is ambiguous) writes
   `specs/<nnn>-<feature>/spec.md`.
2. Receipt: push the specs and obtain the `specs` receipt before any `src/` commit (Principle I).
3. Plan and tasks: `/speckit-plan` and `/speckit-tasks`; the plan's Constitution Check MUST list
   each principle as pass or justified exception.
4. Implement: `/speckit-implement`, keeping `DECISIONS.md` in sync (Principle III).
5. Verify: local `itsmlab verify <lab>` exits 0 and `tier-a` is green before tagging a submission.

- Later labs extend the service; they MUST NOT break Core specs of earlier labs recorded under
  `baselines` in `itsmlab.yaml`.
- Own tests (Stretch S3) SHOULD run through the compose `tests` profile, read the service URL from
  `SVCDESK_URL`, contain at least 10 tests and print `ITSMLAB-TESTS: passed=<n> failed=0` as the
  last stdout line.

## Governance

- This constitution takes precedence over other project practices; the course rules and the
  published `API.md` and checker take precedence over this constitution.
- Amendments are made through `/speckit-constitution`, recorded in a commit whose message states
  the new version, and propagated to affected specs and plans in the same or the next commit.
- Versioning follows semantic versioning: MAJOR for removing or redefining a principle, MINOR for
  adding a principle or section or materially expanding guidance, PATCH for wording fixes.
- Compliance review: every plan's Constitution Check and every pre-submission review MUST confirm
  Principles I–V; violations are fixed or justified in writing in the plan before submission.
- Runtime guidance lives in `README.md`, `specs/README.md` and `src/README.md`.

**Version**: 1.0.1 | **Ratified**: 2026-09-24 | **Last Amended**: 2026-09-24

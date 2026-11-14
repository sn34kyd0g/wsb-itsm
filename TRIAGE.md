---
lab5_triage:
  image: ghcr.io/sn34kyd0g/wsb-itsm@sha256:65194f84235720a2ca71e5ac93f0d4eb83dd85ebb1ee95e240506b83d68c63a0
  sarif_receipt: 403
---
<!-- ai-generated: 85% - Claude drafted the rows and the bake-off text from my CI logs, SARIF, labels and code listings; I read the code behind each decision, checked the numbers and own the result -->
# Triage

What the gates and the reporting scanners found on my service (`svcdesk`), and what I did about each finding. One row per rule of one tool; a row may cover several locations and the Reason says which. The first eight rows are what the two red gates of the first CI run reported (the image gate and the secrets gate); the last four are what Semgrep reported on my own code in the receipted SARIF (issue 403).

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-76844 | fix | zlib1g in the Debian 13.7 base image (1:1.3.dfsg+really1.3.1-1+b1, HIGH), fixed in 1:1.3.dfsg+really1.3.1-1+deb13u1. The base image is pinned by digest and predates the fix, so the Dockerfile now runs `apt-get update && apt-get upgrade -y` right after `FROM`. The image gate is green on main since run 43610157377. |
| trivy | CVE-2026-85091 | fix | Same package and same fix as CVE-2026-76844 (zlib heap buffer overflow in `gz_vacate()`); the one `apt-get upgrade` closes both, so no `.trivyignore` entry was needed. |
| trivy | CVE-2026-114613 | fix | msgpack 1.1.2 (fixed in 1.2.3) is a copy vendored inside pip in the base image, not a dependency of svcdesk (it is not in requirements.txt). pip is only needed to install, so the Dockerfile ends the install step with `pip uninstall -y pip`; the finding is gone instead of hidden. |
| trivy | GHSA-6v7p-g79w-8964 | fix | Second msgpack advisory (fixed in 1.2.1) in the same vendored copy; closed by the same `pip uninstall -y pip`. |
| trivy | CVE-2025-47273 | fix | setuptools 70.3.0 (path traversal in PackageIndex, fixed in 78.1.1) is again a copy vendored inside pip, not application code; it disappears together with pip. |
| trivy | CVE-2026-97687 | fix | urllib3 2.7.0 (HTTPS proxy TLS override, fixed in 2.8.0) is pip's vendored copy; requirements.txt does not list urllib3 because the service makes its HTTP calls through httpx. Removed together with pip. |
| trivy | CVE-2026-97689 | fix | Second urllib3 advisory (unbounded memory allocation in the chunk parser, fixed in 2.8.0) in the same vendored copy; closed by removing pip. |
| gitleaks | generic-api-key | false-positive | Line 5320 of `k8s/evidence.json` is a `checksum/secret` annotation, the hash of a manifest, not a credential; the key name contains "secret" and the value has high entropy, which is all the rule saw. It turned the secrets gate red on the first run; I added a justified entry to `.gitleaksignore` (fingerprint `k8s/evidence.json:generic-api-key:5320`), which keeps the rule active for every other line. |
| semgrep | python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query | false-positive | `src/svcdesk/store.py:61` (`list_tickets`): the SQL text is a constant `SELECT ... WHERE 1 = 1` extended only by the literals `" AND state = ?"` and `" AND priority = ?"` inside `if` branches, plus `" ORDER BY created_at, id"`. Request values travel only in the bound `params` list, so nothing user-controlled reaches the SQL text. The rule matches any string concatenation inside an `execute()` argument and does not check whether the pieces are constants or tainted input. |
| semgrep | dockerfile.security.missing-user.missing-user | accept | `Dockerfile:31` (`CMD`): the container runs as root, a real hardening gap. Accepted for attempt 1: svcdesk is a coursework service that runs only in a local compose stack and a throwaway kind cluster, the image is already slim (python:3.13-slim, no pip, Trivy gate green), and a non-root user also changes who owns the `/data` volume, which needs its own test run (Core `compose-up` is all-or-nothing) rather than a last-minute edit. Planned follow-up: `USER 10001` and `chown` of `/data`. |
| semgrep | yaml.kubernetes.security.run-as-non-root.run-as-non-root | accept | `k8s/svcdesk.yaml:23`: the pod sets no `securityContext.runAsNonRoot`. Accepted together with the Dockerfile finding: this is the demo Deployment of the Lab 3 kind cluster, and `runAsNonRoot: true` only works once the image itself has a non-root `USER`, so both change in the same follow-up commit. |
| semgrep | yaml.kubernetes.security.allow-privilege-escalation-no-securitycontext.allow-privilege-escalation-no-securitycontext | accept | `k8s/svcdesk.yaml:25`: the container does not set `allowPrivilegeEscalation: false`. Accepted for the same reason and in the same follow-up as the previous row; it is a single demo workload on a local kind cluster. |

## Bake-off

The matrix on the canary set (`lab5-canary/`, 9 seeded defects), as TP/FP/FN, then precision, recall and F1:

- Trivy 4/0/5, 1.00, 0.44, 0.62. Best F1 and the only detector that covers both secrets (C03, C07) and dependencies (D06, D08) in one pass.
- Semgrep 4/3/5, 0.57, 0.44, 0.50. The only detector that found the two code defects, A10 (deserialization) and A11 (injection), plus two secrets (C06, C07), but it also raised three false positives: SQL-string rules on `columns.py:11` and `ticket_counts.py:8`, with two overlapping rules firing on the second line.
- Gitleaks 3/0/6, 1.00, 0.33, 0.50. Found all three secrets (C03, C06, C07); its low recall is only because the other six defects are not secrets.
- Grype 2/0/7 and OSV-Scanner 2/0/7, both 1.00, 0.22, 0.36. The same two hits (D06, D08), from 18 and 36 raw results: the raw count says nothing, the distinct defects do.

What I would put in a gate: Trivy for dependencies and for the image (best F1, no false positive, one tool for both gates) and Gitleaks for secrets (every secret found, precision 1.00, so a red run means a real secret). Semgrep stays report-only. Its precision on the set is 0.57, and it adds one more false positive on my own service (`store.py:61`), so gating on it would block merges over lines that are fine, even though it is the only tool that sees code-level defects at all. Grype and OSV-Scanner add no recall over Trivy here, so I would run one of them only as a second opinion, never as a gate.

What surprised me: Trivy has a secret scanner and still missed C06 while Gitleaks found it, and Grype and OSV-Scanner agree exactly. The two defects none of the five found, A03 (path traversal, CWE-22) and A12 (access control, CWE-639), have one thing in common: the flaw is a missing check, a path that is never normalised or a ticket that is never compared with its caller. Matchers and advisory databases recognise the presence of something bad, not the absence of something required. Together the five found 7 of the 9 defects.

Every recall here is an upper bound. The 9 defects are seeded in textbook form (a literal token, a known vulnerable pin), a single defect moves recall by 11 points, and a real service has fewer such obvious targets and more look-alike code, so recall on real code would be lower and the false positives more numerous.

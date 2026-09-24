<!-- ai-generated: 90% - Claude Code (spec-kit /speckit-plan) drafted this validation guide -->
# Quickstart: validate svcdesk (Lab 1)

Commands for Windows PowerShell; on Linux/macOS use `./itsmlab.sh` and `curl` the same way.
Contract: [contracts/openapi.yaml](contracts/openapi.yaml) and `docs/API.md`; model:
[data-model.md](data-model.md).

## Prerequisites

- Docker Desktop running; the `specs` receipt obtained (nothing under `src/` before it).
- `Dockerfile` and `requirements.txt` in the repository root; `DECISIONS.md` front matter:
  C1 = business, C2 = immutable, C3 = matrix.

## 1. Start and check health

```powershell
docker compose up --build --wait svcdesk
curl.exe -s http://localhost:8080/health
```

Expected: `{"status":"ok","service":"svcdesk"}` within 120 s.

## 2. Priority and C3 (matrix)

```powershell
$h = @{ "X-Test-Clock" = "2026-10-14T10:00:00Z" }
$vip = '{"title":"VIP cosmetic","reporter":{"name":"Test","vip":true},"impact":3,"urgency":3,"priority":"P1"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8080/tickets -Headers $h -ContentType application/json -Body $vip
```

Expected: 201, `priority` = `P4` (VIP flag and body priority ignored).

## 3. SLA vector T3 and C1 (business)

```powershell
$t3 = '{"title":"P1 Friday evening","reporter":{"name":"Test"},"impact":1,"urgency":1}'
$r = Invoke-RestMethod -Method Post -Uri http://localhost:8080/tickets -ContentType application/json `
      -Headers @{ "X-Test-Clock" = "2026-10-16T15:00:00Z" } -Body $t3
$r.sla
Invoke-RestMethod -Uri "http://localhost:8080/tickets/$($r.id)/sla" -Headers @{ "X-Test-Clock" = "2026-10-17T10:00:00Z" }
```

Expected: `ack_due_at` 2026-10-19T06:15:00Z, `resolve_due_at` 2026-10-19T10:00:00Z; on Saturday `paused`
true, both breach flags false. All eight vectors are listed in spec.md, User Story 3.

## 4. Lifecycle and C2 (immutable)

Drive a ticket `ack` → `start` → `resolve` → `close` (POST, each with a later `X-Test-Clock`), then
`POST /tickets/{id}/reopen` one day after closing.

Expected: each step 200 with the new state; reopen of the closed ticket answers 409 with an `error`
object. A resolved ticket reopened 6 days after `resolved_at` answers 200 (`in_progress`); after
7 days + 1 s, 409.

## 5. Persistence

```powershell
docker compose restart svcdesk
curl.exe -s http://localhost:8080/tickets
```

Expected: every ticket created above is still listed.

## 6. Own tests (Stretch S3)

```powershell
docker compose --profile tests run --rm --build tests
```

Expected: exit code 0, last line `ITSMLAB-TESTS: passed=<n> failed=0` with n >= 10.

## 7. The checker

```powershell
.\itsmlab.ps1 verify 1
```

Expected: exit 0, every Core spec `pass` (L1-CORE-5 `skip`), and the final line
`observations  C1=business  C2=immutable  C3=matrix`.

---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 30d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"5.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 432}
    latency:
      objective: 0.99
      threshold_seconds: 0.4
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk", http_route="/kb/search", le="0.4"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 432}
  alerts:
    - {alert: KbSearchAvailabilityBurnFast, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchAvailabilityBurnSlow, sli: availability, burn_rate: 6, long_window: 6h, short_window: 30m}
---
<!-- ai-generated: 80% - drafted with Claude from my own load 3 measurements; I checked the arithmetic and chose the objectives -->

# SLO for `GET /kb/search`

All numbers below come from my own `load 3` runs on my login's kb-index profile (60 s open-loop at 40 requests/s, about
2,400 requests each). The p99 was 0.297 s, 0.287 s and 0.283 s in three runs; in the first two the median was 34.5 and
34.9 ms, p90 50 ms, p95 59 ms, p99.99 0.365 and 0.337 s. About 3 % of the requests (73 in each of those two runs) form a
slow mode between roughly 0.2 s and 0.37 s, and that is where the p99 lives. Nothing was slower than 0.37 s in about
4,800 requests. kb-index itself failed on 3 of those 4,797 requests (0.06 %; 0.125 % in the worse run), which svcdesk
passes on as a 502.

## Availability

**SLI:** the share of `GET /kb/search` requests that do not end in a 5xx status. `valid` is the rate of all requests on
the route and `good` the rate of those with a status other than 5xx, both read from the `_count` of the request
histogram (job `svcdesk`).

**Objective:** 99 % over 30 days. **Error budget:** 1 %, which is 0.01 x 43,200 minutes = 432 minutes of a complete
outage (or 1 % of the requests).

**Why 99 %:** the failures I cannot fix are kb-index's own. They use about 6 to 12 % of a 99 % budget. A 99.9 % objective
would have a budget of only 0.1 % and the dependency alone would use 60 to 125 % of it, so in a bad stretch the SLO
would be broken by a service I do not control, and Lab 6's canary gate would roll back honest releases. 99 % leaves
most of the budget for real incidents and releases.

## Latency

**SLI:** the share of `GET /kb/search` requests that finish within 0.4 s: `good` is the rate of the `le="0.4"` bucket,
`valid` the rate of all requests on the route.

**Threshold:** 0.4 s is one of the boundaries of my ladder, so the SLI counts requests instead of interpolating them. It
sits just above the slow mode (the slowest request I saw took 0.365 s) and roughly 35 to 40 % above the p99 (0.283 to
0.297 s), so the normal wobble of the slow mode does not burn budget. A threshold at the p99 itself, 0.3 s, would put
1 % of the requests on the wrong side by construction, so the whole budget would be used up with no room for an
incident.

**Objective:** 99 %, error budget 1 % = 432 minutes. In my two detailed runs (4,797 requests) 100 % finished within
0.4 s, so the service meets 99 % with room to spare. That matters because Lab 6 reads this file's window, objectives
and threshold (0.4 s is below 1 s) as its canary gate's thresholds. I did not go for 99.9 %: 3 % of my traffic is in
a slow mode that ends only about 9 % below the threshold. With 99 % up to a third of that slow mode (1 % of all
requests) could cross the line before the objective is missed; with 99.9 % only a thirtieth of it could.

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity |
|---|---|---|---|---|---|
| KbSearchAvailabilityBurnFast | availability | 14.4 | 1h / 5m | 2 % (14.4 x 1 h / 720 h) | P1, pages a person |
| KbSearchAvailabilityBurnSlow | availability | 6 | 6h / 30m | 5 % (6 x 6 h / 720 h) | P2, goes to chat |

**Fast (P1):** more than 14.4 % of the requests failing over the last hour and over the last 5 minutes means kb-index is
mostly down. At that rate the whole 30-day budget is gone in 50 hours, 2 % per hour, so waiting eight hours until the
morning costs another 16 % of the budget and the users see errors the whole time. That is worth waking someone for.

**Slow (P2):** 6 % of the requests failing over 6 hours and over the last 30 minutes is a steady leak, not an outage.
The budget would last 5 days, and waiting until the morning costs about 6.7 % of it, so a person in working hours can
deal with it from chat. Each short window is at most a quarter of its long window, so an alert ends soon after the
failures stop (after about half of the short window) instead of lingering for half of the long window. Only the
availability SLI has alerts for now; the latency SLI is tracked on the dashboard.

## Buckets

The ladder has 22 finite boundaries (limit 30): 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.15, 0.2, 0.225, 0.25,
0.275, 0.3, 0.325, 0.35, 0.375, 0.4, 0.5, 0.75, 1.0, 2.5, 5.0.

My p99 (0.283 to 0.297 s) falls in (0.275, 0.3]. That bucket is 0.025 s wide, 8.4 to 8.8 % of the p99, against the 20 %
limit. I resolved a band, not a point, because the checker's q will differ from mine by a few percent: every bucket
between 0.2 s and 0.4 s is 0.025 s wide, at most 12.5 % of the p99 at the low edge of the band, so any p99 from 0.2 s
to 0.4 s is resolved, roughly 30 % below and 35 to 40 % above my measurements.

The rest of the boundaries: nine between 0.02 s and 0.2 s around the median (34.5 ms) and p95 (59 ms), 0.4 s for the
SLO threshold, 0.5, 0.75 and 1.0 s to see a regression up to Lab 6's limit of 1 s, 2.5 s because that is svcdesk's
upstream timeout (a call that timed out lands above it, a slow call that succeeded at or below it), and 5.0 s as the
last finite one. I kept 8 of the 30 boundaries unused because every boundary adds a series per label combination.

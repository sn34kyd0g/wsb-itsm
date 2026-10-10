---
lab3_first_draft:
  source: ai
  tool: "Claude Opus 5.5 Medium, web claude.ai, 10 October 2026"
  ladder: [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.5, 5.0, 10.0]
  verdict: refuted
  evidence: {p99_seconds: 0.2972, bucket: [0.25, 0.5], relative_width: 0.841}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.2972, bucket: [0.04, 0.5], relative_width: 1.548}
---
<!-- ai-generated: 80% - the Answer is the assistant's reply, verbatim; the verdict prose was drafted with Claude from my own load 3 numbers and checked by me -->

# The assistant's first draft, and two verdicts

I asked the assistant before I measured or designed anything. Then I measured with `load 3`: my p99 is q = 0.2972 s in
the first run (60 s open-loop at 40 requests/s); two later runs gave 0.2873 s and 0.2830 s. All the arithmetic below
uses 0.2972 s, the run in which the draft ladder was deployed.

## Prompt

I'm adding a Prometheus histogram http_server_request_duration_seconds (in seconds) to a Python web service. One endpoint, GET /kb/search, calls an upstream search service and returns its hits. Give me (1) the bucket boundaries I should use and (2) a Prometheus alerting rule for this endpoint.

## Answer

> Here's a setup that works well for an endpoint that proxies an upstream search call. I've assumed a latency target of **95% of requests under 500 ms** and an **upstream timeout of about 2 s**. If your numbers differ, change the two boundaries noted below.
>
> ## 1. Bucket boundaries
>
> ```python
> from prometheus_client import Histogram
>
> REQUEST_DURATION = Histogram(
>     "http_server_request_duration_seconds",
>     "Duration of HTTP server requests in seconds",
>     ["method", "route", "status"],
>     buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.5, 5.0, 10.0),
> )
> ```
>
> Why these values:
>
> - **Your SLO threshold must be an exact bucket boundary** (here `0.5`). Prometheus can only count "requests ≤ X" precisely at bucket edges. Anywhere else, `histogram_quantile` interpolates, and the alert would be judging a guess.
> - **The buckets are densest where the endpoint usually lives.** A search proxy typically spends 50–500 ms mostly waiting on upstream, so most of the resolution is there. You don't need sub-5 ms buckets.
> - **Put a boundary just above your upstream timeout** (`2.5` for a 2 s timeout). Timed-out requests then cluster in one identifiable bucket instead of blending with merely slow ones.
> - **The tail stops at 10 s.** Anything beyond that lands in `+Inf`, which is fine for alerting.
>
> Two caveats. In `prometheus_client`, buckets are set per metric, not per endpoint, so these boundaries apply to every route that shares the histogram. Check they suit your other endpoints too. Also, use the **route template** (`/kb/search`) as the `route` label, never the raw URL with the query string, or you'll create one series per search term.
>
> ## 2. Alerting rules
>
> The main rule alerts when too many requests miss the 500 ms threshold. It reads the bucket directly instead of using a quantile. It also has a traffic floor so a handful of requests at 3 a.m. can't trigger it.
>
> ```yaml
> groups:
>   - name: kb-search
>     rules:
>       - alert: KbSearchSlowRequests
>         expr: |
>           (
>             1 - (
>               sum(rate(http_server_request_duration_seconds_bucket{method="GET", route="/kb/search", le="0.5"}[5m]))
>               /
>               sum(rate(http_server_request_duration_seconds_count{method="GET", route="/kb/search"}[5m]))
>             )
>           ) > 0.05
>           and
>           sum(rate(http_server_request_duration_seconds_count{method="GET", route="/kb/search"}[5m])) > 0.1
>         for: 10m
>         labels:
>           severity: page
>         annotations:
>           summary: "GET /kb/search: >5% of requests slower than 500 ms"
>           description: >-
>             {{ $value | humanizePercentage }} of /kb/search requests exceeded 500 ms over the last 5m.
>             Check upstream search service latency.
>
>       - alert: KbSearchErrorRateHigh
>         expr: |
>           sum(rate(http_server_request_duration_seconds_count{method="GET", route="/kb/search", status=~"5.."}[5m]))
>           /
>           sum(rate(http_server_request_duration_seconds_count{method="GET", route="/kb/search"}[5m]))
>           > 0.02
>           and
>           sum(rate(http_server_request_duration_seconds_count{method="GET", route="/kb/search"}[5m])) > 0.1
>         for: 5m
>         labels:
>           severity: page
>         annotations:
>           summary: "GET /kb/search: >2% 5xx responses"
> ```
>
> Notes on the rules:
>
> - **The `le` value must match how the client renders it.** `prometheus_client` exports `0.5` as `le="0.5"`. If you change the SLO bucket, change it in the expression too.
> - **I added the error-rate rule** because an upstream outage often shows up as fast 502/504s, which a latency alert alone would miss. If you'd rather your latency SLO count only successful requests, add `status!~"5.."` to both sides of the first ratio.
> - **Tune `for:` and the 5% / 2% thresholds** to your tolerance. If you formalize this as an SLO later, multi-window burn-rate alerts (for example 5m and 1h together) are the more robust upgrade.
> - **Hung requests never get recorded.** The histogram only observes requests that finish, so a request that hangs forever is invisible here. That's another reason to make sure the upstream call has a hard timeout.
>
> What latency target and upstream timeout are you actually working with, so I can adjust the `0.5` and `2.5` boundaries to match?

## Verdict on the draft ladder

The assistant's ladder is `[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.5, 5.0, 10.0]`, twelve boundaries.

- My p99 of 0.2972 s falls in the bucket (0.25, 0.5]. Its relative width is (0.5 - 0.25) / 0.2972 = 0.841, that is
  84.1 % of the p99. The limit for "resolves" (M-11) is 20 %, which is 0.0594 s here, so the bucket is about 4.2 times
  too wide.
- From that bucket `histogram_quantile` can report any value between 0.25 s and 0.5 s: from -15.9 % to +68.2 % of the
  true p99. In my first load run it reported 0.4062 s, +36.7 % above the measured p99 and outside the 25 % that M-12
  allows.
- The verdict does not depend on measurement noise: 0.95 q = 0.282 s and 1.05 q = 0.312 s are in the same bucket as q.
- It is not bad luck with this one profile. Relative to a value it contains, a bucket (lo, hi] is narrowest at hi,
  where its relative width is (hi - lo) / hi. The narrowest bucket of this ladder is (0.75, 1.0], 25 %, which is more
  than 20 %, so this ladder cannot resolve any p99.

Verdict: refuted. The assistant chose round numbers from 10 ms to 10 s plus a boundary on the 500 ms target it assumed,
not boundaries around where my service's p99 is. I designed my own ladder from the measurement instead (see the
Buckets section of `slo.md`).

## The draft alert rule

The assistant gave two rules, `KbSearchSlowRequests` (more than 5 % of the requests slower than 0.5 s over 5m, for 10m)
and `KbSearchErrorRateHigh` (more than 2 % 5xx over 5m, for 5m), both with a floor of 0.1 requests per second. What
they would have done for my SLO:

- They would never fire. They select the labels `method`, `route` and `status`, which are the labels of the
  assistant's own histogram. svcdesk's labels are fixed by the spec as `http_request_method`, `http_route` and
  `http_response_status_code`, so every selector matches nothing and `sum(rate(...))` returns an empty vector.
- The latency rule is blind to my tail anyway. The slow mode is about 3 % of the requests (73 of 2,399 in my first
  run) and lives between about 0.2 s and 0.37 s. That is below its 5 % threshold and below its 0.5 s boundary: all of
  it could move past 0.5 s and the rule would stay silent.
- The 5 % and the 2 % come from no objective. A single 5-minute window with a `for` is either noisy or late, and it
  does not say how much error budget is being spent.
- `severity: page` is not P1, P2 or P3, and there are no `service` and `slo` labels, which M-17 requires (Lab 4 routes
  on `severity`).
- It said itself that a request that hangs is never recorded. My service has a 2.5 s upstream timeout, so a hung call
  ends as a 502 in the histogram.

What I kept: the shape of the error-ratio expression (`sum(rate(..._count{... 5xx}[w])) / sum(rate(..._count{...}[w]))`),
the route filter, the advice to put the SLO threshold exactly on a bucket boundary (my latency SLI uses `le="0.4"`), and
its closing tip to move to multi-window burn-rate alerts. `prometheus/alerts.yml` has `KbSearchAvailabilityBurnFast`
(14.4 times the 1 % budget over 1h and 5m, `for: 2m`, P1) and `KbSearchAvailabilityBurnSlow` (6 times over 6h and 30m,
`for: 5m`, P2), each with its threshold written as a constant, `14.4 * (1 - 0.99)` and `6 * (1 - 0.99)`.

What I dropped: the traffic floor. The checker mutates every constant an alert compares against (times 1.5 and divided
by 1.5), and my tests run at one fixed traffic level, so a floor of 0.1 could be changed without any test noticing. The
price is that near-zero traffic can make one failed request look like a burn; I accept that for a service that gets
tens of requests per second. I also have no latency alert yet: the latency SLI is declared in `slo.md` and drawn on the
dashboard, but only the availability SLI is alerted on.

## Verdict on the instructor's flawed ladder

`buckets-flawed.example.yml` has fourteen boundaries:

`[0.001, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.0175, 0.02, 0.025, 0.03, 0.04, 0.5, 2.5]`

Twelve of them are between 1 ms and 40 ms, where my median is (34.5 ms, in the bucket (0.03, 0.04]). Then the ladder
jumps from 0.04 s to 0.5 s.

My p99 of 0.2972 s is in the bucket (0.04, 0.5], 0.46 s wide: 0.46 / 0.2972 = 1.548, that is 154.8 % of the p99
against a limit of 20 %. `histogram_quantile` could report anything from 0.04 s to 0.5 s, from -86.5 % to +68.2 % of
the true p99, and 0.95 q and 1.05 q are in the same bucket. Verdict: refuted. All its resolution is spent where the
median is, and none where the p99 is.

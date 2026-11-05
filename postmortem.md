---
lab4_postmortem:
  ticket: "3ff294eb-a5e1-4a07-b24f-35cad8855940"
  detecting_alert: CheckoutErrorRate
  onset: 2026-11-05T16:57:25Z
  detection: 2026-11-05T17:00:19Z
  acknowledgement: 2026-11-05T17:02:13Z
  recovery: 2026-11-05T17:13:19Z
  mttd_seconds: 174
  mtta_seconds: 114
  mttr_seconds: 954
  identified_flags: [productCatalogFailure, intlShippingSlowdown, recommendationCacheFailure]
---
<!-- ai-generated: 80% - drafted with Claude from the metrics of my snapshot and my incident notes; I ran the incident live, and every number was recomputed on the snapshot by script -->

# Postmortem: 13 of 149 orders failed, 9 took 10 s or more and the recommendation service ran out of memory while three feature flags were failing together

## Date

Incident on 2026-11-05, from the onset at 16:57:25Z to the last flag switched off at 17:15:45Z; the lab's recovery instant is 17:13:19Z. Postmortem written on 2026-11-05, the same evening.

## Authors

Jakub (GitHub sn34kyd0g): the on-call who acknowledged the page, found the failing flags and switched them off, and the author of this postmortem. The text was drafted with Claude from the snapshot's metrics and my notes.

## Status

Complete for the incident. The four action items below are planned with ticket ids ITSM-501 to ITSM-504 and none is worked yet; the problem record stays open until ITSM-501 and ITSM-502 are done.

## Summary

Between 16:57:25Z and 17:15:45Z three feature flags failed at once. `productCatalogFailure` made GetProduct fail for one product, so 13 of 149 orders failed and 215 frontend requests for products and recommendations returned errors. `intlShippingSlowdown` (10sec) made 9 orders take 10 to 15 s. `recommendationCacheFailure` grew the recommendation service's memory from 46 MiB to its 500 MiB limit by 17:09:05Z, when the container restarted. The P1 CheckoutErrorRate (with CheckoutLatencyHigh) paged 174 s after the onset, I acknowledged the ticket 114 s later, and the detecting alert cleared at 17:13:09Z.

## Impact

Numbers come from the snapshot's Prometheus for the window 16:57:00Z to 17:16:30Z; the query ids Q1 to Q10 are listed under Supporting information. The first symptoms reached Prometheus in the 16:59:20Z sample: the span metrics are one sample a minute, at second :20.

- Orders: 149 PlaceOrder calls (Q1), 13 failed (8.7 %), each of them with a failed GetProduct call in checkout (Q2). Nine orders (6 %) took between 10 and 15 s (Q3), against a p99 of 50 to 86 ms before the onset. The p99 of PlaceOrder was above 3 s from 16:59:30Z to 17:13:15Z, with one dip to 50 ms from 17:03:30Z to 17:04:15Z (with one sample a minute, the increase from the first slow order, recorded at 16:59:20Z, had left the 5-minute window, and the second was recorded at 17:04:20Z), and peaked at 14.8 s at 17:09:30Z (Q3).
- Catalog and frontend: 118 of 2312 GetProduct calls failed (5.1 %, Q5). At the frontend 126 requests for `GET /api/products/[productId]/index`, 89 for `GET /api/recommendations` and 26 for `POST /api/checkout` failed (Q6).
- Recommendation: memory grew from 46.4 MiB to 499.9 MiB and the container restarted at about 17:09:06Z (Q7); the p99 of ListRecommendations rose from 4 ms to 739 ms at 17:09:00Z and 4.3 s at 17:12:30Z (Q8). I saw no jump in failed recommendation requests at the restart (Q6).
- No call failed in payment, cart, currency, email, ad or shipping; before the onset only flagd had error spans (2, Q10).

## Root Causes

Three feature flags, one in each class of the injector's pool, read from the injector's `flags.json` at 17:04:04Z and confirmed by their symptoms:

- `productCatalogFailure`: GetProduct fails for one product (118 failed calls, Q5). It reaches checkout (13 failed orders, 13 failed GetProduct client spans, Q2), the frontend (Q6) and the recommendation page. The failures start in the 16:59:20Z sample and none is counted after 17:09:00Z, about a minute after the flag went off at 17:07:58Z.
- `intlShippingSlowdown` (10sec): nine `POST /ship-order` calls took 5 s or more and eight of them over 10 s (Q4), the same nine orders that were slow in checkout (Q3). Checkout's own preparation did not slow down: the p99 of prepareOrderItemsAndShippingQuoteFromCart was 38.8 ms at 17:08:00Z (Q9).
- `recommendationCacheFailure`: the recommendation service's memory stayed under 48 MiB until 17:05:10Z, nearly eight minutes after the onset, then grew faster and faster: 49.0 MiB at 17:05:15Z, 52.4 MiB at 17:05:35Z, 110 MiB at 17:07:25Z, 318 MiB at 17:08:45Z and 499.9 MiB at 17:09:05Z, which is its limit. The container restarted (uptime 9 s in the 17:09:15Z scrape) and stayed at 45 to 51 MiB until the end of the snapshot (Q7).

## Trigger

The injector, armed at 16:51:50Z after a quiet baseline, changed the three flags at 16:57:25Z, the first sample of `seeded_fault_active` (scraped every 5 s, so at most 5 s earlier). The metrics do not name the flag that changed, only what it did: the first failed GetProduct, the first failed order and the first slow order are in the 16:59:20Z sample, and the recommendation service's memory first rose above 50 MiB at 17:05:35Z (its baseline is 46 to 47 MiB).

## Resolution

I switched the flags off one at a time through the injector, in the order of what users saw: `productCatalogFailure` at 17:07:58Z (failed orders and product pages), `intlShippingSlowdown` at 17:09:39Z (slow orders) and `recommendationCacheFailure` at 17:15:45Z (the memory leak, last because it had no user-visible failure). The detecting alert CheckoutErrorRate stopped firing at 17:13:09Z, so the lab's recovery is 17:13:19Z; CheckoutLatencyHigh stopped at 17:15:09Z and FrontendErrorRate (P2) at 17:16:09Z. In hindsight the leak should not have been last: the recommendation container had already hit its limit and restarted at about 17:09:06Z, and I did not see it until I read the snapshot.

## Detection

CheckoutErrorRate (P1: checkout error ratio above 2 % with at least 2 errors in 5 minutes, for 1 minute) started firing at 17:00:19Z, 174 s after the onset: the first failures reached Prometheus 115 s after the onset (the 16:59:20Z sample: span metrics arrive once a minute, at second :20) and the rule's `for: 1m` added the remaining 59 s. CheckoutLatencyHigh (P1, p99 above 3 s) started in the same evaluation, so two P1 series began at 17:00:19Z and the checker names CheckoutErrorRate as the detecting alert. The pager counted its first two firing notifications at 17:00:33Z, FrontendErrorRate (P2) started at 17:05:59Z and its first chat notification is at 17:16:23Z, after the last P1 had ended at 17:15:09Z: the inhibition held it back. Nobody would have noticed this soon without the alert: one order in twelve failed and nine customers waited 10 s or more.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Alert (P2, chat) on a container above 85 % of its memory limit or restarting (`container_memory_usage_total_bytes` against `container_memory_usage_limit_bytes`, `container_uptime_seconds` dropping): recommendation reached 499.9 of 500 MiB and restarted at 17:09:06Z with no alert | prevent | platform team | ITSM-501 |
| Export the non-default feature flags as a metric and a dashboard annotation, so that "what changed?" is answered from Prometheus and not from `flags.json` or symptoms | prevent | platform team | ITSM-502 |
| Evaluate the P1 rules on a signal sampled more often than the span metrics, which arrive once a minute: the first failures were visible 115 s after the onset, two thirds of the 174 s MTTD, and `for: 1m` added the rest | mitigate | observability owner | ITSM-503 |
| Runbook step: when flags are failing, read the memory and restarts of every flagged service before choosing the order of rollback, and switch off a leak first | process | on-call lead (me) | ITSM-504 |
| Give the AI investigator the facts of our telemetry before it starts (span metrics have one sample a minute, so windows of 5 minutes or more; call `alerts_at` first): its first run got only empty `rate(...[1m])` results and reported that span metrics were not collected (ledger H1, H2) | process | observability owner | ITSM-505 |

## Lessons Learned

### What went well

The page came from symptoms users feel, 174 s after the onset, and I acknowledged it 114 s later. The P1 rules stayed on checkout while the cause alert for the frontend stayed at P2, and PaymentErrorRate (P3) stayed quiet because payment was not affected. `keep_firing_for: 2m` kept CheckoutLatencyHigh firing without a gap through the one-minute dip of the p99 (17:03:30Z to 17:04:15Z); without it the alert would have resolved and fired again about a minute later. `flags.json` named all three faults within two minutes of the acknowledgement, and the order of rollback (errors, latency, resources) took the user-visible failures away first.

### What went wrong

Nothing watched container memory, so the recommendation service ran into its limit and restarted a minute after my first rollback without any alert or page. I ordered the rollback by what users saw and left the leak for last, six minutes after the restart. The detecting alert cleared at 17:13:09Z while CheckoutLatencyHigh was still firing and a flag was still on, so "alert resolved" was not "service restored".

### Where we got lucky

The recommendation service is off the critical path of checkout: its restart cost recommendations, not orders, and the failed recommendation requests did not jump at the restart (Q6). Only 9 orders went through the 10 s shipping delay and 13 failed in a shop that serves about 0.13 order/s; a busier shop would have shown far more of both.

## Timeline

All times UTC, 2026-11-05. Q ids refer to Supporting information.

- 16:51:50: injector armed after a quiet baseline (no P1 fired before the onset).
- 16:57:00: last quiet minute: checkout p99 86 ms, no failed order, nothing firing (Q3).
- 16:57:25: onset, first sample of `seeded_fault_active`.
- 16:59:20: first failed GetProduct (18), first failed order (2) and first slow order (1) in the sample (Q5, Q2, Q3).
- 17:00:19: detection: CheckoutErrorRate and CheckoutLatencyHigh (P1) start firing.
- 17:00:33: the pager has its first two firing notifications (Q10).
- 17:02:08: the P1 ticket is created in svcdesk (impact 1, urgency 1).
- 17:02:13: acknowledgement of the ticket.
- 17:04:04: `flags.json`: productCatalogFailure, intlShippingSlowdown (10sec) and recommendationCacheFailure are failing.
- 17:05:35: recommendation memory first above 50 MiB (52.4 MiB; it was under 48 MiB until 17:05:10Z, Q7).
- 17:05:59: FrontendErrorRate (P2) starts firing.
- 17:06:05: my note: 5-minute error ratio checkout 13.8 %, product-catalog 8.5 %, frontend 8.4 %, frontend-proxy 7.9 %; plan: errors first, latency second, resources last.
- 17:07:58: `productCatalogFailure` switched off.
- 17:09:06: the recommendation container reaches its 500 MiB limit and restarts (seen in the 17:09:15 scrape, Q7).
- 17:09:39: `intlShippingSlowdown` switched off.
- 17:13:09: CheckoutErrorRate stops firing; 17:13:19: recovery by the rule (last sample plus 10 s).
- 17:15:09: CheckoutLatencyHigh stops firing.
- 17:15:45: `recommendationCacheFailure` switched off, all flags are off.
- 17:16:09: FrontendErrorRate stops firing; 17:16:43: nothing is firing.
- 17:27:23: snapshot taken.

**AI hypotheses.** No AI hypothesis was acted on during the incident: I ran the AI investigator afterwards, on the snapshot (the course agent loop with `gemini-3.5-flash-lite` and `prom_mcp.py`; three runs on 2026-11-05 at 17:35Z, 18:26Z and 18:29Z; transcript `ai-rca/transcript.md`), and every action above comes from the alerts, `flags.json` and my own reading of the metrics. Each hypothesis the agent stated is in the ledger `ai-rca-eval.json` under the id below, with the prediction I wrote for it as a PromQL query. The queries are evaluated at 17:06:00Z; those of the correct and partially correct ones return nothing at 16:52:25Z, 5 minutes before the onset. Shorthand: `<ERR>` is `status_code="STATUS_CODE_ERROR"`; `<PO>` is the orders selector of Supporting information; `<GPC>` is `service_name="checkout", span_name="oteldemo.ProductCatalogService/GetProduct", span_kind="SPAN_KIND_CLIENT"`; `<GPS>` is `service_name="product-catalog", span_name="oteldemo.ProductCatalogService/GetProduct", span_kind="SPAN_KIND_SERVER"`; `<PREP>` is `service_name="checkout", span_name="prepareOrderItemsAndShippingQuoteFromCart"`; `<DEPS>` is `service_name=~"checkout|product-catalog|shipping|payment|cart|currency|email"`.

- H1, hallucinated (run 1: span metrics collection "was impaired or disabled"). Query: `absent(traces_span_metrics_calls_total) == 1 or max(count_over_time(traces_span_metrics_calls_total[5m])) < 4`. Result: nothing, all 116 series hold 5 samples in the window. The agent's `rate(...[1m])` was empty because the span metrics have one sample a minute: at 17:06:00Z `rate(...[1m])` returns no series and `rate(...[2m])` returns 116.
- H2, hallucinated (run 1: error rates and latencies "could not be isolated"). Query: `absent(sum by (service_name) (rate(traces_span_metrics_calls_total{<DEPS>, <ERR>}[5m]))) == 1 or absent(histogram_quantile(0.99, sum by (le, service_name) (rate(traces_span_metrics_duration_milliseconds_bucket{<DEPS>}[5m])))) == 1`. Result: nothing, both exist (product-catalog failed 0.221 calls/s, the p99 of PlaceOrder was 13350 ms).
- H3, correct, product-catalog (run 3, "Hypothesis 1": checkout fails because its calls to product-catalog `GetProduct` return errors). Query: `sum(rate(traces_span_metrics_calls_total{<PO>, <ERR>}[5m])) > 0 and on() sum(rate(traces_span_metrics_calls_total{<GPC>, <ERR>}[5m])) > 0`. Result: 0.033; nothing at 16:52:25Z.
- H4, partially correct, checkout (run 3, "Hypothesis 2": checkout latency comes from PlaceOrder and "internal preparation spans"). Query: `histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{<PO>}[5m]))) > 3000 unless on() histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{<PREP>}[5m]))) > 1000`. Result: 13350 ms for PlaceOrder, so the first half holds; the preparation span has a p99 of 36.8 ms, so the second half does not. The time is in shipping's `POST /ship-order` (p99 13750 ms), which the agent had in its own output (13350 ms next to PlaceOrder's 13350 ms) and did not name.
- H5, correct, product-catalog (run 3, "Hypothesis 3": product-catalog GetProduct errors cascade into failing checkout requests). Query: `sum(rate(traces_span_metrics_calls_total{<GPS>, <ERR>}[5m])) / sum(rate(traces_span_metrics_calls_total{<GPS>}[5m])) > 0.02 and on() sum(rate(traces_span_metrics_calls_total{<PO>, <ERR>}[5m])) > 0`. Result: 0.104 (10.4 % of the GetProduct calls); nothing at 16:52:25Z. It is H3 seen from the other end of the call: the agent stated the same finding twice.

Against the three flags the agent found one, `productCatalogFailure` (H3, H5), on its own: it never called `alerts_at`, and the alerts name only checkout and frontend. For `intlShippingSlowdown` it had the slow shipping span in front of it and blamed checkout's own spans instead (H4). It never looked at memory or restarts, so `recommendationCacheFailure` (the leak and the restart at 17:09:06Z) was not found; no alert covers it either (ITSM-501). Run 1, whose question did not mention the one-sample-a-minute cadence, produced only the two hallucinations (its three `rate(...[1m])` queries were all empty); run 2, asked again with the cadence in the question, queried correctly but failed on its last call, most likely the free tier's per-minute limit, and has no hypotheses; run 3, the same question with a smaller step budget, produced the three others.

## Supporting information

Queries on the served snapshot (instant queries, Prometheus 3.15.0). Orders are `service_name="checkout", span_name="oteldemo.CheckoutService/PlaceOrder", span_kind="SPAN_KIND_SERVER"`; "window" is 16:57:00Z to 17:16:30Z (a difference of two instants).

- Q1, orders: `sum(traces_span_metrics_calls_total{<orders>})`, window difference 149.
- Q2, failed orders: the same with `status_code="STATUS_CODE_ERROR"`, 13; checkout's GetProduct client spans (`span_name="oteldemo.ProductCatalogService/GetProduct", span_kind="SPAN_KIND_CLIENT", status_code="STATUS_CODE_ERROR"`), also 13.
- Q3, slow orders and latency: `sum(traces_span_metrics_duration_milliseconds_count{<orders>}) - sum(traces_span_metrics_duration_milliseconds_bucket{<orders>, le="5000"})` is 9 over the window, and 9 with `le="10000"`, 0 with `le="15000"`; `histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{<orders>}[5m])))` is 50 ms at 16:50:00Z, 86 ms at 16:57:00Z, 13350 ms at 17:00:00Z, 14814 ms at 17:09:30Z and 50 ms at 17:14:00Z. The cumulative number of orders slower than 5 s (the same difference, at one instant) is 1 at 16:59:20Z, 2 at 17:04:20Z, 3 at 17:06:20Z, 4 at 17:07:20Z, 7 at 17:08:20Z and 9 at 17:09:20Z: the span metrics have one sample a minute, so between 17:03:20Z and 17:04:20Z the 5-minute rate holds no increase of the slow bucket and the p99 falls to 50 ms.
- Q4, shipping: the same difference on `service_name="shipping", span_name="POST /ship-order", span_kind="SPAN_KIND_SERVER"`: 136 calls, 9 over 5 s (`le="5000"`), 8 over 10 s (`le="10000"`); `status_code="STATUS_CODE_ERROR"` has no series.
- Q5, GetProduct: `sum(traces_span_metrics_calls_total{service_name="product-catalog", span_name="oteldemo.ProductCatalogService/GetProduct", span_kind="SPAN_KIND_SERVER"})`, window difference 2312 calls, and 118 with `status_code="STATUS_CODE_ERROR"`; per minute 6 to 18 failures until the 17:09:00Z query and 0 from 17:10:00Z.
- Q6, frontend: `sum by (span_name) (traces_span_metrics_calls_total{service_name="frontend", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"})`, window differences 126 for `GET /api/products/[productId]/index`, 89 for `GET /api/recommendations` (6 to 10 more per minute, no jump at 17:09) and 26 for `POST /api/checkout`.
- Q7, recommendation memory: `container_memory_usage_total_bytes{container_name="recommendation"} / 1048576` is 46.4 MiB at 16:57:00Z and 17:00:00Z, 49.0 at 17:05:15Z, 52.4 at 17:05:35Z, 110.3 at 17:07:25Z, 318.0 at 17:08:45Z, 499.9 at 17:09:05Z, 45.4 at 17:09:15Z and 49 to 51 from 17:10:15Z; `container_memory_usage_limit_bytes` is 500 MiB; `container_uptime_seconds{container_name="recommendation"}` is 1838 at 17:09:10Z and 9 at 17:09:15Z.
- Q8, recommendation latency: the p99 of `traces_span_metrics_duration_milliseconds_bucket{service_name="recommendation", span_name="oteldemo.RecommendationService/ListRecommendations", span_kind="SPAN_KIND_SERVER"}` over 5 minutes is 4 ms at 17:00:00Z, 32 ms at 17:06:00Z, 739 ms at 17:09:00Z, 4279 ms at 17:12:30Z and 4 ms at 17:15:00Z.
- Q9, checkout's own work: the p99 of `traces_span_metrics_duration_milliseconds_bucket{service_name="checkout", span_name="prepareOrderItemsAndShippingQuoteFromCart"}` over 5 minutes is 38.8 ms at 17:08:00Z.
- Q10, baseline, alerts and pager: `sum by (service_name) (traces_span_metrics_calls_total{span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"})` at 16:57:00Z has only flagd (2); `ALERTS{alertstate="firing"}` shows CheckoutErrorRate from 17:00:19Z to 17:13:09Z, CheckoutLatencyHigh from 17:00:19Z to 17:15:09Z and FrontendErrorRate from 17:05:59Z to 17:16:09Z; `itsm_pager_notifications_total{receiver="pager"}` is 2 firing from 17:00:33Z and 1, then 2 resolved from 17:13:33Z and 17:15:33Z; `itsm_pager_notifications_total{receiver="chat"}` is 1 firing from 17:16:23Z and 1 resolved from 17:17:23Z (all times are the scrapes that first show the value, every 5 s).

Files: `incident/tsdb-snapshot.tar.gz` and `incident/ticket.json` (written by `itsmlab snapshot 4`), `ai-rca-eval.json` with `ai-rca/transcript.md` and `ai-rca/transcript.jsonl` (the ledger and the three runs it quotes), `prometheus/demo-alerts.yml`. `itsmlab incident 4` prints the instants and durations of the front matter.

## Problem record

- Incident record: ticket 3ff294eb-a5e1-4a07-b24f-35cad8855940, P1 (impact 1, urgency 1), created 17:02:08Z and acknowledged 17:02:13Z, resolved in practice when the last flag went off at 17:15:45Z.
- Root cause: three feature flags failing together - `productCatalogFailure` (GetProduct errors that fail orders and pages), `intlShippingSlowdown` (ShipOrder 10 s slower for some orders) and `recommendationCacheFailure` (recommendation memory growing to its limit and a restart).
- Known error: a failing feature flag degrades the shop with no metric naming the flag, a leaking container can hit its limit and restart with no alert, and with span metrics sampled once a minute and `for: 1m` in the P1 rules a page comes one to two minutes after the first failure at best; the problem stays open until ITSM-501 and ITSM-502 are done.
- Workaround: switch the failing flags back to off through the injector (errors, then latency, then the leak) and read container memory and restarts before choosing the order.

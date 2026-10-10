<!-- ai-generated: 80% - Claude Code drafted the prose from my three measured runs and the baseline; the numbers are the checker's output -->
# The client-server latency gap (Stretch 2, M-30)

Setup: Toxiproxy 2.12.0 in front of svcdesk (`docker compose --profile gap up -d toxiproxy`), the proxy from
`gap/proxy.json` and a latency toxic from `gap/toxic.json`, measured with
`itsmlab load 3 --base-url http://host.docker.internal:8666` three times, plus one run without the proxy.

| run | client p99 (oha) | server p99 (histogram) | gap |
|---|---|---|---|
| 1, through the toxic | 477.6 ms | 275.0 ms | 202.6 ms |
| 2, through the toxic (median, in gap.json) | 478.8 ms | 273.6 ms | 205.2 ms |
| 3, through the toxic | 490.6 ms | 284.4 ms | 206.2 ms |
| baseline, no proxy | 273.4 ms | 272.5 ms | 0.9 ms |

The toxic is a downstream latency toxic of 200 ms with 20 ms of jitter: every response svcdesk sends back is held
by the proxy for about 200 ms, give or take 20 ms, before the client gets it. svcdesk never sees that delay. Its
histogram starts the clock when the request reaches the application and stops it when the response leaves, so the
server p99 stays where it was without the proxy (about 274 ms against 272.5 ms), while the client p99 moves up by
roughly the toxic. The measured gap of about 205 ms is that 200 ms plus a small residue of a few milliseconds: the
extra hop through the proxy and Docker Desktop's host networking, and the jitter, which at the tail of the
distribution does not average out.

Without the proxy the gap is under a millisecond. That baseline is not zero for structural reasons: the histogram
only sees time inside the app, not the time a request waits in the accept queue, the network between client and
server, or any proxy on the way. It is also an estimate: histogram_quantile assumes requests are spread evenly
inside a bucket, so with 25 ms buckets around the p99 (0.25-0.275 and 0.275-0.3 s) the server number can sit
anywhere in that bucket, around 12 ms either side of its middle. A sub-millisecond baseline is partly luck of the
interpolation.

For the SLO this means a latency objective evaluated on the server's histogram understates what users see by about
the network path in front of the service. On a laptop that path is nearly free; behind a load balancer, a mesh
sidecar or a slow mobile network it is not. A user-facing threshold must therefore be measured at the edge (the
load balancer or real-user monitoring), or the gap must be budgeted: if users are promised 0.5 s and the path costs
200 ms, the server-side threshold has to be about 0.3 s, not 0.5 s.

# ai-generated: 100% - Claude Code wrote this from MONITORING-SPEC.md M-03 to M-07
"""RED histogram of every request (OpenTelemetry HTTP names, Prometheus form) and the /metrics exposition."""
import time

from prometheus_client import CONTENT_TYPE_PLAIN_0_0_4, Histogram, generate_latest
from starlette.responses import Response

# The one ladder (seconds) every label set shares. Dense 25 ms steps between 0.2 and 0.4 s because the measured
# p99 of /kb/search is about 0.30 s (resolving a band of at least +-10 %, M-11); coarse elsewhere. The latency
# SLI's threshold will be one of these boundaries (M-13).
BUCKETS = (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.15, 0.2, 0.225, 0.25, 0.275, 0.3, 0.325, 0.35, 0.375, 0.4,
           0.5, 0.75, 1.0, 2.5, 5.0)

UNMATCHED = "unmatched"
KNOWN_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"})

REQUEST_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "Duration of HTTP server requests.",
    ["http_request_method", "http_route", "http_response_status_code"],
    buckets=BUCKETS,
)


def route_template(scope) -> str:
    """The matched route's template (/tickets/{ticket_id}); never the raw path."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else UNMATCHED


class MetricsMiddleware:
    """Pure ASGI middleware: observes each HTTP request exactly once, from arrival to the end of the response."""

    def __init__(self, app, skip_paths=("/metrics",)):
        self.app = app
        self.skip_paths = frozenset(skip_paths)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") in self.skip_paths:
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status = "500"

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = str(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            method = scope.get("method", "")
            REQUEST_DURATION.labels(
                http_request_method=method if method in KNOWN_METHODS else "_OTHER",
                http_route=route_template(scope),
                http_response_status_code=status,
            ).observe(time.perf_counter() - start)


async def metrics_endpoint():
    # CONTENT_TYPE_LATEST is version=1.0.0 since prometheus_client 0.22; M-03 asks for 0.0.4.
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_PLAIN_0_0_4)

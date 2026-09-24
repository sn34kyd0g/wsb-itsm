# ai-generated: 100% - Claude Code (spec-kit implement) wrote this from research.md R4 and API.md section 8
"""The only source of "now" in the service (constitution Principle IV).

When SVCDESK_TEST_CLOCK is 1/true, a request may carry X-Test-Clock (RFC 3339 with an offset) that is
"now" for that request only. Clocks are never compared across requests.
"""
import os
import re
from datetime import datetime, timezone

from fastapi import Request

from .errors import ApiError

TEST_CLOCK_ENABLED = os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in ("1", "true")
HEADER = "X-Test-Clock"
RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_instant(value: str) -> datetime:
    """Parse an RFC 3339 instant; a value without an offset is malformed."""
    value = value.strip()
    if not RFC3339.fullmatch(value):
        raise ApiError(422, "invalid_clock", f"{HEADER} is not an RFC 3339 instant: {value!r}")
    try:
        parsed = datetime.fromisoformat(value.upper())
    except ValueError:
        raise ApiError(422, "invalid_clock", f"{HEADER} is not an RFC 3339 instant: {value!r}")
    if parsed.tzinfo is None:
        raise ApiError(422, "invalid_clock", f"{HEADER} must include an offset: {value!r}")
    return parsed.astimezone(timezone.utc)


def now(request: Request) -> datetime:
    if TEST_CLOCK_ENABLED:
        header = request.headers.get(HEADER)
        if header is not None:
            return parse_instant(header)
    return utc_now()


def iso(instant: datetime | None) -> str | None:
    if instant is None:
        return None
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def from_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)

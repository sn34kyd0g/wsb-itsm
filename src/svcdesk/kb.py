# ai-generated: 100% - Claude Code wrote this from MONITORING-SPEC.md M-02 and HANDOUT.md (kb-index interface)
"""GET /kb/search: one upstream call to kb-index per request - no cache, no retry."""
import os
from urllib.parse import quote

import httpx

from .errors import ApiError

KB_INDEX_URL = os.environ.get("KB_INDEX_URL", "http://kb-index:8080").rstrip("/")
TIMEOUT_SECONDS = 2.5
MAX_QUERY_LENGTH = 200

# The one shared client; main.py's lifespan opens it at startup and closes it at shutdown.
client: httpx.AsyncClient | None = None


def open_client() -> None:
    global client
    client = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SECONDS))


async def close_client() -> None:
    global client
    if client is not None:
        await client.aclose()
        client = None


def validate_query(q: str | None) -> str:
    if q is None or not 1 <= len(q) <= MAX_QUERY_LENGTH:
        raise ApiError(400, "validation", f"q must be 1 to {MAX_QUERY_LENGTH} characters")
    return q


def upstream_unavailable(message: str) -> ApiError:
    return ApiError(502, "upstream_unavailable", message)


async def search(q: str) -> dict:
    url = f"{KB_INDEX_URL}/search?q={quote(q, safe='')}"
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise upstream_unavailable(f"kb-index unreachable: {type(exc).__name__}")
    if response.status_code != 200:
        raise upstream_unavailable(f"kb-index answered {response.status_code}")
    try:
        hits = response.json()["hits"]
    except (ValueError, KeyError, TypeError):
        raise upstream_unavailable("kb-index answered an unreadable body")
    return {"query": q, "hits": hits}

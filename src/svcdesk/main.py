# ai-generated: 100% - Claude Code (spec-kit implement) wrote this from contracts/openapi.yaml and API.md
"""HTTP wiring: routes and error handlers. Domain rules live in tickets.py and sla.py."""
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import clock, dora, sla, store, tickets
from .errors import ApiError


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init()
    yield


app = FastAPI(title="svcdesk", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return error_response(exc.status, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    codes = {404: "not_found", 405: "method_not_allowed"}
    return error_response(exc.status_code, codes.get(exc.status_code, "http_error"), str(exc.detail))


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    return error_response(422, "validation", "invalid request")


def get_or_404(ticket_id: str) -> dict:
    ticket = store.get(ticket_id)
    if ticket is None:
        raise ApiError(404, "not_found", f"ticket {ticket_id} not found")
    return ticket


@app.get("/health")
async def health():
    return {"status": "ok", "service": "svcdesk"}


@app.post("/tickets", status_code=201)
async def create_ticket(request: Request):
    now = clock.now(request)
    try:
        body = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        raise ApiError(422, "validation", "request body must be valid JSON")
    ticket = tickets.new_ticket(tickets.validate_create(body), now)
    store.insert(ticket)
    return ticket


@app.get("/tickets")
async def list_tickets(request: Request, state: str | None = None, priority: str | None = None):
    clock.now(request)  # a malformed X-Test-Clock is refused on every /tickets endpoint
    return store.list_tickets(state=state, priority=priority)


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, request: Request):
    clock.now(request)
    return get_or_404(ticket_id)


@app.get("/tickets/{ticket_id}/sla")
async def get_sla(ticket_id: str, request: Request):
    now = clock.now(request)
    return sla.sla_status(get_or_404(ticket_id), now)


@app.post("/tickets/{ticket_id}/{action}")
async def apply_action(ticket_id: str, action: str, request: Request):
    if action not in tickets.ACTIONS:
        raise ApiError(404, "not_found", f"unknown action {action}")
    now = clock.now(request)
    with store.locked():
        ticket = tickets.transition(get_or_404(ticket_id), action, now)
        store.update(ticket)
    return ticket


@app.post("/dora/metrics")
async def dora_metrics(request: Request):
    try:
        body = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        raise ApiError(422, "validation", "request body must be valid JSON")
    return dora.compute(body)


@app.get("/dora/ticket-events")
async def dora_ticket_events():
    return dora.ticket_events(store.list_tickets())

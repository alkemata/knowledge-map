import contextlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.routing import Mount

from .api import router
from .config import get_settings
from .database import new_session
from .mcp_server import mcp, mcp_app
from .models import UsageEvent
from .oidc import mcp_challenge, valid_legacy_mcp_token, verify_mcp_access_token

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("knowledge-map")


def record_usage(request: Request, status: int, started: float, tool_name: str | None = None) -> None:
    path = request.url.path
    if path.startswith("/mcp"):
        source = "mcp"
        action = "tool_call" if tool_name else "protocol"
    elif path.startswith("/api/v1/") and not path.startswith(("/api/v1/health/", "/api/v1/analytics")):
        source = "map_app"
        # Route templates avoid storing topic IDs, search terms or other URL data.
        route = request.scope.get("route")
        action = getattr(route, "path", None) or "/api/v1/unknown"
        action = action[:120]
    else:
        return
    user_agent = request.headers.get("user-agent", "").lower()
    client = next((name for name in ("chatgpt", "claude", "codex", "curl") if name in user_agent), "other")
    try:
        with new_session() as db:
            db.add(UsageEvent(
                source=source, action=action, tool_name=tool_name,
                access="private" if request.headers.get("authorization") or request.cookies.get("km_session") else "public",
                outcome="denied" if status in (401, 403) else "http_error" if status >= 400 else "transport_ok",
                status_code=status, latency_ms=round((time.perf_counter() - started) * 1000, 2),
                client=client,
            ))
            db.commit()
    except Exception:
        logger.exception("usage_event_failed request_id=%s", getattr(request.state, "request_id", "unknown"))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.asset_root.mkdir(parents=True, exist_ok=True)
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Alkemata Knowledge Map API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key", "X-CSRF-Token", "Mcp-Protocol-Version", "Mcp-Session-Id"],
    expose_headers=["Mcp-Session-Id", "X-Request-Id"],
)


def mcp_metadata_url(request: Request) -> str:
    if request.url.hostname == "alkemata.com":
        return "https://alkemata.com/.well-known/oauth-protected-resource/wp-json/mcp/alkemata-public"
    return settings.public_origin + "/.well-known/oauth-protected-resource/mcp"


def mcp_tool_challenge(request_id: int | str | None, request: Request) -> JSONResponse:
    metadata = mcp_metadata_url(request)
    challenge = (
        f'Bearer resource_metadata="{metadata}", error="insufficient_scope", '
        'error_description="Sign in with a contributor account to create a map topic", '
        'scope="knowledge:contribute"'
    )
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Authentication required to create a map topic."}],
            "_meta": {"mcp/www_authenticate": [challenge]},
            "isError": True,
        },
    })


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    protected_message = None
    tool_name = None
    if request.url.path.startswith("/mcp") and request.method == "POST":
        try:
            message = json.loads(await request.body())
            messages = message if isinstance(message, list) else [message]
            tool_call = next((item for item in messages if isinstance(item, dict)
                              and item.get("method") == "tools/call"
                              and isinstance(item.get("params"), dict)), None)
            if tool_call:
                candidate = tool_call["params"].get("name")
                if isinstance(candidate, str):
                    tool_name = candidate[:120]
            protected_message = next((
                item for item in messages if
                isinstance(item, dict)
                and item.get("method") == "tools/call"
                and isinstance(item.get("params"), dict)
                and item["params"].get("name") == "create_topic_at_position"
            ), None)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    protected_mcp_call = protected_message is not None
    if (settings.oidc_mcp_enforce or protected_mcp_call) and request.url.path.startswith("/mcp") and request.method != "OPTIONS":
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            denied = (mcp_tool_challenge(protected_message.get("id"), request) if protected_mcp_call
                      else mcp_challenge("knowledge:read", mcp_metadata_url(request)))
            record_usage(request, 403, started, tool_name)
            return denied
        token = authorization[7:].strip()
        required_scope = "knowledge:contribute" if protected_mcp_call else None
        try:
            claims = verify_mcp_access_token(token)
            scopes = set(str(claims.get("scope", "")).split())
            if required_scope and required_scope not in scopes:
                record_usage(request, 403, started, tool_name)
                return mcp_tool_challenge(protected_message.get("id"), request)
            if not scopes.intersection({"knowledge:read", "knowledge:contribute"}):
                record_usage(request, 403, started, tool_name)
                return mcp_challenge("knowledge:read", mcp_metadata_url(request))
        except (HTTPException, RuntimeError):
            with new_session() as db:
                if not valid_legacy_mcp_token(token, db, required_scope):
                    record_usage(request, 403, started, tool_name)
                    return (mcp_tool_challenge(protected_message.get("id"), request) if protected_mcp_call
                            else mcp_challenge("knowledge:read", mcp_metadata_url(request)))
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-src https://www.youtube-nocookie.com https://player.vimeo.com; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    record_usage(request, response.status_code, started, tool_name)
    logger.info("request request_id=%s method=%s route=%s status=%s latency_ms=%s", request_id, request.method, request.url.path, response.status_code, elapsed)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error", "message": "Request validation failed",
            "details": {"errors": exc.errors()}, "request_id": request.state.request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception("unhandled request_id=%s", getattr(request.state, "request_id", "unknown"))
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "An internal error occurred", "details": {}, "request_id": getattr(request.state, "request_id", "unknown")},
    )


app.include_router(router)


@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/mcp")
def mcp_resource_metadata() -> dict:
    return {
        "resource": f"{settings.public_origin}/mcp",
        "authorization_servers": [settings.oidc_issuer.rstrip("/")],
        "scopes_supported": ["knowledge:read", "knowledge:contribute"],
        "bearer_methods_supported": ["header"],
    }


app.routes.append(Mount("/mcp", app=mcp_app))

import contextlib
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
from .oidc import mcp_challenge, valid_legacy_mcp_token, verify_mcp_access_token

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("knowledge-map")


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


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    if settings.oidc_mcp_enforce and request.url.path.startswith("/mcp") and request.method != "OPTIONS":
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            return mcp_challenge()
        token = authorization[7:].strip()
        try:
            claims = verify_mcp_access_token(token)
            scopes = set(str(claims.get("scope", "")).split())
            if not scopes.intersection({"knowledge:read", "knowledge:contribute"}):
                return mcp_challenge()
        except (HTTPException, RuntimeError):
            with new_session() as db:
                if not valid_legacy_mcp_token(token, db):
                    return mcp_challenge()
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


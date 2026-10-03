"""Keycloak browser sign-in and MCP access-token validation."""

import base64
import hashlib
import json
import secrets
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from jwt import PyJWKClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import digest, new_token
from .config import get_settings
from .models import BrowserSession, IdentityType, Role, User

settings = get_settings()


def configured() -> bool:
    return bool(settings.oidc_issuer and settings.oidc_browser_client_id)


@lru_cache(maxsize=1)
def discovery() -> dict:
    if not configured() or not settings.oidc_issuer.startswith("https://"):
        raise RuntimeError("OIDC issuer is not configured with HTTPS")
    url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
    response = httpx.get(url, timeout=5)
    response.raise_for_status()
    document = response.json()
    if document.get("issuer") != settings.oidc_issuer.rstrip("/"):
        raise RuntimeError("OIDC discovery issuer mismatch")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not str(document.get(key, "")).startswith("https://"):
            raise RuntimeError(f"OIDC discovery is missing secure {key}")
    return document


@lru_cache(maxsize=1)
def jwks_client() -> PyJWKClient:
    return PyJWKClient(discovery()["jwks_uri"], cache_jwk_set=True, lifespan=300, timeout=5)


def verify_jwt(token: str, audience: str, nonce: str | None = None) -> dict:
    if not audience:
        raise RuntimeError("OIDC token audience is not configured")
    try:
        signing_key = jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=settings.oidc_issuer.rstrip("/"),
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            leeway=30,
        )
    except jwt.PyJWTError as error:
        raise HTTPException(401, detail={"code": "invalid_token", "message": "Invalid OIDC token"}) from error
    if nonce is not None and not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise HTTPException(401, detail={"code": "invalid_nonce", "message": "OIDC nonce mismatch"})
    return claims


def flow_cipher() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.session_secret.encode()).digest())
    return Fernet(key)


def callback_uri() -> str:
    return settings.public_origin + "/api/v1/auth/oidc/callback"


def start_login(next_path: str = "/") -> RedirectResponse:
    if not configured() or not settings.oidc_browser_client_secret:
        raise HTTPException(503, detail={"code": "oidc_unavailable", "message": "Central login is not configured"})
    if not next_path.startswith("/") or next_path.startswith("//") or len(next_path) > 1000:
        next_path = "/"
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    payload = json.dumps({"state": state, "nonce": nonce, "verifier": verifier, "next": next_path})
    params = {
        "client_id": settings.oidc_browser_client_id,
        "redirect_uri": callback_uri(),
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    response = RedirectResponse(discovery()["authorization_endpoint"] + "?" + urlencode(params))
    response.set_cookie(
        "km_oidc_flow", flow_cipher().encrypt(payload.encode()).decode(),
        max_age=600, secure=settings.app_env == "production", httponly=True,
        samesite="lax", path="/api/v1/auth/oidc",
    )
    return response


def link_user(db: Session, claims: dict) -> User:
    subject = str(claims["sub"])
    email = str(claims.get("email", "")).strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise HTTPException(403, detail={"code": "email_unverified", "message": "Verify your email in Keycloak"})
    user = db.scalar(select(User).where(User.external_subject == subject))
    if user is None:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is not None and user.identity_type != IdentityType.human:
            raise HTTPException(409, detail={
                "code": "agent_identity_conflict",
                "message": "Agent identities cannot be linked to a human login",
            })
        if user is not None and user.external_subject not in (None, subject):
            raise HTTPException(409, detail={"code": "identity_conflict", "message": "Account is linked to another identity"})
        if user is None:
            user = User(
                email=email, display_name=str(claims.get("name") or email.split("@")[0])[:120],
                role=Role.reader, identity_type=IdentityType.human,
            )
            db.add(user)
        user.external_subject = subject
        db.flush()
    if user.disabled_at is not None:
        raise HTTPException(403, detail={"code": "account_disabled", "message": "Account is disabled"})
    return user


def finish_login(request: Request, code: str, state: str, db: Session) -> RedirectResponse:
    encrypted = request.cookies.get("km_oidc_flow", "")
    try:
        flow = json.loads(flow_cipher().decrypt(encrypted.encode(), ttl=600))
    except (InvalidToken, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(400, detail={"code": "invalid_login_flow", "message": "Login attempt expired"}) from error
    if not secrets.compare_digest(str(flow.get("state", "")), state):
        raise HTTPException(400, detail={"code": "invalid_state", "message": "Login state mismatch"})
    token_response = httpx.post(
        discovery()["token_endpoint"],
        data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": callback_uri(), "code_verifier": flow["verifier"],
        },
        auth=(settings.oidc_browser_client_id, settings.oidc_browser_client_secret),
        timeout=10,
    )
    if token_response.status_code != 200:
        raise HTTPException(401, detail={"code": "token_exchange_failed", "message": "Central login failed"})
    id_token = token_response.json().get("id_token")
    if not isinstance(id_token, str):
        raise HTTPException(401, detail={"code": "missing_id_token", "message": "Central login failed"})
    claims = verify_jwt(id_token, settings.oidc_browser_client_id, nonce=flow["nonce"])
    user = link_user(db, claims)
    raw_session = new_token()
    csrf = secrets.token_urlsafe(24)
    from datetime import datetime, timedelta, timezone
    db.add(BrowserSession(
        user_id=user.id, hashed_token=digest(raw_session), csrf_token=csrf,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    ))
    db.commit()
    response = RedirectResponse(settings.public_origin + flow["next"])
    response.delete_cookie("km_oidc_flow", path="/api/v1/auth/oidc")
    response.set_cookie(
        "km_session", raw_session, secure=settings.app_env == "production",
        httponly=True, samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/",
    )
    return response


def verify_mcp_access_token(token: str) -> dict:
    return verify_jwt(token, settings.oidc_mcp_audience)


def valid_legacy_mcp_token(token: str, db: Session) -> bool:
    from datetime import datetime, timezone
    from .models import AgentCredential

    credential = db.scalar(select(AgentCredential).where(
        AgentCredential.hashed_token == digest(token),
        AgentCredential.revoked_at.is_(None),
    ))
    return bool(
        credential
        and credential.user.disabled_at is None
        and (credential.expires_at is None or credential.expires_at > datetime.now(timezone.utc))
        and bool(set(credential.scopes).intersection({"knowledge:read", "knowledge:contribute"}))
    )


def mcp_challenge() -> Response:
    metadata = settings.public_origin + "/.well-known/oauth-protected-resource/mcp"
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": f'Bearer resource_metadata="{metadata}"'},
    )

import hashlib
import secrets
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import AgentCredential, BrowserSession, Role, User

hasher = PasswordHasher()


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    authorization = request.headers.get("authorization", "")
    now = datetime.now(timezone.utc)
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        credential = db.scalar(
            select(AgentCredential).where(
                AgentCredential.hashed_token == digest(token),
                AgentCredential.revoked_at.is_(None),
            )
        )
        if credential and (credential.expires_at is None or credential.expires_at > now):
            user = credential.user
            if user.disabled_at is None:
                request.state.scopes = set(credential.scopes)
                return user
    token = request.cookies.get("km_session")
    if token:
        session = db.scalar(
            select(BrowserSession).where(
                BrowserSession.hashed_token == digest(token),
                BrowserSession.revoked_at.is_(None),
                BrowserSession.expires_at > now,
            )
        )
        if session and session.user.disabled_at is None:
            request.state.browser_session = session
            request.state.scopes = set()
            return session.user
    return None


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, detail={"code": "authentication_required", "message": "Sign in required"})
    return user


ROLE_LEVEL = {Role.reader: 0, Role.contributor: 1, Role.editor: 2, Role.administrator: 3}


def require_role(minimum: Role):
    def dependency(user: User = Depends(current_user)) -> User:
        if ROLE_LEVEL[user.role] < ROLE_LEVEL[minimum]:
            raise HTTPException(403, detail={"code": "forbidden", "message": f"{minimum.value} role required"})
        return user

    return dependency


def verify_csrf(request: Request, user: User = Depends(current_user)) -> User:
    session = getattr(request.state, "browser_session", None)
    if session is not None:
        token = request.headers.get("x-csrf-token")
        if not token or not secrets.compare_digest(token, session.csrf_token):
            raise HTTPException(403, detail={"code": "csrf_failed", "message": "Missing or invalid CSRF token"})
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, detail={"code": "origin_rejected", "message": "Origin check failed"})
    return user


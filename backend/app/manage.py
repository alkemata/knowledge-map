import argparse
import getpass
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .auth import digest, hash_password
from .database import new_session
from .models import AgentCredential, IdentityType, Role, User


def create_admin() -> None:
    email = input("Administrator email: ").strip().lower()
    display_name = input("Public display name or pseudonym: ").strip()
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12 or password != confirmation:
        raise SystemExit("Passwords do not match or are too short")
    with new_session() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("A user with that email already exists")
        db.add(User(
            email=email, display_name=display_name, role=Role.administrator,
            identity_type=IdentityType.human, password_hash=hash_password(password),
        ))
        db.commit()
    print("Administrator created.")


def create_agent() -> None:
    email = input("Internal identifier/email: ").strip().lower()
    display_name = input("Public agent display name: ").strip()
    role_name = input("Role [contributor]: ").strip() or "contributor"
    if role_name not in {"reader", "contributor", "editor"}:
        raise SystemExit("Allowed agent roles: reader, contributor, editor")
    scope_text = input("Scopes [knowledge:read,knowledge:contribute]: ").strip() or "knowledge:read,knowledge:contribute"
    hours = int(input("Token lifetime hours [720]: ").strip() or "720")
    raw = "akm_" + secrets.token_urlsafe(36)
    with new_session() as db:
        user = User(
            email=email, display_name=display_name, role=Role(role_name),
            identity_type=IdentityType.agent,
        )
        db.add(user)
        db.flush()
        db.add(AgentCredential(
            user_id=user.id, hashed_token=digest(raw), prefix=raw[:12],
            scopes=[value.strip() for value in scope_text.split(",") if value.strip()],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        ))
        db.commit()
    print("Token (shown once):")
    print(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Alkemata Knowledge Map management")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create-admin")
    sub.add_parser("create-agent")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin()
    elif args.command == "create-agent":
        create_agent()


if __name__ == "__main__":
    main()


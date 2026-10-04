"""Grant or revoke a human map role after verifying a Keycloak identity."""

import os
import sys
from urllib.parse import urlencode

from sqlalchemy import func, select

sys.path.insert(0, "/srv/alkemata/auth/keycloak")
from bootstrap import DIRECTORY, REALM, admin_token, read_env, request

os.chdir("/srv/alkemata/knowledge-map")
sys.path.insert(0, "/srv/alkemata/knowledge-map/backend")
os.environ["DATABASE_URL"] = "postgresql+psycopg://knowledge@127.0.0.1:55432/knowledge"

from app.database import new_session  # noqa: E402
from app.models import IdentityType, Role, User  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in {"reader", "contributor", "editor"}:
        raise SystemExit("Usage: set-map-role.py EMAIL reader|contributor|editor")
    email = sys.argv[1].strip().lower()
    if not email or "@" not in email:
        raise SystemExit("Enter a valid email address")
    role = Role(sys.argv[2])
    token = admin_token(read_env(DIRECTORY / ".env"))
    users = request(f"/admin/realms/{REALM}/users?{urlencode({'email': email, 'exact': 'true'})}", token=token)
    matches = [user for user in users if user.get("email", "").lower() == email]
    if len(matches) != 1 or not matches[0].get("emailVerified") or not matches[0].get("enabled"):
        raise SystemExit("Exactly one enabled, email-verified Keycloak user is required")
    subject = matches[0]["id"]
    with new_session() as db:
        by_subject = db.scalar(select(User).where(User.external_subject == subject))
        by_email = db.scalar(select(User).where(func.lower(User.email) == email))
        if by_subject and by_email and by_subject.id != by_email.id:
            raise SystemExit("Map identity conflict; no change made")
        user = by_subject or by_email
        if user and (user.identity_type != IdentityType.human or user.external_subject not in (None, subject)):
            raise SystemExit("Map identity conflict; no change made")
        if user and user.role == Role.administrator:
            raise SystemExit("Administrator role cannot be changed with this command")
        if user is None:
            user = User(email=email, display_name=email.split("@")[0], identity_type=IdentityType.human)
            db.add(user)
        user.external_subject = subject
        user.role = role
        db.commit()
    print(f"{email}: {role.value}")


if __name__ == "__main__":
    main()

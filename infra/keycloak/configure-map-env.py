"""Set map OIDC environment without displaying secrets or changing other settings."""

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from bootstrap import read_env


MAP_ENV = Path("/srv/alkemata/knowledge-map/.env")
CLIENTS_ENV = Path("/srv/alkemata/auth/keycloak/clients.env")
BACKUP_ROOT = Path("/srv/alkemata/auth/map-backups")


def main() -> None:
    client_secret = read_env(CLIENTS_ENV)["MAP_BROWSER_CLIENT_SECRET"]
    updates = {
        "OIDC_ISSUER": "https://auth.alkemata.com/realms/alkemata",
        "OIDC_BROWSER_CLIENT_ID": "knowledge-map-browser",
        "OIDC_BROWSER_CLIENT_SECRET": client_secret,
        "OIDC_MCP_AUDIENCE": "https://map.alkemata.com/mcp",
        "OIDC_MCP_ENFORCE": "false",
    }
    original = MAP_ENV.read_text()
    lines = [line for line in original.splitlines() if line.split("=", 1)[0] not in updates]
    lines.extend(f"{key}={value}" for key, value in updates.items())
    output = "\n".join(lines) + "\n"
    if output == original:
        print("Map OIDC environment already configured")
        return
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_ROOT / f"map-env-before-oidc-{stamp}.txt"
    shutil.copyfile(MAP_ENV, backup)
    backup.chmod(0o600)
    previous_umask = os.umask(0o077)
    try:
        with tempfile.NamedTemporaryFile("w", dir=MAP_ENV.parent, delete=False) as temporary:
            temporary.write(output)
            staged = Path(temporary.name)
        staged.chmod(0o600)
        os.replace(staged, MAP_ENV)
    finally:
        os.umask(previous_umask)
    print("Map OIDC environment configured; previous file backed up with mode 600")


if __name__ == "__main__":
    main()

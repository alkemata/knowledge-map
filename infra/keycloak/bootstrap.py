"""Create the initial Keycloak OIDC clients without printing their secrets."""

import json
import os
import secrets
import urllib.parse
import urllib.request
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
BASE = "http://172.17.0.1:18081"
REALM = "alkemata"


def read_env(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    )


def request(path: str, method: str = "GET", data: dict | None = None, token: str = ""):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def admin_token(env: dict[str, str]) -> str:
    data = urllib.parse.urlencode({
        "client_id": "admin-cli",
        "grant_type": "password",
        "username": env["KEYCLOAK_ADMIN_USERNAME"],
        "password": env["KEYCLOAK_ADMIN_PASSWORD"],
    }).encode()
    req = urllib.request.Request(
        BASE + "/realms/master/protocol/openid-connect/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)["access_token"]


def load_client_secrets() -> dict[str, str]:
    path = DIRECTORY / "clients.env"
    if not path.exists():
        old_umask = os.umask(0o077)
        try:
            path.write_text(
                "MAP_BROWSER_CLIENT_SECRET=" + secrets.token_hex(32) + "\n"
                "WORDPRESS_CLIENT_SECRET=" + secrets.token_hex(32) + "\n"
            )
        finally:
            os.umask(old_umask)
    return read_env(path)


def create_client(token: str, client_id: str, definition: dict) -> None:
    query = urllib.parse.urlencode({"clientId": client_id})
    existing = request(f"/admin/realms/{REALM}/clients?{query}", token=token)
    if existing:
        print(f"Existing Keycloak client preserved: {client_id}")
        return
    request(f"/admin/realms/{REALM}/clients", "POST", definition, token)
    print(f"Created Keycloak client: {client_id}")


def main() -> None:
    env = read_env(DIRECTORY / ".env")
    secrets_map = load_client_secrets()
    token = admin_token(env)
    create_client(token, "knowledge-map-browser", {
        "clientId": "knowledge-map-browser",
        "name": "Alkemata Knowledge Map browser",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": secrets_map["MAP_BROWSER_CLIENT_SECRET"],
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "redirectUris": ["https://map.alkemata.com/api/v1/auth/oidc/callback"],
        "webOrigins": ["https://map.alkemata.com"],
    })
    create_client(token, "wordpress", {
        "clientId": "wordpress",
        "name": "Alkemata WordPress",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": secrets_map["WORDPRESS_CLIENT_SECRET"],
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "redirectUris": ["https://alkemata.com/openid-connect-authorize"],
        "webOrigins": ["https://alkemata.com"],
    })
    create_client(token, "knowledge-map-mcp", {
        "clientId": "knowledge-map-mcp",
        "name": "Alkemata Knowledge Map MCP resource",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": True,
        "standardFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "attributes": {"resource_url": "https://map.alkemata.com/mcp"},
    })
    print("Client secrets are stored only in clients.env (mode 600).")


if __name__ == "__main__":
    main()

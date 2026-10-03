"""Provision a confidential, read-only ChatGPT MCP OAuth client."""

import os
import secrets
from urllib.parse import urlencode

from bootstrap import DIRECTORY, admin_token, read_env, request

REALM = "alkemata"
RESOURCE = "https://map.alkemata.com/mcp"
CLIENT_ID = "alkemata-chatgpt-mcp"
SCOPE = "knowledge:read"


def get_by_name(token: str, collection: str, key: str, value: str) -> dict | None:
    items = request(f"/admin/realms/{REALM}/{collection}", token=token)
    return next((item for item in items if item.get(key) == value), None)


def ensure_secret() -> str:
    path = DIRECTORY / "clients.env"
    values = read_env(path)
    if "CHATGPT_MCP_CLIENT_SECRET" in values:
        return values["CHATGPT_MCP_CLIENT_SECRET"]
    new_secret = secrets.token_hex(32)
    old_umask = os.umask(0o077)
    try:
        with path.open("a") as handle:
            handle.write("CHATGPT_MCP_CLIENT_SECRET=" + new_secret + "\n")
        path.chmod(0o600)
    finally:
        os.umask(old_umask)
    return new_secret


def main() -> None:
    token = admin_token(read_env(DIRECTORY / ".env"))
    scope = get_by_name(token, "client-scopes", "name", SCOPE)
    if scope is None:
        request(f"/admin/realms/{REALM}/client-scopes", "POST", {
            "name": SCOPE,
            "description": "Read published Alkemata map content through MCP",
            "protocol": "openid-connect",
            "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "true"},
        }, token)
        scope = get_by_name(token, "client-scopes", "name", SCOPE)
        if scope is None:
            raise RuntimeError("Client scope creation was not visible")
        print("Created read-only MCP scope")
    scope_id = scope["id"]
    mappers = request(f"/admin/realms/{REALM}/client-scopes/{scope_id}/protocol-mappers/models", token=token)
    if not any(item.get("name") == "alkemata-mcp-audience" for item in mappers):
        request(f"/admin/realms/{REALM}/client-scopes/{scope_id}/protocol-mappers/models", "POST", {
            "name": "alkemata-mcp-audience",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {
                "included.custom.audience": RESOURCE,
                "access.token.claim": "true",
                "id.token.claim": "false",
            },
        }, token)
        print("Bound read scope to MCP token audience")
    client_query = urlencode({"clientId": CLIENT_ID})
    clients = request(f"/admin/realms/{REALM}/clients?{client_query}", token=token)
    if not clients:
        request(f"/admin/realms/{REALM}/clients", "POST", {
            "clientId": CLIENT_ID,
            "name": "Alkemata MCP in ChatGPT",
            "description": "Read-only OAuth client for ChatGPT MCP connection",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "clientAuthenticatorType": "client-secret",
            "secret": ensure_secret(),
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "redirectUris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
            "webOrigins": ["https://chatgpt.com"],
            "attributes": {"pkce.code.challenge.method": "S256"},
        }, token)
        clients = request(f"/admin/realms/{REALM}/clients?{client_query}", token=token)
        if not clients:
            raise RuntimeError("ChatGPT client creation was not visible")
        print("Created confidential ChatGPT MCP client")
    client_id = clients[0]["id"]
    attached = request(f"/admin/realms/{REALM}/clients/{client_id}/default-client-scopes", token=token)
    if not any(item.get("id") == scope_id for item in attached):
        request(f"/admin/realms/{REALM}/clients/{client_id}/default-client-scopes/{scope_id}", "PUT", token=token)
        print("Assigned read scope to ChatGPT client")
    print("Client ID:", CLIENT_ID)
    print("Client secret stored only in clients.env (mode 600)")


if __name__ == "__main__":
    main()

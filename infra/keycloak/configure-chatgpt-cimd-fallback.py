"""Register ChatGPT's stable CIMD URL as a fixed, JWT-authenticated client.

Keycloak 26.8 cannot parse ChatGPT's CIMD metadata. This narrowly scoped
pre-registration accepts connections that retained ChatGPT's stable client ID
before the realm switched to DCR. ChatGPT proves possession of its private key
at token exchange; no shared client secret is created.
"""

from urllib.parse import urlencode

from bootstrap import DIRECTORY, REALM, admin_token, read_env, request

CLIENT_ID = "https://chatgpt.com/oauth/client.json"
JWKS_URL = "https://chatgpt.com/oauth/jwks.json"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"


def main() -> None:
    token = admin_token(read_env(DIRECTORY / ".env"))
    query = urlencode({"clientId": CLIENT_ID})
    clients = request(f"/admin/realms/{REALM}/clients?{query}", token=token)
    if clients:
        client = clients[0]
        print("Existing ChatGPT metadata-URL client preserved")
    else:
        request(f"/admin/realms/{REALM}/clients", "POST", {
            "clientId": CLIENT_ID,
            "name": "ChatGPT MCP (stable metadata URL)",
            "description": "Compatibility for ChatGPT connections created before DCR",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "clientAuthenticatorType": "client-jwt",
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "consentRequired": True,
            "fullScopeAllowed": False,
            "redirectUris": [REDIRECT],
            "webOrigins": ["https://chatgpt.com"],
            "attributes": {
                "use.jwks.url": "true",
                "jwks.url": JWKS_URL,
                "token.endpoint.auth.signing.alg": "RS256",
                "pkce.code.challenge.method": "S256",
            },
        }, token)
        clients = request(f"/admin/realms/{REALM}/clients?{query}", token=token)
        if not clients:
            raise RuntimeError("ChatGPT URL client was not visible after creation")
        client = clients[0]
        print("Created JWT-authenticated ChatGPT metadata-URL client")

    scopes = request(f"/admin/realms/{REALM}/client-scopes", token=token)
    by_name = {scope["name"]: scope["id"] for scope in scopes}
    client_path = f"/admin/realms/{REALM}/clients/{client['id']}"
    default = request(client_path + "/default-client-scopes", token=token)
    if by_name["knowledge:read"] not in {item["id"] for item in default}:
        request(
            client_path + "/default-client-scopes/" + by_name["knowledge:read"],
            "PUT", token=token,
        )
    optional = request(client_path + "/optional-client-scopes", token=token)
    if by_name["knowledge:contribute"] not in {item["id"] for item in optional}:
        request(
            client_path + "/optional-client-scopes/" + by_name["knowledge:contribute"],
            "PUT", token=token,
        )
    print("Read and optional contribution scopes assigned")


if __name__ == "__main__":
    main()

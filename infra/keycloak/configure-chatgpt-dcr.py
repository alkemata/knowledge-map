"""Permit narrowly scoped anonymous DCR for ChatGPT MCP OAuth.

Keycloak 26.8 cannot parse ChatGPT's CIMD document. ChatGPT falls back to DCR
when CIMD is not advertised. The anonymous registration policy still limits
client URLs to chatgpt.com and caps the total number of realm clients.
"""

from bootstrap import DIRECTORY, REALM, admin_token, read_env, request

POLICY_TYPE = "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy"
SCOPES = ("knowledge:read", "knowledge:contribute")


def main() -> None:
    token = admin_token(read_env(DIRECTORY / ".env"))
    policies = request(f"/admin/realms/{REALM}/client-policies/policies", token=token)
    compatible = [
        item for item in policies.get("policies", [])
        if item.get("name") != "alkemata-chatgpt-cimd"
    ]
    if len(compatible) != len(policies.get("policies", [])):
        policies["policies"] = compatible
        request(f"/admin/realms/{REALM}/client-policies/policies", "PUT", policies, token)

    components = request(
        f"/admin/realms/{REALM}/components?type={POLICY_TYPE}", token=token
    )
    trusted = next(
        item for item in components
        if item.get("providerId") == "trusted-hosts"
        and item.get("subType") == "anonymous"
    )
    trusted["config"] = {
        **trusted.get("config", {}),
        "trusted-hosts": ["chatgpt.com"],
        "host-sending-registration-request-must-match": ["false"],
        "client-uris-must-match": ["true"],
    }
    request(f"/admin/realms/{REALM}/components/{trusted['id']}", "PUT", trusted, token)

    maximum = next(
        item for item in components
        if item.get("providerId") == "max-clients"
        and item.get("subType") == "anonymous"
    )
    maximum["config"] = {**maximum.get("config", {}), "max-clients": ["35"]}
    request(f"/admin/realms/{REALM}/components/{maximum['id']}", "PUT", maximum, token)

    allowed = next(
        item for item in components
        if item.get("providerId") == "allowed-client-templates"
        and item.get("subType") == "anonymous"
    )
    allowed["config"] = {
        **allowed.get("config", {}),
        "allowed-client-scopes": list(SCOPES),
        "allow-default-scopes": ["true"],
    }
    request(f"/admin/realms/{REALM}/components/{allowed['id']}", "PUT", allowed, token)

    optional = request(
        f"/admin/realms/{REALM}/default-optional-client-scopes", token=token
    )
    optional_names = {item["name"] for item in optional}
    scopes = request(f"/admin/realms/{REALM}/client-scopes", token=token)
    for name in SCOPES:
        if name not in optional_names:
            scope = next(item for item in scopes if item["name"] == name)
            request(
                f"/admin/realms/{REALM}/default-optional-client-scopes/{scope['id']}",
                "PUT", token=token,
            )
    print("ChatGPT DCR policy configured; no client secret displayed")


if __name__ == "__main__":
    main()

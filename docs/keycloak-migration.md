# Keycloak migration

## Deployment boundary

Keycloak runs at `https://auth.alkemata.com` behind the existing Traefik file
provider. Its PostgreSQL volume is separate from both WordPress and the map.
The HTTP listener is bound to the Docker bridge host address, not the public
interface. Keep `infra/keycloak/.env` out of Git and mode 600.

The operator deploys `infra/keycloak/compose.yaml` using the system Docker
daemon, then copies `infra/keycloak/traefik.yaml` to
`/srv/alkemata/traefik/custom/auth.yaml`. The file provider watches that
directory. Verify `https://auth.alkemata.com/realms/master/.well-known/openid-configuration`
before creating clients or switching application logins.

## Identity model

Use one `alkemata` realm and separate OIDC clients for WordPress, map browser
login, and the map MCP resource. Preserve WordPress user IDs, posts and roles.
Create or invite Keycloak users with verified email addresses matching their
WordPress accounts. Link the first OIDC login to the existing WordPress account
and retain its role. Keep WordPress's existing login available until a tested
administrator account has signed in through Keycloak.

Use the WordPress.org OpenID Connect Generic Client plugin with the following
settings during migration:

- Issuer: `https://auth.alkemata.com/realms/alkemata`
- Client ID: `wordpress`
- Scope: `openid profile email`
- Alternate redirect URI: enabled (`https://alkemata.com/openid-connect-authorize`)
- Link existing users: enabled, by email
- Create user if missing: disabled
- Login type: button, until a WordPress administrator has completed a round trip
- JWKS, authorization, token, userinfo and logout endpoints from the issuer's
  discovery document

Install `infra/keycloak/wordpress-verified-email.php` as a must-use plugin
before activating the OIDC client. It rejects unverified email claims and
prevents new WordPress accounts during the first migration. The generic plugin
stores the Keycloak subject in the existing WordPress user's metadata after
the first successful link.

The map already stores `external_subject` alongside its local user ID and role.
Link that subject on first OIDC login; do not infer a privileged role from an
unverified email address. MCP access tokens must have the map MCP resource as
their audience and be checked on every request. Preserve the current map agent
tokens until all existing clients have migrated.

## Rollback

Do not disable the current WordPress and map login routes until both OIDC paths
and account linking have been verified. If the new identity provider is
unavailable, remove only the new auth proxy route and return to the prior login
routes. Back up the Keycloak PostgreSQL volume and realm configuration before
upgrades.

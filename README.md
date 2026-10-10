# Alkemata Knowledge Map

Persistent illustrated knowledge landscape for people and AI agents.

Production endpoints:

- App: https://map.alkemata.com
- REST/OpenAPI: https://map.alkemata.com/api/v1 and /api/docs
- Registered MCP gateway: https://alkemata.com/wp-json/mcp/alkemata-public
- Direct map MCP endpoint: https://map.alkemata.com/mcp

Source is in /srv/alkemata/knowledge-map. The Compose project is
alkemata-knowledge-map and attaches to the existing traefik_web network.
WordPress remains separate.
The live Traefik route and registry manifest are tracked in
`deploy/traefik-userland.yaml` and `deploy/mcp-registry-server.json`.

## Deployment

Create a protected .env from .env.example, then run the following commands in
order: docker compose config --quiet; docker compose build; docker compose up -d
db; docker compose run --rm api alembic upgrade head; docker compose run --rm api
python -m app.manage create-admin; docker compose run --rm api python -m app.seed
--demo; docker compose up -d; scripts/smoke.sh https://map.alkemata.com.

The admin command prompts securely. The demo seed is idempotent and requires the
explicit --demo flag.

## Tests and conventions

Run pytest in backend. Run npm ci, npm run build and npm test in frontend.
Domain points use x/y; Leaflet receives y/x. Visibility is half open:
min_zoom <= zoom < max_zoom.

The world uses simple absolute coordinates from (0, 0) to (6144, 4096). Its
background is a 256-pixel WebP tile pyramid with native zoom levels -4 through
0. Leaflet loads only visible tiles and reuses zoom-0 tiles for closer levels.
The source illustration is assets/source/knowledge-map-landscape.png.

Rebuild the pyramid with:

python scripts/build_map_tiles.py assets/source/knowledge-map-landscape.png
frontend/public/map-tiles --width 6144 --height 4096 --min-zoom -4 --max-zoom 0

The generated metadata is frontend/public/map-tiles/metadata.json.

## MCP

Connect any Streamable HTTP MCP client to the registered gateway at
`https://alkemata.com/wp-json/mcp/alkemata-public`. Published map and WordPress
content is public: no account, token, or client registration is
needed for read tools. In ChatGPT, add a custom MCP connector with that URL and
choose no authentication for public reading. Other MCP clients use the same URL.

For personal map contributions, use OAuth with the same URL. The server advertises
`https://auth.alkemata.com/realms/alkemata` through its OAuth protected-resource
metadata. The registered ChatGPT client is `alkemata-chatgpt-mcp`; its secret is
stored on the server in `/srv/alkemata/auth/keycloak/clients.env` (mode 600).
An administrator can enter that client ID and secret in the connector's OAuth
setup, request `openid profile email offline_access knowledge:read knowledge:contribute`, and
sign in with an individual Keycloak account. Only grant the optional
`knowledge:contribute` scope to people who need to create topics. The map also
checks that person's map role: `contributor` creates drafts, while `editor`
can publish. Without the contribution scope and role, write calls are rejected.
To require sign-in for all MCP tools, set `OIDC_MCP_ENFORCE=true` in the
protected map `.env` and restart the API. Set it to `false` for public reads
with authenticated writes (the current deployment).

To approve a person, create or verify their Keycloak account, then run
`/srv/alkemata/knowledge-map/runtime/venv/bin/python /srv/alkemata/knowledge-map/scripts/set-map-role.py EMAIL contributor` on the
server. Use `editor` only for someone authorized to publish. Revoke access by
setting the role to `reader` or disabling the Keycloak account. A client for
another LLM host can be registered in Keycloak with authorization code + PKCE,
the host's exact redirect URI, the `knowledge:read` default scope, and optional
`knowledge:contribute` scope. Keep client secrets out of the LLM prompt.

The gateway exposes the four original `alkemata-*` public WordPress MCP tools
for site info, published post/page search, published content and guidance. It
also exposes map topics, regions and trails, plus `search_articles`,
`get_article`, `list_map_categories`, and the protected `add_map_content` and
`create_topic_at_position` tools. The original
WordPress tools are called through WordPress MCP, so its tool activity remains
recorded there. The newer article tools read the public WordPress REST API.
WordPress remains the content source; nothing is copied into the map database.
Private WordPress administration tools are not exposed by this gateway.

### Topic categories and map editing

For normal content creation, call `list_map_categories` and then
`add_map_content(title, summary, content, category_name)`; omit `category_name`
for a top-level topic. A category is another topic, linked by a published
`broader_than` relationship. A topic has one active parent category per map.
The server chooses an unused position near the parent, or near the map's
default center for a top-level topic. It assigns visibility at zoom -4 for
top-level topics, -2 for their children, 0 for grandchildren, then 2 and 3.5
for deeper levels. Top-level category labels are visible on the map. The
older `create_topic_at_position` tool remains available for precise manual
placement.

Editor/administrator MCP creations publish immediately by default; contributor
creations remain drafts until an editor publishes them. A draft never appears
in the public map viewport. The result includes `status`, `published`,
`placement`, and `visible_from_zoom` so clients can explain where to look.
The map refreshes when moved, focused, or after 30 seconds while visible.

Only administrators can switch on Edit map in the browser. In edit mode,
drag a circle anywhere within the map bounds to move it, or open a topic to
change its category or archive it. Dragging across legacy region boundaries
updates the topic's region automatically. Every visible circle has a label;
deeper topics and their labels appear as the map is zoomed in.
Changing a category repositions the topic and recalculates visibility for its
descendants. A category with children cannot be archived until its children
are moved or removed. Server endpoints enforce administrator role and CSRF,
not just the browser switch.

create_topic_at_position accepts a title, summary, paragraph content, map ID,
x/y position, min_zoom, max_zoom, label priority, optional region, language and
icon. It creates the topic revision and placement together. It requires an
Authorization: Bearer token belonging to an agent with knowledge:contribute
scope. Contributor agents create drafts for review. Editor agents may set
publish=true to publish immediately. Use an idempotency_key when retrying a
request.

Generate scoped tokens with python -m app.manage create-agent. Tokens are shown
once and only their SHA-256 digest is stored.

## Backup

After loading .env, use scripts/backup.sh with an explicit protected destination.
Use scripts/restore.sh with an explicit isolated database. The restore script
refuses the production database name. Configure encrypted off-server transfer;
a local backup alone does not protect against server loss.

# Alkemata Knowledge Map

Persistent illustrated knowledge landscape for people and AI agents.

Production endpoints:

- App: https://map.alkemata.com
- REST/OpenAPI: https://map.alkemata.com/api/v1 and /api/docs
- MCP Streamable HTTP: https://map.alkemata.com/mcp

Source is in /srv/alkemata/knowledge-map. The Compose project is
alkemata-knowledge-map and attaches to the existing traefik_web network.
WordPress remains separate.

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

MCP exposes get_app_info, get_agent_guidance, search_topics, get_topic,
get_region, get_trail and create_topic_at_position. Read tools return only
published content.

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

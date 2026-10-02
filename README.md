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

MCP exposes get_app_info, get_agent_guidance, search_topics, get_topic,
get_region and get_trail. Only published content is returned. Authenticated MCP
writes remain disabled until OAuth inputs and a target client are confirmed.

## Backup

After loading .env, use scripts/backup.sh with an explicit protected destination.
Use scripts/restore.sh with an explicit isolated database. The restore script
refuses the production database name. Configure encrypted off-server transfer;
a local backup alone does not protect against server loss.

# Handover - 2 October 2026

Delivered: React/Leaflet CRS.Simple map; FastAPI API; PostgreSQL models and
Alembic migration; published-revision isolation; roles, sessions and CSRF;
versioned placements; idempotence records; vector regions/layers/features;
relationships and branching trails; 30 original labelled demo topics; official
MCP SDK v2 read server; Compose, health, backup, restore and smoke scripts.

Deployment facts:

- origin https://map.alkemata.com
- MCP https://map.alkemata.com/mcp
- source /srv/alkemata/knowledge-map
- data volumes alkemata_knowledge_map_db and alkemata_knowledge_map_assets
- existing Traefik via traefik_web; WordPress unchanged

Known limitations:

- Stage B is not complete. MCP writes and OAuth are disabled. OAuth issuer,
  audience, JWKS and target-client requirements are missing.
- Source uses /srv rather than root-owned /opt, matching existing Alkemata apps.
- Terrain create APIs and placement movement exist, but full visual handles,
  background replacement, unsaved undo and every update/archive operation remain.
- Rich inline marks, asset promotion/download policy, invitation/review screens,
  cursor pagination, database full-text search, shared rate limiting and portable
  import/export preview remain.
- The 1,000-placement benchmark and full accessibility audit remain.
- Backup artifacts are local until an encrypted off-server target is supplied.
- The shared legacy Traefik 2.2 installation was preserved, not upgraded.

Never use docker compose down -v. Before upgrades, run a backup and restore it to
an isolated database. An incompatible rollback requires coordinated database and
asset restore, not only an old image.

Create an administrator with python -m app.manage create-admin inside the api
service. Create scoped agent credentials with python -m app.manage create-agent;
the token is displayed once and stored only as a hash.

Complete the editor UI, invitation and review UI, performance test, off-server
restore drill and OAuth-backed MCP contribution flow before claiming full Stage A
or Stage B conformance.

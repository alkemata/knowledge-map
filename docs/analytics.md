# Alkemata usage dashboard

The administrator-only dashboard is at
`https://map.alkemata.com/api/v1/analytics/dashboard`. Its JSON version is
`https://map.alkemata.com/api/v1/analytics?days=7` (1–90 days). Sign in with a
map administrator account. No anonymous statistics endpoint is available.

## Collection

- The central MCP gateway records tool names, transport status, latency,
  coarse client family, and whether a request supplied credentials. It does
  not store tool arguments, prompts, responses, IP addresses, or raw tokens.
- The map API records route templates, HTTP status and latency. The map
  frontend reports `map_open`, `topic_open`, and `search_open` events without
  identifiers or search text.
- Authorized AI clients can report an AI call using
  `POST /api/v1/analytics/ai-event` with an agent bearer token belonging to a
  contributor, editor, or administrator. The JSON body is:

  ```json
  {
    "model_name": "example-model",
    "operation": "model_call",
    "outcome": "success",
    "input_tokens": 100,
    "output_tokens": 50,
    "latency_ms": 1200
  }
  ```

  `operation` can be `model_call` or `agent_run`; `outcome` can be `success`
  or `error`. Do not include prompt or response content. These figures are
  self-reported by the client, and ChatGPT does not automatically provide them
  to an MCP server.
- WordPress site visits and top published content come from the existing WP
  Statistics plugin through a dedicated read-only bridge. The dashboard fetches
  aggregates directly; it does not copy visitor records, IPs, or referrers.

The WordPress bridge is installed as
`wp-content/mu-plugins/alkemata-private-statistics.php`. Its
`/wp-json/alkemata-analytics/v1/summary` route requires a dedicated bearer
token. WordPress stores only its SHA-256 hash in the
`alkemata_analytics_token_hash` option; the map service reads the token from
its private `.env` file. The route returns only daily totals and top published
post/page counts. Anonymous and invalid-token requests return 403.

## Interpretation and next integrations

`transport_ok` means HTTP succeeded. Some MCP tool failures are carried inside
HTTP 200 responses, so it is not a count of successful tool execution. Public
clients' user agents can be absent or inaccurate. The dashboard counts events,
not unique people.

WordPress MCP calls routed through the gateway appear as MCP tool events; site
visits come from WP Statistics. The existing Easy MCP AI statistics concern
that plugin's own endpoint. Other apps can use the AI event contract for
model calls; product actions need their own event adapter.

Back up the database before schema migrations. Usage data resides in the
`usage_events` table. The dashboard queries only the selected date range and
does not expose individual events.

#!/bin/sh
set -eu
origin=${1:-https://map.alkemata.com}
curl -fsS "$origin/api/v1/health/live"
curl -fsS "$origin/api/v1/health/ready"
curl -fsS "$origin/api/v1/capabilities"
curl -fsS "$origin/api/v1/maps"
curl -fsS -X POST "$origin/mcp" +  -H 'Content-Type: application/json' +  -H 'Accept: application/json, text/event-stream' +  -H 'Mcp-Protocol-Version: 2025-11-25' +  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'
printf '\nSmoke checks passed.\n'

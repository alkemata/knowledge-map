#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
set -a
. "$root/.env"
set +a
export DATABASE_URL="postgresql+psycopg://knowledge@127.0.0.1:55432/knowledge"
export ASSET_ROOT="$root/runtime/assets"
export LD_LIBRARY_PATH="$root/runtime/postgres/usr/lib/x86_64-linux-gnu"
exec "$root/runtime/venv/bin/uvicorn" app.main:app --app-dir "$root/backend" \
  --host 172.17.0.1 --port 18000 --proxy-headers --forwarded-allow-ips=172.16.0.0/12

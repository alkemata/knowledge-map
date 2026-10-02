#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
runtime="$root/runtime"
pgbin="$runtime/postgres/usr/lib/postgresql/17/bin"
export LD_LIBRARY_PATH="$runtime/postgres/usr/lib/x86_64-linux-gnu"
export PATH="$pgbin:$runtime/venv/bin:$PATH"
mkdir -p "$runtime/logs" "$runtime/pids" "$runtime/assets" "$runtime/pgsocket"

if ! "$pgbin/pg_isready" -h 127.0.0.1 -p 55432 -q; then
  nohup "$pgbin/postgres" -D "$runtime/pgdata" -h 127.0.0.1 -p 55432 -k "$runtime/pgsocket" >"$runtime/logs/postgres.log" 2>&1 &
  echo $! > "$runtime/pids/postgres.pid"
fi

set -a
. "$root/.env"
set +a
export DATABASE_URL="postgresql+psycopg://knowledge@127.0.0.1:55432/knowledge"
export ASSET_ROOT="$runtime/assets"

if ! curl -fsS http://172.17.0.1:18000/api/v1/health/live >/dev/null 2>&1; then
  nohup "$runtime/venv/bin/uvicorn" app.main:app --app-dir "$root/backend" --host 172.17.0.1 --port 18000 --proxy-headers --forwarded-allow-ips=172.16.0.0/12 >"$runtime/logs/api.log" 2>&1 &
  echo $! > "$runtime/pids/api.pid"
fi

if ! curl -fsS http://172.17.0.1:18080/health >/dev/null 2>&1; then
  nohup /usr/bin/python3 "$root/scripts/serve_frontend.py" >"$runtime/logs/web.log" 2>&1 &
  echo $! > "$runtime/pids/web.pid"
fi
sleep 3
curl -fsS http://172.17.0.1:18000/api/v1/health/ready
curl -fsS http://172.17.0.1:18080/

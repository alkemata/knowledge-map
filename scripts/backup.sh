#!/bin/sh
set -eu
umask 077
project_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
root=${1:-}
if [ -z "$root" ]; then
  echo "Usage: scripts/backup.sh /protected/backup/destination" >&2
  exit 2
fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="$root/$stamp"
mkdir -p "$destination"

pgbin="$project_root/runtime/postgres/usr/lib/postgresql/17/bin"
if [ -x "$pgbin/pg_dump" ]; then
  set -a
  . "$project_root/.env"
  set +a
  export LD_LIBRARY_PATH="$project_root/runtime/postgres/usr/lib/x86_64-linux-gnu"
  "$pgbin/pg_dump" -Fc -h 127.0.0.1 -p "${POSTGRES_PORT:-55432}" \
    -U "${POSTGRES_USER:-knowledge}" "${POSTGRES_DB:-knowledge}" \
    > "$destination/database.dump"
  tar -C "$project_root/runtime/assets" -czf "$destination/assets.tar.gz" .
  printf '{"runtime":"userland-postgresql","port":%s}\n' "${POSTGRES_PORT:-55432}" \
    > "$destination/images.json"
else
  cd "$project_root"
  docker compose exec -T db pg_dump -Fc -U "${POSTGRES_USER:-knowledge}" \
    "${POSTGRES_DB:-knowledge}" > "$destination/database.dump"
  docker run --rm -v alkemata_knowledge_map_assets:/source:ro \
    -v "$destination":/backup alpine:3.23.3 \
    tar -C /source -czf /backup/assets.tar.gz .
  docker compose images --format json > "$destination/images.json"
fi

git -C "$project_root" rev-parse HEAD > "$destination/revision.txt"
(cd "$destination" && sha256sum database.dump assets.tar.gz > SHA256SUMS)
echo "$destination"

#!/bin/sh
set -eu
umask 077
root=${1:-}
if [ -z "$root" ]; then
  echo "Usage: scripts/backup.sh /protected/backup/destination" >&2
  exit 2
fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="$root/$stamp"
mkdir -p "$destination"
docker compose exec -T db pg_dump -Fc -U "${POSTGRES_USER:-knowledge}" "${POSTGRES_DB:-knowledge}" > "$destination/database.dump"
docker run --rm -v alkemata_knowledge_map_assets:/source:ro -v "$destination":/backup alpine:3.23.3 +  tar -C /source -czf /backup/assets.tar.gz .
git rev-parse HEAD > "$destination/revision.txt"
docker compose images --format json > "$destination/images.json"
sha256sum "$destination/database.dump" "$destination/assets.tar.gz" > "$destination/SHA256SUMS"
echo "$destination"

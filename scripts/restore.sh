#!/bin/sh
set -eu
backup=${1:-}
destination_db=${2:-}
if [ -z "$backup" ] || [ -z "$destination_db" ]; then
  echo "Usage: scripts/restore.sh BACKUP_DIRECTORY DESTINATION_DATABASE" >&2
  echo "The destination must be an isolated database, never production." >&2
  exit 2
fi
case "$destination_db" in
  knowledge) echo "Refusing to restore over the production database." >&2; exit 3 ;;
esac
test -f "$backup/database.dump"
test -f "$backup/assets.tar.gz"
(cd "$backup" && sha256sum -c SHA256SUMS)
docker compose exec -T db createdb -U "${POSTGRES_USER:-knowledge}" "$destination_db" 2>/dev/null || true
docker compose exec -T db pg_restore --clean --if-exists --no-owner -U "${POSTGRES_USER:-knowledge}" -d "$destination_db" < "$backup/database.dump"
echo "Database restored to isolated destination: $destination_db"
echo "Asset archive verified but not applied to the production volume."

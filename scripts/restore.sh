#!/bin/sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
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

pgbin="$project_root/runtime/postgres/usr/lib/postgresql/17/bin"
if [ -x "$pgbin/pg_restore" ]; then
  set -a
  . "$project_root/.env"
  set +a
  export LD_LIBRARY_PATH="$project_root/runtime/postgres/usr/lib/x86_64-linux-gnu"
  "$pgbin/createdb" -h 127.0.0.1 -p "${POSTGRES_PORT:-55432}" \
    -U "${POSTGRES_ADMIN_USER:-rdi}" -O "${POSTGRES_USER:-knowledge}" \
    "$destination_db" 2>/dev/null || true
  "$pgbin/pg_restore" --clean --if-exists --no-owner \
    -h 127.0.0.1 -p "${POSTGRES_PORT:-55432}" \
    -U "${POSTGRES_USER:-knowledge}" -d "$destination_db" \
    < "$backup/database.dump"
else
  cd "$project_root"
  docker compose exec -T db createdb -U "${POSTGRES_USER:-knowledge}" \
    "$destination_db" 2>/dev/null || true
  docker compose exec -T db pg_restore --clean --if-exists --no-owner \
    -U "${POSTGRES_USER:-knowledge}" -d "$destination_db" \
    < "$backup/database.dump"
fi
echo "Database restored to isolated destination: $destination_db"
echo "Asset archive verified but not applied to the production volume."

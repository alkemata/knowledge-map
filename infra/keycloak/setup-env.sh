#!/bin/sh
set -eu

deployment_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
target="$deployment_dir/.env"
if [ -e "$target" ]; then
  echo "Existing .env preserved: $target"
  exit 0
fi
umask 077
db_password=$(openssl rand -hex 32)
admin_password=$(openssl rand -hex 32)
printf 'KEYCLOAK_DB_PASSWORD=%s\nKEYCLOAK_ADMIN_USERNAME=bootstrap-admin\nKEYCLOAK_ADMIN_PASSWORD=%s\n' \
  "$db_password" "$admin_password" >"$target"
echo "Generated protected Keycloak credentials at $target"
echo "Read the bootstrap admin password from this file in your own terminal."

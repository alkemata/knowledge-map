#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
for name in web api postgres; do
  file="$root/runtime/pids/$name.pid"
  if [ -f "$file" ]; then
    pid=$(cat "$file")
    kill "$pid" 2>/dev/null || true
    rm -f "$file"
  fi
done

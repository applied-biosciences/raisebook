#!/usr/bin/env bash
# Stop the local Wasila started by deploy/local/start.sh (and anything else on its ports).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RUN="$HERE/run"
WEB_PORT="${WEB_PORT:-3600}"
API_PORT="${API_PORT:-8000}"
QUIET="${1:-}"

for name in web api mock-claude; do
  f="$RUN/$name.pid"
  if [ -f "$f" ]; then
    pid="$(cat "$f")"
    kill "$pid" 2>/dev/null || true
    rm -f "$f"
  fi
done

# Whatever still holds the ports (the dev windows, an old run).
for port in "$WEB_PORT" "$API_PORT" 8788; do
  pids="$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null || true
done
sleep 1

[ "$QUIET" = "--quiet" ] || echo "Wasila stopped."

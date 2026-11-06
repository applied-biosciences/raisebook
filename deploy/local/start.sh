#!/usr/bin/env bash
# Wasila on this computer, production style: the web app is a production build
# (next build + next start) and the API runs without auto-reload.
#
#   ./deploy/local/start.sh          start (or restart) everything
#   ./deploy/local/stop.sh           stop it
#
# Web  http://localhost:3600     API  http://localhost:8000
# Running it again rebuilds and restarts (use it after git pull).
#
# Safe for testing:
# - Sign-in links are shown on screen (no email is sent).
# - Outreach "Send" is recorded in Wasila but no email leaves this computer.
#   REAL_EMAIL=1 ./deploy/local/start.sh uses the SMTP settings you save in Settings → Email.
# - Claude uses the Anthropic key you save in Settings → Claude.
#   MOCK_CLAUDE=1 ./deploy/local/start.sh uses a local fake Claude instead (no cost).
#
# Nothing here deploys anywhere. Data stays in your local Postgres (database wasila_dev).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/deploy/local"
LOGS="$HERE/logs"
RUN="$HERE/run"
mkdir -p "$LOGS" "$RUN"

WEB_PORT="${WEB_PORT:-3600}"
API_PORT="${API_PORT:-8000}"
DB_NAME="${DB_NAME:-wasila_dev}"
API_URL="http://localhost:$API_PORT"
WEB_URL="http://localhost:$WEB_PORT"

say() { printf '\033[1;34m▸ %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is not installed. $2"; }
need uv "Install it with: brew install uv"
need npm "Install Node 20+ with: brew install node"
need pg_isready "Install Postgres with: brew install postgresql@16 && brew services start postgresql@16"

# 1. Postgres
say "Checking Postgres"
if ! pg_isready -q; then
  if command -v brew >/dev/null 2>&1; then
    brew services start postgresql@16 >/dev/null 2>&1 || brew services start postgresql >/dev/null 2>&1 || true
    sleep 3
  fi
  pg_isready -q || fail "Postgres is not running. Start it with: brew services start postgresql@16"
fi
psql -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$DB_NAME" || { say "Creating database $DB_NAME"; createdb "$DB_NAME"; }

# 2. A local encryption key for saved secrets (Claude key, SMTP password). Created once,
#    kept in deploy/local/.env.local (git-ignored). Losing it means re-entering those secrets.
ENV_FILE="$HERE/.env.local"
if [ ! -f "$ENV_FILE" ]; then
  say "Creating a local encryption key (deploy/local/.env.local)"
  (cd "$ROOT/backend" && uv sync -q)
  KEK="$(cd "$ROOT/backend" && uv run -q wasilactl secrets gen-kek | tail -1)"
  umask 077
  printf "WASILA_SECRETS_KEK='%s'\n" "$KEK" > "$ENV_FILE"
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

# 3. Stop anything already on the two ports (an earlier run or the dev windows).
"$HERE/stop.sh" --quiet || true

export WASILA_ENV=dev
export WASILA_DATABASE_URL="postgresql://localhost/$DB_NAME"
export WASILA_PUBLIC_BASE_URL="$API_URL"
export WASILA_APP_URL="$WEB_URL"
export WASILA_SESSION_COOKIE_SECURE=false
export WASILA_EMAIL_BACKEND=log
if [ "${REAL_EMAIL:-0}" = "1" ]; then
  export WASILA_OUTREACH_BACKEND=smtp
else
  export WASILA_OUTREACH_BACKEND=memory
fi

# 4. Optional fake Claude
if [ "${MOCK_CLAUDE:-0}" = "1" ]; then
  say "Starting the local fake Claude on :8788"
  (cd "$ROOT/backend" && nohup uv run python scripts/mock_anthropic.py --port 8788 </dev/null >"$LOGS/mock-claude.log" 2>&1 & echo $! >"$RUN/mock-claude.pid")
  export WASILA_ANTHROPIC_BASE_URL="http://localhost:8788"
fi

# 5. API: dependencies, migrations, server
say "Preparing the API (uv sync, migrations)"
cd "$ROOT/backend"
uv sync -q
uv run -q alembic upgrade head >"$LOGS/migrate.log" 2>&1 || { tail -20 "$LOGS/migrate.log"; fail "Migrations failed (log above)"; }
say "Starting the API on :$API_PORT"
nohup uv run uvicorn --factory wasila.main:create_app --host 127.0.0.1 --port "$API_PORT" \
  </dev/null >"$LOGS/api.log" 2>&1 &
echo $! >"$RUN/api.pid"

# 6. Web: production build, then serve it
cd "$ROOT/web"
if [ ! -d node_modules ] || [ package-lock.json -nt node_modules ]; then
  say "Installing web packages (npm ci)"
  npm ci --no-audit --no-fund >"$LOGS/npm-ci.log" 2>&1 || { tail -20 "$LOGS/npm-ci.log"; fail "npm ci failed (log above)"; }
fi
say "Building the web app (a minute or two)"
NEXT_PUBLIC_API_URL="$API_URL" NEXT_PUBLIC_SITE_URL="$WEB_URL" NEXT_TELEMETRY_DISABLED=1 \
  npm run build >"$LOGS/build.log" 2>&1 || { tail -30 "$LOGS/build.log"; fail "Web build failed (log above)"; }
# The same layout as the Docker image (deploy/web.Dockerfile): the standalone server with
# its static files and public/ beside it.
rm -rf .next/standalone/.next/static .next/standalone/public
cp -R .next/static .next/standalone/.next/static
cp -R public .next/standalone/public
say "Starting the web app on :$WEB_PORT"
(cd .next/standalone && PORT="$WEB_PORT" HOSTNAME=127.0.0.1 NEXT_TELEMETRY_DISABLED=1 \
  nohup node server.js </dev/null >"$LOGS/web.log" 2>&1 & echo $! >"$RUN/web.pid")

# 7. Wait until both answer
say "Waiting for both to answer"
for _ in $(seq 1 60); do
  if curl -fsS "$API_URL/healthz" >/dev/null 2>&1 && curl -fsS -o /dev/null "$WEB_URL/signin" 2>/dev/null; then
    printf '\n\033[1;32m✓ Wasila v1.0.0.0 is running\033[0m\n'
    echo "  Open:  $WEB_URL/signin"
    echo "  Logs:  deploy/local/logs/ (api.log, web.log)"
    echo "  Stop:  ./deploy/local/stop.sh"
    [ "${WASILA_OUTREACH_BACKEND}" = "memory" ] && echo "  Email: test mode (sends are recorded, nothing is emailed)"
    [ "$(uname)" = "Darwin" ] && open "$WEB_URL/signin" || true
    exit 0
  fi
  sleep 1
done
echo "--- api.log ---"; tail -20 "$LOGS/api.log" || true
echo "--- web.log ---"; tail -20 "$LOGS/web.log" || true
fail "Wasila did not start within 60 seconds (logs above)"

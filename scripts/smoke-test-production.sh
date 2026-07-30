#!/usr/bin/env bash

set -euo pipefail

APP_URL="${APP_URL:-}"

if [ -z "$APP_URL" ]; then
  echo "Usage:"
  echo "APP_URL=https://copilot.example.com $0"
  exit 1
fi

APP_URL="${APP_URL%/}"

echo "Testing frontend: $APP_URL"

curl \
  --fail \
  --silent \
  --show-error \
  --location \
  --max-time 20 \
  "$APP_URL/" \
  >/dev/null

echo "✅ Frontend is reachable"

echo "Testing API health: $APP_URL/api/health"

HEALTH_PAYLOAD="$(
  curl \
    --fail \
    --silent \
    --show-error \
    --max-time 20 \
    "$APP_URL/api/health"
)"

printf '%s\n' "$HEALTH_PAYLOAD"

python - "$HEALTH_PAYLOAD" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])

if payload.get("status") != "ok":
    raise SystemExit(
        f"Unexpected health status: {payload!r}"
    )

print("✅ API health response verified")
PY

echo "Testing database health: $APP_URL/api/health/database"

curl \
  --fail \
  --silent \
  --show-error \
  --max-time 20 \
  "$APP_URL/api/health/database"

echo
echo "✅ Production smoke test passed"

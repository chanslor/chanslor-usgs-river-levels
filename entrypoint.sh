#!/usr/bin/env bash
set -euo pipefail

# Allow overrides via env
: "${CONFIG_PATH:=/app/gauges.conf.json}"
: "${RUN_INTERVAL_SEC:=600}"           # every 10 minutes
: "${BIND_HOST:=0.0.0.0}"
: "${BIND_PORT:=8080}"

echo "[usgs] starting… (interval=${RUN_INTERVAL_SEC}s)"

/usr/bin/python3 --version || true

# Create a placeholder index.html so HTTP server can start immediately
mkdir -p /site
echo '<!DOCTYPE html><html><head><title>Loading...</title></head><body><h1>River Monitor Starting...</h1><p>Please wait while initial data loads (may take 30-60 seconds)...</p></body></html>' > /site/index.html
echo '{"loading": true}' > /site/gauges.json

# First run immediately to produce the site
echo "[usgs] Running initial data fetch..."
/usr/bin/python3 /app/usgs_multi_alert.py \
  --config "${CONFIG_PATH}" \
  --cfs \
  --dump-json /site/gauges.json \
  --dump-html /site/index.html \
  --trend-hours 8 || echo "[usgs] initial run failed (will retry in background loop)"

# Background loop to refresh every N seconds
(
  while true; do
    sleep "${RUN_INTERVAL_SEC}"
    /usr/bin/python3 /app/usgs_multi_alert.py \
      --config "${CONFIG_PATH}" \
      --cfs \
      --dump-json /site/gauges.json \
      --dump-html /site/index.html \
      --trend-hours 8 || echo "[usgs] periodic run failed"
  done
) &

# Serve /site on 8080 (simple, fast, no deps)
cd /site
echo "[usgs] Starting HTTP server on ${BIND_HOST}:${BIND_PORT}"
ls -la /site/
exec /usr/bin/python3 -m http.server "${BIND_PORT}" --bind "${BIND_HOST}"


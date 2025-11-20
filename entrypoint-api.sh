#!/usr/bin/env bash
set -euo pipefail

# Allow overrides via env
: "${CONFIG_PATH:=/app/gauges.conf.json}"
: "${RUN_INTERVAL_SEC:=60}"            # every 1 minute
: "${BIND_HOST:=0.0.0.0}"
: "${BIND_PORT:=8080}"

echo "[usgs-api] starting with API server… (interval=${RUN_INTERVAL_SEC}s)"

/usr/bin/python3 --version || true

# Create directories and placeholder files
mkdir -p /site
echo '<!DOCTYPE html><html><head><title>Loading...</title></head><body><h1>River Monitor Starting...</h1><p>Please wait while initial data loads (may take 30-60 seconds)...</p></body></html>' > /site/index.html
echo '{"loading": true}' > /site/gauges.json

# First run immediately to produce the site
echo "[usgs-api] Running initial data fetch..."
/usr/bin/python3 /app/usgs_multi_alert.py \
  --config "${CONFIG_PATH}" \
  --cfs \
  --dump-json /site/gauges.json \
  --dump-html /site/index.html \
  --trend-hours 8 || echo "[usgs-api] initial run failed (will retry in background loop)"

# Background loop to refresh every N seconds
(
  while true; do
    sleep "${RUN_INTERVAL_SEC}"
    echo "[usgs-api] Refreshing river data..."
    /usr/bin/python3 /app/usgs_multi_alert.py \
      --config "${CONFIG_PATH}" \
      --cfs \
      --dump-json /site/gauges.json \
      --dump-html /site/index.html \
      --trend-hours 8 || echo "[usgs-api] periodic run failed"
  done
) &

# Start Flask API server on port 8080
cd /app
echo "[usgs-api] Starting Flask API server on ${BIND_HOST}:${BIND_PORT}"
echo "[usgs-api] API endpoints available at:"
echo "  - GET /api/health"
echo "  - GET /api/river-levels"
echo "  - GET /api/river-levels/{site_id}"
echo "  - GET /api/river-levels/name/{name}"
echo ""
echo "[usgs-api] Example for Little River Canyon:"
echo "  curl http://localhost:${BIND_PORT}/api/river-levels/02399200"
echo ""

exec /usr/bin/python3 /app/api_app.py

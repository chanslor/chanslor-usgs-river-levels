# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

USGS Multi-Site River Gauge Alert System — Monitors USGS river gauges and sends email alerts when water levels exceed configurable thresholds. Generates live HTML dashboard with river levels, CFS (cubic feet per second), and trend indicators. Integrates NWS Quantitative Precipitation Forecast (QPF) data with SQLite caching.

## Container Build & Run

Build the container:
```bash
# Build with version tag
VER=usgs-alert:$(date +%Y%m%d%H%M)
podman build -t "$VER" -t usgs-alert:latest .

# Or simple build
podman build -t usgs-alert:3.3 .
```

Run the container:
```bash
# Remove existing container if present
podman rm -f usgs-alert 2>/dev/null || true

# Run with all mounts and environment variables
podman run -d --name usgs-alert \
  --pull=never \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  -v "$(pwd)/gauges.conf.json":/app/gauges.conf.json:ro,Z \
  -e RUN_INTERVAL_SEC=600 \
  -e NWS_UA="mdchansl-usgs-alert/1.0" \
  -e NWS_CONTACT="michael.chanslor@gmail.com" \
  -e QPF_TTL_HOURS="3" \
  -e QPF_CACHE="/data/qpf_cache.sqlite" \
  localhost/usgs-alert:latest
```

View logs:
```bash
podman logs -f usgs-alert
```

Access the dashboard:
```
http://localhost:8080
```

## Development Commands

Run the main script directly (for development):
```bash
# Basic run with CFS data
python3 usgs_multi_alert.py --config gauges.conf.json --cfs

# Generate public site files with 8-hour trend analysis
python3 usgs_multi_alert.py --config gauges.conf.json --cfs \
  --dump-json public/gauges.json \
  --dump-html public/index.html \
  --trend-hours 8
```

Test QPF functionality:
```bash
# Fetch QPF data for a specific location
python3 qpf.py --lat 34.0522 --lon -86.2437 --days 3 \
  --ua "mdchansl-usgs-alert/1.0" \
  --email "michael.chanslor@gmail.com"
```

Verify generated files:
```bash
# Check that site files exist
ls -l "$(pwd)/usgs-site"/{index.html,gauges.json}

# Verify QPF cache was created
ls -l "$(pwd)/usgs-data/qpf_cache.sqlite"

# Check JSON contains QPF section
jq '.rows[0].qpf // empty' "$(pwd)/usgs-site/gauges.json"

# Verify HTML includes rainfall data
grep -i 'Rain:' "$(pwd)/usgs-site/index.html" | head
```

## Architecture

### Core Components

1. **usgs_multi_alert.py** — Main monitoring script
   - Fetches USGS instantaneous value (IV) data for multiple river gauges
   - Evaluates per-site thresholds (min_ft and/or min_cfs — both must pass for "IN" status)
   - Manages alert state in SQLite (`/data/state.sqlite`) with cooldown logic
   - Sends email alerts via SMTP for rising/falling water levels
   - Generates JSON feed (`gauges.json`) and static HTML dashboard (`index.html`)
   - Supports site ID normalization (e.g., "Foo (USGS 03572690)" → "03572690")

2. **qpf.py** — NWS Quantitative Precipitation Forecast integration
   - Fetches QPF data from `api.weather.gov` using lat/lon coordinates
   - Parses ISO 8601 validTime intervals (e.g., "2025-10-28T12:00:00+00:00/PT6H")
   - Apportions precipitation across local calendar days in local timezone
   - Converts from millimeters to inches
   - Implements SQLite cache with configurable TTL (default 3 hours)
   - NWS API requires proper User-Agent with contact info

3. **entrypoint.sh** — Container orchestration
   - Runs initial gauge check immediately on startup
   - Launches background loop to refresh data every `RUN_INTERVAL_SEC` (default 600s)
   - Serves static site files via Python's built-in HTTP server on port 8080

4. **gauges.conf.json** — Configuration file
   - SMTP settings for email alerts (server, port, credentials)
   - Site definitions with USGS site IDs and custom thresholds
   - Alert behavior: `notify.mode` ("rising" or "any"), cooldown periods
   - State persistence path (`state_db`)

### Data Flow

```
USGS IV API → usgs_multi_alert.py → SQLite state + email alerts
                       ↓
                 gauges.json + index.html (in /site)
                       ↓
              Python HTTP server (port 8080)

NWS API → qpf.py → SQLite cache → QPF data merged into gauge data
```

### Key Patterns

- **Site ID normalization**: All USGS site identifiers go through `normalize_site_id()` to extract numeric IDs from free-form strings
- **Dual threshold logic**: Sites can specify `min_ft` and/or `min_cfs`; both conditions must pass for "IN" status
- **State persistence**: SQLite stores last alert times, water levels, and in/out status per site to prevent alert spam
- **Trend calculation**: `fetch_trend_label()` requests historical data over N hours to classify river stage as rising/falling/steady
- **Alert modes**:
  - `rising`: Alert only on OUT→IN transitions (default behavior)
  - `any`: Alert whenever thresholds are met (regardless of previous state)
- **Out alerts**: Optional `send_out` sends notification when levels drop below thresholds

### Environment Variables

- `CONFIG_PATH`: Path to gauges.conf.json (default: /app/gauges.conf.json)
- `RUN_INTERVAL_SEC`: Seconds between data refreshes (default: 600)
- `BIND_HOST` / `BIND_PORT`: HTTP server binding (default: 0.0.0.0:8080)
- `NWS_UA`: User-Agent for NWS API (required for qpf.py)
- `NWS_CONTACT`: Contact email for NWS API (required for qpf.py)
- `QPF_TTL_HOURS`: Cache TTL for QPF data (default: 3)
- `QPF_CACHE`: Path to QPF SQLite cache (default: /data/qpf_cache.sqlite)

### File Locations (in container)

- `/app/`: Application code (usgs_multi_alert.py, qpf.py, entrypoint.sh, gauges.conf.json)
- `/data/`: Persistent state (state.sqlite, qpf_cache.sqlite) — bind mount required
- `/site/`: Generated output (index.html, gauges.json) — bind mount required

## Configuration Notes

The `gauges.conf.json` file contains sensitive credentials (SMTP password visible in current version). When modifying:
- Update the mounted config: `$(pwd)/gauges.conf.json:/app/gauges.conf.json:ro,Z`
- Stop/remove container, then run again to pick up changes
- Consider using environment variables for secrets instead of config file

Per-site configuration supports:
- `site`: USGS site ID (can include text like "River Name (USGS 12345678)")
- `name`: Display name for alerts and dashboard
- `include_discharge`: Whether to fetch CFS data (00060 parameter)
- `min_ft`: Minimum stage in feet (can be null)
- `min_cfs`: Minimum discharge in CFS (can be null)

## Systemd Integration

Enable auto-start on boot using Podman Quadlet:
```bash
mkdir -p ~/.config/containers/systemd
# Create usgs-alert.container file in that directory

systemctl --user daemon-reload
systemctl --user enable --now usgs-alert.service
loginctl enable-linger "$USER"
```

Verify service status:
```bash
systemctl --user status usgs-alert.service --no-pager
```

## Git Repository State

Current version is working as of 10-29-2025 (see working.10-29-2025.png).

Backup files exist in backups/ directory. Several experimental/patched versions present:
- usgs_multi_alert.py.BACKUP, .b4, .b4-patch, .claude-fix
- qpf_trend.patch

These should not be committed to production branches.

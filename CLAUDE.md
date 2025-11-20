# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

USGS Multi-Site River Gauge Alert System — Monitors USGS river gauges and sends email alerts when water levels exceed configurable thresholds. Generates live HTML dashboard with river levels, CFS (cubic feet per second), and trend indicators. Integrates NWS Quantitative Precipitation Forecast (QPF) data with SQLite caching. Includes Flask REST API for ESP32/IoT device integration.

**Production URL**: https://docker-blue-sound-1751.fly.dev/
- **Dashboard**: https://docker-blue-sound-1751.fly.dev/ (main sparkly UI)
- **API Info**: https://docker-blue-sound-1751.fly.dev/api (API documentation)
- **ESP32 API**: https://docker-blue-sound-1751.fly.dev/api/river-levels/{site_id}

## Container Build & Run

### Current Production Build (Flask API + Dashboard)

Build the container:
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker

# Build with current production Containerfile
podman build -f Containerfile.api.simple -t usgs-api:latest .
```

Run the container locally:
```bash
# Remove existing container if present
podman rm -f usgs-api 2>/dev/null || true

# Run with all mounts and environment variables
podman run -d --name usgs-api \
  --pull=never \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  -e RUN_INTERVAL_SEC=60 \
  -e NWS_UA="mdchansl-usgs-alert/1.0" \
  -e NWS_CONTACT="michael.chanslor@gmail.com" \
  -e QPF_TTL_HOURS="3" \
  -e QPF_CACHE="/data/qpf_cache.sqlite" \
  localhost/usgs-api:latest
```

View logs:
```bash
podman logs -f usgs-api
```

Access locally:
```
Dashboard: http://localhost:8080/
API Info:  http://localhost:8080/api
ESP32 API: http://localhost:8080/api/river-levels/02399200
```

### Deploy to Fly.io

```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy --local-only
```

The `fly.toml` is configured to use `Containerfile.api.simple` with persistent storage mounted at `/data`.

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

1. **api_app.py** — Flask REST API server
   - Serves HTML dashboard at `/` (main page)
   - Serves API documentation at `/api`
   - Provides REST endpoints at `/api/river-levels/*`
   - Formats data for ESP32 OLED displays (5-line format)
   - Reads from cached `gauges.json` for fast responses
   - Supports CORS for web applications
   - Serves detail pages at `/details/{site_id}.html`

2. **usgs_multi_alert.py** — Main monitoring script
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

3. **observations.py** — Weather observations integration
   - Fetches current weather conditions from NWS API
   - Retrieves temperature, wind speed, and other meteorological data
   - Uses station IDs to get location-specific observations
   - Integrates with dashboard to show weather alerts

4. **site_detail.py** — Site detail page generator
   - Creates individual detail pages for each gauge
   - Generates 7-day historical charts using Chart.js
   - Provides detailed historical data and trend analysis
   - Linked from main dashboard for deep-dive analysis

5. **entrypoint-api.sh** — Container orchestration (PRODUCTION)
   - Runs initial gauge check immediately on startup
   - Launches background loop to refresh data every `RUN_INTERVAL_SEC` (default 60s)
   - Starts Flask API server on port 8080
   - Serves both HTML dashboard (/) and API endpoints (/api/*)

   **entrypoint.sh** — Simple HTTP server (LEGACY)
   - Basic Python HTTP server for static file serving
   - No API endpoints, dashboard only
   - Use entrypoint-api.sh for production deployments

6. **gauges.conf.json** — Configuration file
   - SMTP settings for email alerts (server, port, credentials)
   - Site definitions with USGS site IDs and custom thresholds
   - Alert behavior: `notify.mode` ("rising" or "any"), cooldown periods
   - State persistence path (`state_db`)

7. **test_visual_indicators.py** — Test suite generator
   - Generates comprehensive test HTML for all visual indicators
   - Tests all 6 Little River Canyon color zones with 22 test cases
   - Validates temperature alerts (10 cases: 35-85°F)
   - Validates wind alerts (8 cases: 0-30 mph)
   - Creates standalone HTML test file with color legend
   - Run with: `python3 test_visual_indicators.py`

### Data Flow

```
┌────────────────────────────────────────────────────────────┐
│  External APIs                                             │
│  - USGS Instantaneous Values API                          │
│  - NWS Quantitative Precipitation Forecast (QPF)          │
│  - NWS Observations API                                    │
│  - StreamBeam API                                          │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  Background Worker (usgs_multi_alert.py)                   │
│  - Runs every 60 seconds                                   │
│  - Fetches + processes data                                │
│  - Updates SQLite state DB                                 │
│  - Sends email alerts (on threshold changes)               │
│  - Generates output files:                                 │
│    • gauges.json (API data source)                         │
│    • index.html (main dashboard)                           │
│    • site_*.html (detail pages)                            │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  Flask API Server (api_app.py) - Port 8080                 │
│  - GET / → index.html (sparkly dashboard)                  │
│  - GET /api → API documentation                            │
│  - GET /api/health → health check                          │
│  - GET /api/river-levels → all rivers JSON                 │
│  - GET /api/river-levels/{site_id} → single river          │
│  - GET /api/river-levels/name/{name} → search by name      │
│  - GET /gauges.json → raw data feed                        │
│  - GET /details/{site}.html → detail pages                 │
└────────────────────────────────────────────────────────────┘
                         ↓
            ┌────────────┴────────────┐
            ↓                         ↓
    ┌──────────────┐          ┌──────────────┐
    │ Web Browsers │          │ ESP32 Devices│
    │ (Dashboard)  │          │ (API Client) │
    └──────────────┘          └──────────────┘
```

**Key Features:**
- Background worker and Flask server run concurrently in single container
- Flask reads from pre-generated JSON (no external API calls on every request)
- Fast response times (~10ms for API endpoints)
- Persistent SQLite state prevents duplicate alerts
- QPF data cached with 3-hour TTL

### Key Patterns

- **Site ID normalization**: All USGS site identifiers go through `normalize_site_id()` to extract numeric IDs from free-form strings
- **Dual threshold logic**: Sites can specify `min_ft` and/or `min_cfs`; both conditions must pass for "IN" status
- **State persistence**: SQLite stores last alert times, water levels, and in/out status per site to prevent alert spam
- **Trend calculation**: `fetch_trend_label()` requests historical data over N hours to classify river stage as rising/falling/steady
- **Alert modes**:
  - `rising`: Alert only on OUT→IN transitions (default behavior)
  - `any`: Alert whenever thresholds are met (regardless of previous state)
- **Out alerts**: Optional `send_out` sends notification when levels drop below thresholds

## REST API Endpoints

The Flask API provides the following endpoints:

### Web Interface
- **`GET /`** - Main HTML dashboard with sparkles, color-coded rivers, charts
- **`GET /details/{site_id}.html`** - Individual river detail page with 7-day history
- **`GET /gauges.json`** - Raw JSON data feed

### API Documentation
- **`GET /api`** - API information and endpoint listing

### Data Endpoints (for ESP32/IoT)
- **`GET /api/health`** - Health check, returns `{"status": "ok", "timestamp": "..."}`
- **`GET /api/river-levels`** - All monitored rivers with formatted data
- **`GET /api/river-levels/{site_id}`** - Single river by USGS site ID (e.g., 02399200)
- **`GET /api/river-levels/name/{name}`** - Single river by name search (case-insensitive)

### ESP32 Response Format

Each river data endpoint returns a `display_lines` array optimized for ESP32 OLED displays (5 lines):

```json
{
  "site_id": "02399200",
  "name": "Little River Canyon",
  "flow": "22 cfs",
  "trend": "-> steady",
  "stage_ft": 0.74,
  "qpf": {
    "today": 0.00,
    "tomorrow": 0.00,
    "day3": 0.18
  },
  "weather": {
    "temp_f": 60,
    "wind_mph": 0.0,
    "wind_dir": "N"
  },
  "timestamp": "2025-11-19T19:30:00Z",
  "in_range": false,
  "display_lines": [
    "Little River Canyon",
    "22 cfs -> steady",
    "QPF Today: 0.00\"",
    "Tom:0.00\" Day3:0.18\"",
    "Max:60F Wind:0.0 N"
  ]
}
```

See `API_README.md` for detailed API documentation and ESP32 integration examples.

### Environment Variables

- `CONFIG_PATH`: Path to gauges.conf.json (default: /app/gauges.conf.json)
- `RUN_INTERVAL_SEC`: Seconds between data refreshes (default: 60)
- `BIND_HOST` / `BIND_PORT`: HTTP server binding (default: 0.0.0.0:8080)
- `SITE_DIR`: Path to site files directory (default: /site)
- `PORT`: Flask server port (default: 8080)
- `NWS_UA`: User-Agent for NWS API (required for qpf.py and observations.py)
- `NWS_CONTACT`: Contact email for NWS API (required for qpf.py and observations.py)
- `QPF_TTL_HOURS`: Cache TTL for QPF data (default: 3)
- `QPF_CACHE`: Path to QPF SQLite cache (default: /data/qpf_cache.sqlite)

### File Locations (in container)

- `/app/`: Application code
  - `usgs_multi_alert.py` - Main monitoring script
  - `qpf.py` - QPF weather forecast integration
  - `observations.py` - Current weather observations
  - `site_detail.py` - Detail page generator
  - `entrypoint.sh` - Container startup script
  - `gauges.conf.json` - Configuration file
- `/data/`: Persistent state (bind mount required)
  - `state.sqlite` - Alert state database
  - `qpf_cache.sqlite` - QPF cache database
- `/site/`: Generated output (bind mount required)
  - `index.html` - Main dashboard
  - `gauges.json` - JSON data feed
  - `test_visual_indicators.html` - Test suite
  - `site_*.html` - Individual gauge detail pages

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

**Current Production Status**: Working as of 11-19-2025

**Production Deployment:**
- URL: https://docker-blue-sound-1751.fly.dev/
- Containerfile: `Containerfile.api.simple`
- Entrypoint: `entrypoint-api.sh`
- Features: Flask API + Dashboard + ESP32 endpoints

**Recent Updates:**
- Added Flask REST API (`api_app.py`) for ESP32/IoT integration
- Created dual-service architecture (background worker + API server)
- Migrated from Python HTTP server to Flask
- Added API documentation at `/api` endpoint
- Dashboard moved from root API to root HTML serving

**Configuration Files:**
- `fly.toml` - Fly.io deployment config (uses Containerfile.api.simple)
- `gauges.conf.cloud.json` - Production configuration with site definitions
- `gauges.conf.json` - Local development configuration

**Documentation:**
- `CLAUDE.md` - This file (project overview and guidance)
- `API_README.md` - REST API documentation and ESP32 examples
- `CONTAINERFILES.md` - Complete guide to all Containerfiles
- `README.md` - General project information
- `VALIDATOR_README.md` - Dashboard validation tool documentation

**Backup Files:**
Backup files exist in backups/ directory. Several experimental/patched versions present:
- usgs_multi_alert.py.BACKUP, .b4, .b4-patch, .claude-fix
- qpf_trend.patch

These should not be committed to production branches.

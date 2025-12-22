# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Directory

**Always use this directory for all commands:**
```
/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
```

When running bash commands, use absolute paths or `cd` to this directory first.

## Project Overview

USGS Multi-Site River Gauge Alert System — Monitors USGS river gauges and sends email alerts when water levels exceed configurable thresholds. Generates live HTML dashboard with river levels, CFS (cubic feet per second), and trend indicators. Integrates NWS Quantitative Precipitation Forecast (QPF) data with SQLite caching. Includes Flask REST API for ESP32/IoT device integration.

**Production URL**: https://docker-blue-sound-1751.fly.dev/
- **Dashboard**: https://docker-blue-sound-1751.fly.dev/ (main sparkly UI)
- **API Info**: https://docker-blue-sound-1751.fly.dev/api (API documentation)
- **ESP32 API**: https://docker-blue-sound-1751.fly.dev/api/river-levels/{site_id}

## Short Creek StreamBeam Calibration Status (2025-11-26)

**Current Status**: Calibrated with offset `22.39`

### Configuration:
- **Offset Setting**: `streambeam_zero_offset: 22.39`
- **Floor Setting**: `streambeam_floor_at_zero: false` (allows negative values for debugging)
- **StreamBeam Site ID**: 1
- **Gauge Location**: Short Creek near Hustleville Road

### Reference Links:
- StreamBeam Gauge: https://www.streambeam.net/Home/Gauge?siteID=1
- Production API: https://docker-blue-sound-1751.fly.dev/api/river-levels/name/short

### To Recalibrate (if needed):
1. **Go on-site** with staff gauge or known reference point
2. **Record both values**:
   - What StreamBeam website shows: X.XX ft
   - What actual staff gauge/reference shows: Y.YY ft
3. **Calculate offset**: `streambeam_zero_offset = X.XX - Y.YY`
4. **Update both config files**:
   - `gauges.conf.json` (local dev)
   - `gauges.conf.cloud.json` (production)
5. **Deploy**: `fly deploy -a docker-blue-sound-1751 --local-only`

## Container Build & Run

### Containerfile Setup

`Containerfile` is a symbolic link to `Containerfile.api.simple` (the production Flask API + Dashboard build). This means `podman build .` uses the correct production configuration by default.

### Current Production Build (Flask API + Dashboard)

Build the container:
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker

# Build using default Containerfile (symlink to Containerfile.api.simple)
podman build -t usgs-api:latest .
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

The `fly.toml` is configured to use `Containerfile.api.simple` (same as the default `Containerfile` symlink) with persistent storage mounted at `/data`.

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

3. **observations.py** — NWS Weather observations (fallback)
   - Fetches current weather conditions from NWS API (official airport stations)
   - Retrieves temperature, wind speed, and other meteorological data
   - Uses airport station IDs (KCMD, KBFZ, K4A9, etc.)
   - Used as fallback when PWS stations are unavailable

4. **pws_observations.py** — Personal Weather Station observations (primary)
   - Fetches weather from Weather Underground Personal Weather Stations
   - Uses embedded public API key (no account required)
   - More local/hyperlocal data than airport stations
   - Supports fallback chains: tries 4 PWS stations per river in order
   - PWS station mapping from GPS.txt:
     - Locust Fork: KALBLOUN24, KALBLOUN23, KALHANCE17, KALONEON42
     - Short Creek: KALGUNTE26, KALALBER97, KALALBER66, KALALBER69
     - Town Creek: KALFYFFE7, KALFYFFE11, KALALBER111, KALGROVE15
     - South Sauty: KALLANGS7, KALGROVE15, KALFYFFE11, KALRAINS14
     - Little River Canyon: KALCEDAR14, KALGAYLE19, KALGAYLE16, KALGAYLE7
     - Mulberry Fork: KALHAYDE19, KALHAYDE21, KALHAYDE13, KALWARRI54
     - Hiwassee Dries: KNCMURPH4, KTNBENTO3, KTNCLEVE20
     - Ocoee #3 (Upper): KTNBENTO3, KNCMURPH4, KTNCLEVE20
     - Ocoee #2 (Middle): KTNBENTO3, KNCMURPH4, KTNCLEVE20
     - Ocoee #1 (Lower): KTNBENTO3, KTNCLEVE20, KNCMURPH4
     - Rush South: KGACOLUM39, KGACOLUM96, KGAPHENI5, KGACOLUM50

5. **tva_fetch.py** — TVA Dam Data Fetcher (NEW - 2025-12-18, Updated 2025-12-22)
   - Fetches observed data from TVA REST API for dam monitoring
   - Used for sites like Apalachia Dam (Hiwassee Dries) that don't have USGS gauges
   - API endpoint: `https://www.tva.com/RestApi/observed-data/{SITE_CODE}.json`
   - Returns discharge (CFS), pool elevation, tailwater elevation
   - No authentication required
   - Supports trend calculation from recent observations
   - Generates 3-day forecast panel and historical chart for detail pages
   - **Tailwater Trend Detection** (NEW - 2025-12-22):
     - `get_tva_tailwater_trend()` calculates if tailwater is rising/falling/steady
     - Rising tailwater indicates water pouring over dam spillway
     - Key indicator for kayakers that river is running
     - Displays as "💧 tailwater ↗ +X.Xft" on dashboard
     - Included in email alerts when tailwater is rising
   - Site codes: HADT1, OCAT1, OCBT1, OCCT1

6. **tva_history.py** — TVA Historical Data Storage (NEW - 2025-12-19)
   - SQLite database module for indefinite storage of TVA dam observations
   - Stores discharge (CFS), pool elevation, and tailwater elevation
   - Auto-deduplication using unique constraint on site_code + timestamp
   - Functions: `init_database()`, `save_observations_batch()`, `get_observations()`, `get_stats()`, `get_date_range()`
   - Database location: `/data/tva_history.sqlite`
   - Data is preserved across deployments and accumulates over time

7. **site_detail.py** — Site detail page generator
   - Creates individual detail pages for each gauge
   - Generates 7-day historical charts using Chart.js
   - Provides detailed historical data and trend analysis
   - Linked from main dashboard for deep-dive analysis

8. **drought.py** — US Drought Monitor integration
   - Fetches county-level drought status from USDM REST API
   - API endpoint: `https://usdmdataservices.unl.edu/api/CountyStatistics/GetDroughtSeverityStatisticsByArea`
   - Uses FIPS county codes (configured per river in gauges.conf.json)
   - SQLite caching with configurable TTL (default 12 hours)
   - Only applies to Alabama rivers (Tellico River in TN excluded)
   - Drought levels and colors:
     | Level | Description | Color | Hex |
     |-------|-------------|-------|-----|
     | D0 | Abnormally Dry | Orange | `#e89b3c` |
     | D1 | Moderate Drought | Tan | `#fcd37f` |
     | D2 | Severe Drought | Dark Orange | `#ffaa00` |
     | D3 | Extreme Drought | Red | `#e60000` |
     | D4 | Exceptional Drought | Dark Red | `#730000` |
   - Cache is stored at `/data/drought_cache.sqlite`
   - To force refresh: delete cache file and restart container

9. **entrypoint-api.sh** — Container orchestration (PRODUCTION)
   - Runs initial gauge check immediately on startup
   - Launches background loop to refresh data every `RUN_INTERVAL_SEC` (default 60s)
   - Starts Flask API server on port 8080
   - Serves both HTML dashboard (/) and API endpoints (/api/*)

   **entrypoint.sh** — Simple HTTP server (LEGACY)
   - Basic Python HTTP server for static file serving
   - No API endpoints, dashboard only
   - Use entrypoint-api.sh for production deployments

10. **gauges.conf.json** — Configuration file
   - SMTP settings for email alerts (server, port, credentials)
   - Site definitions with USGS site IDs and custom thresholds
   - FIPS county codes for drought monitoring (Alabama rivers only)
   - Alert behavior: `notify.mode` ("rising" or "any"), cooldown periods
   - State persistence path (`state_db`)

11. **test_visual_indicators.py** — Test suite generator
   - Generates comprehensive test HTML for all visual indicators
   - Tests all 6 Little River Canyon color zones with 22 test cases
   - Validates temperature alerts (10 cases: 35-85°F)
   - Validates wind alerts (8 cases: 0-30 mph)
   - Creates standalone HTML test file with color legend
   - Run with: `python3 test_visual_indicators.py`

12. **predictions.py** — River Predictions Module (NEW - 2025-11-30)
   - Calculates likelihood of rivers reaching runnable levels
   - Uses QPF (rainfall forecast) + historical response patterns
   - Based on 90-day analysis of USGS gauge data
   - Generates HTML panel showing predictions with:
     - Likelihood percentage (0-100%)
     - Rain needed vs forecast comparison
     - Estimated peak timing window
   - API endpoint: `/api/predictions`

### River Predictions Feature

The dashboard includes a **River Predictions** panel that forecasts which rivers are likely to run based on:

1. **QPF Forecast** - NWS Quantitative Precipitation Forecast (72-hour rainfall)
2. **Historical Response Times** - How long each river takes to rise after rain (24-36 hours typical)
3. **Rain-to-Runnable Correlation** - How much rain each river needs to reach threshold

![River Predictions Panel](new-predictive.png)

**Prediction Status Colors:**
| Status | Color | Likelihood |
|--------|-------|------------|
| 🟢 Likely | Green | 70%+ |
| 🟡 Possible | Yellow | 40-69% |
| 🟠 Unlikely | Orange | 15-39% |
| 🔴 Very Unlikely | Gray | <15% |
| ✅ Running Now | Green | 100% |

**River Response Characteristics (from config):**

| River | Avg Response | Rain Needed | Responsiveness |
|-------|--------------|-------------|----------------|
| Short Creek | 12 hours | 0.65" | Fast |
| Town Creek | 32 hours | 1.25" | Moderate |
| Tellico River | 24 hours | 1.50" | Moderate |
| Little River Canyon | 33 hours | 1.75" | Moderate |
| Locust Fork | 33 hours | 1.75" | Moderate |
| South Sauty | 33 hours | 2.00" | Slow |
| Mulberry Fork | 33 hours | 2.25" | Slow |

### Data Flow

```
┌────────────────────────────────────────────────────────────┐
│  External APIs                                             │
│  - USGS Instantaneous Values API                          │
│  - NWS Quantitative Precipitation Forecast (QPF)          │
│  - Weather Underground PWS API (primary weather)          │
│  - NWS Observations API (fallback weather)                │
│  - StreamBeam API (Short Creek gauge)                     │
│  - TVA REST API (Hiwassee Dries / Apalachia Dam)          │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  Background Worker (usgs_multi_alert.py)                   │
│  - Runs every 60 seconds                                   │
│  - Fetches + processes data                                │
│  - Updates SQLite state DB                                 │
│  - Saves TVA observations to tva_history.sqlite            │
│  - Sends email alerts (on threshold changes)               │
│  - Generates output files:                                 │
│    • gauges.json (API data source)                         │
│    • index.html (main dashboard)                           │
│    • site_*.html (detail pages)                            │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  Flask API Server (api_app.py) - Port 8080                 │
│  - GET / → index.html (sparkly dashboard + predictions)    │
│  - GET /api → API documentation                            │
│  - GET /api/health → health check                          │
│  - GET /api/river-levels → all rivers JSON                 │
│  - GET /api/river-levels/{site_id} → single river          │
│  - GET /api/river-levels/name/{name} → search by name      │
│  - GET /api/predictions → river predictions JSON           │
│  - GET /api/tva-history/{site} → TVA historical data       │
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
- **`GET /api/predictions`** - River predictions based on QPF and historical patterns

### TVA Historical Data Endpoints (NEW - 2025-12-19)
- **`GET /api/tva-history/{site_code}?days=7`** - Get historical TVA observations
  - Query param `days`: Number of days of history (1-365, default: 7)
  - Returns: observations array, stats, date range
- **`GET /api/tva-history/{site_code}/stats?days=30`** - Get statistics only
  - Returns: min/max/avg for discharge, pool, tailwater

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
- `DROUGHT_TTL_HOURS`: Cache TTL for drought data (default: 12)
- `DROUGHT_CACHE`: Path to drought SQLite cache (default: /data/drought_cache.sqlite)

### File Locations (in container)

- `/app/`: Application code
  - `usgs_multi_alert.py` - Main monitoring script
  - `qpf.py` - QPF weather forecast integration
  - `observations.py` - NWS weather observations (fallback)
  - `pws_observations.py` - PWS weather observations (primary)
  - `drought.py` - US Drought Monitor integration
  - `tva_fetch.py` - TVA dam data fetcher (Hiwassee Dries)
  - `tva_history.py` - TVA historical data storage module
  - `site_detail.py` - Detail page generator
  - `predictions.py` - River predictions module
  - `api_app.py` - Flask REST API server
  - `entrypoint-api.sh` - Container startup script
  - `gauges.conf.json` - Configuration file
- `/data/`: Persistent state (bind mount required)
  - `state.sqlite` - Alert state database
  - `qpf_cache.sqlite` - QPF cache database
  - `drought_cache.sqlite` - Drought monitor cache database
  - `tva_history.sqlite` - TVA historical observations (indefinite storage)
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
- `min_ft`: Minimum stage in feet for "IN" status (can be null)
- `min_cfs`: Minimum discharge in CFS for "IN" status (can be null)
- `good_ft`: Stage threshold for "GOOD" status - ideal conditions (can be null)
- `good_cfs`: CFS threshold for "GOOD" status - ideal conditions (can be null)
- `fips`: 5-digit county FIPS code for drought monitoring (Alabama rivers only, omit for TN)

### County FIPS Codes for Drought Monitoring

| River | County | FIPS |
|-------|--------|------|
| Mulberry Fork | Blount County, AL | 01009 |
| Locust Fork | Blount County, AL | 01009 |
| Town Creek | DeKalb County, AL | 01049 |
| South Sauty | Marshall County, AL | 01095 |
| Little River Canyon | DeKalb County, AL | 01049 |
| Short Creek | Marshall County, AL | 01095 |
| Rush South | Muscogee County, GA | 13215 |
| Tellico River | Monroe County, TN | (not configured - TN excluded) |

### Dashboard Color Coding

Rivers are color-coded based on their thresholds:

| Status | Condition | Color | Hex |
|--------|-----------|-------|-----|
| **OUT** | Below min threshold | Gray | `#f6f7f9` |
| **IN** | At/above min, below good | Yellow | `#fff9c4` |
| **GOOD** | At/above good threshold | Light Green | `#c8e6c9` |

**Exception:** Little River Canyon uses a special 6-level classification based on expert paddler knowledge (Adam Goshorn):

| CFS Range | Status | Color |
|-----------|--------|-------|
| < 250 | Not runnable | Gray |
| 250-400 | Good low | Yellow |
| 400-800 | Shitty medium | Brown |
| 800-1,500 | Good medium | Light Green |
| 1,500-2,500 | Good high (BEST!) | Green |
| 2,500+ | Too high | Red |

### Tailwater Trend Indicators (TVA Dam Sites Only)

TVA dam sites display tailwater trend when water is pouring over the dam spillway:

| Indicator | Meaning | Color | Hex |
|-----------|---------|-------|-----|
| 💧 tailwater ↗ +X.Xft | Tailwater rising (water over dam!) | Bright Blue | `#38bdf8` |
| 💧 tailwater ↘ -X.Xft | Tailwater falling | Muted Gray | `#94a3b8` |
| (not shown) | Tailwater steady | - | - |

**Why This Matters for Kayakers:**
- Rising tailwater = water pouring over the dam spillway
- This is the key indicator that the river section below the dam is running
- Example: At Ocoee #1 (Parksville Dam), when release exceeds ~1,300 CFS, tailwater rises ~1 ft as water spills over
- The tailwater indicator appears on the main dashboard next to the discharge trend

### Current River Thresholds

| River | min | good | Data Source |
|-------|-----|------|-------------|
| Mulberry Fork | 5.0 ft | 10.0 ft | USGS |
| Locust Fork | 1.70 ft | 2.5 ft | USGS |
| Town Creek | 180 cfs | 250 cfs | USGS |
| South Sauty | 8.34 ft | 8.9 ft | USGS |
| Tellico River | 1.70 ft | 2.0 ft | USGS |
| Little River Canyon | 300 cfs | 500 cfs (uses special 6-level) | USGS |
| Short Creek | 0.5 ft | 1.0 ft | StreamBeam |
| Rush South | 4,000 cfs (2 units) | 8,000 cfs (3 units) | USGS |
| Hiwassee Dries | 3,000 cfs | 5,000 cfs | TVA |
| Ocoee #3 (Upper) | 1,000 cfs | 1,250 cfs | TVA |
| Ocoee #2 (Middle) | 1,000 cfs | 1,250 cfs | TVA |
| Ocoee #1 (Lower) | 800 cfs | 1,000 cfs | TVA |

## Systemd Integration

Enable auto-start on boot using Podman Quadlet. This will run the Flask API + Dashboard system automatically.

### Setup Steps

1. **Create the systemd unit file**:
```bash
mkdir -p ~/.config/containers/systemd
cat > ~/.config/containers/systemd/usgs-alert.container << 'EOF'
[Unit]
Description=USGS River Alert System with Flask API
After=network-online.target

[Container]
Image=localhost/usgs-api:latest
Pull=never
PublishPort=8080:8080

# Load credentials from .env_creds file
EnvironmentFile=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/.env_creds

# Runtime configuration
Environment=BIND_HOST=0.0.0.0
Environment=RUN_INTERVAL_SEC=60
Environment=QPF_TTL_HOURS=3
Environment=QPF_CACHE=/data/qpf_cache.sqlite
Environment=SITE_DIR=/site
Environment=PORT=8080
Environment=NWS_UA=mdchansl-usgs-alert/1.0
Environment=NWS_CONTACT=michael.chanslor@gmail.com

# Persistent data volumes
Volume=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data:/data:Z
Volume=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-site:/site:Z

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=default.target
EOF
```

2. **Build the image** (if not already built):
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
podman build -f Containerfile.api.simple -t usgs-api:latest .
```

3. **Enable and start the service**:
```bash
systemctl --user daemon-reload
systemctl --user enable --now usgs-alert.service
loginctl enable-linger "$USER"
```

4. **Verify service status**:
```bash
systemctl --user status usgs-alert.service --no-pager
```

5. **View logs**:
```bash
journalctl --user -u usgs-alert.service -f
```

6. **Access locally**:
- Dashboard: http://YOUR_IP:8080/ (e.g., http://192.168.1.168:8080/)
- API Info: http://YOUR_IP:8080/api
- River Data: http://YOUR_IP:8080/api/river-levels/02399200

**Note**: Use your machine's IP address (not `localhost`) for reliable access. Find your IP with: `ip addr show | grep "inet "`

### Service Management

```bash
# Stop service
systemctl --user stop usgs-alert.service

# Restart service (after config changes)
systemctl --user restart usgs-alert.service

# Disable auto-start
systemctl --user disable usgs-alert.service

# Check if enabled
systemctl --user is-enabled usgs-alert.service
```

## Cache Management

The system uses SQLite caching for external API data to reduce load and improve performance.

### Cache Files (in `/data/`)

| File | Data | TTL | Source |
|------|------|-----|--------|
| `qpf_cache.sqlite` | Rainfall forecasts | 3 hours | NWS API |
| `drought_cache.sqlite` | Drought status | 12 hours | USDM API |
| `state.sqlite` | Alert state | Permanent | Internal |
| `tva_history.sqlite` | TVA dam observations | Permanent | TVA API |

### Deploying Code Changes That Affect Cached Data

**IMPORTANT:** If you change code that affects cached data (like drought display text, colors, etc.), you must clear the cache AND restart for changes to appear. Just deploying is NOT enough!

**Step-by-step for Fly.io:**

```bash
# Step 1: Deploy your code changes
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy -a docker-blue-sound-1751 --local-only

# Step 2: Find your machine ID
fly status -a docker-blue-sound-1751
# Look for the ID in the Machines table (e.g., d8994e4a0d6138)

# Step 3: Delete the relevant cache file(s)
fly ssh console -a docker-blue-sound-1751 -C "rm -f /data/drought_cache.sqlite"
# For QPF changes:
fly ssh console -a docker-blue-sound-1751 -C "rm -f /data/qpf_cache.sqlite"

# Step 4: Restart the machine to regenerate data with new code
fly machine restart d8994e4a0d6138 -a docker-blue-sound-1751

# Step 5: Wait ~10 seconds, then verify the change
fly ssh console -a docker-blue-sound-1751 -C "grep 'your-search-term' /site/index.html"
```

**Why this matters:** The cache stores the formatted output (including text/colors). Even after deploying new code, the old cached data is still used until it expires (up to 12 hours for drought). Deleting the cache forces a fresh fetch with the new code.

### Clearing Caches (Quick Reference)

**On Fly.io (production):**
```bash
# Clear drought cache
fly ssh console -a docker-blue-sound-1751 -C "rm -f /data/drought_cache.sqlite"

# Clear QPF cache
fly ssh console -a docker-blue-sound-1751 -C "rm -f /data/qpf_cache.sqlite"

# Restart to fetch fresh data (replace with your machine ID)
fly machine restart d8994e4a0d6138 -a docker-blue-sound-1751
```

**Locally (podman/systemd):**
```bash
# Clear caches
rm -f usgs-data/drought_cache.sqlite usgs-data/qpf_cache.sqlite

# Restart container
podman restart usgs-api
# or
systemctl --user restart usgs-alert.service
```

## Git Repository State

**Current Production Status**: Working as of 12-19-2025

**Production Deployment:**
- URL: https://docker-blue-sound-1751.fly.dev/
- Containerfile: `Containerfile.api.simple`
- Entrypoint: `entrypoint-api.sh`
- Features: Flask API + Dashboard + ESP32 endpoints + TVA integration + Historical Charts
- **Total Sites Monitored**: 12 rivers

**Recent Updates:**
- **2025-12-19: Added TVA Historical Chart Feature**
  - New `tva_history.py` module for indefinite storage of TVA dam observations
  - SQLite database stores discharge, pool elevation, tailwater for all time
  - API endpoints: `/api/tva-history/{site_code}` and `/api/tva-history/{site_code}/stats`
  - Interactive Chart.js visualization with 7d/30d/90d/1yr time range selector
  - Dual-axis chart: CFS on left, elevation on right
  - Stats cards showing observation count, max/avg release, data range
  - See updated `TVA_HIWASSEE_DRIES.md` for full documentation

- **2025-12-18: Added TVA Hiwassee Dries Integration**
  - New `tva_fetch.py` module for TVA REST API
  - Monitors Apalachia Dam spillway releases via `HADT1` site code
  - API endpoint: `https://www.tva.com/RestApi/observed-data/HADT1.json`
  - Threshold: 3,000 CFS for runnable status
  - PWS weather stations: KNCMURPH4 (Murphy NC), KTNBENTO3 (Benton TN), KTNCLEVE20 (Cleveland TN)
  - Added `get_tva_trend_data()` for 12-hour trend sparklines (same format as USGS)
  - See `TVA_HIWASSEE_DRIES.md` for full documentation
- Added US Drought Monitor integration (`drought.py`) for Alabama rivers
- Drought status displayed below weather with color-coded D0-D4 levels
- Sparklines now show runnable status (green=above threshold, red=below)
- CFS-based rivers use discharge data in sparklines
- Added PWS (Weather Underground Personal Weather Stations) as primary weather source
- NWS airport stations now used as fallback when PWS unavailable
- Fixed Containerfile permissions for pws_observations.py
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
- `TVA_HIWASSEE_DRIES.md` - TVA API discovery and Hiwassee Dries integration details

**Backup Files:**
Backup files exist in backups/ directory. Several experimental/patched versions present:
- usgs_multi_alert.py.BACKUP, .b4, .b4-patch, .claude-fix
- qpf_trend.patch

These should not be committed to production branches.

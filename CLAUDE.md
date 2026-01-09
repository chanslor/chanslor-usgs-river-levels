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

## Short Creek StreamBeam Gauge

See **[SHORT_CREEK_STREAMBEAM.md](SHORT_CREEK_STREAMBEAM.md)** for complete documentation including:
- Current offset configuration (22.39)
- Recalibration procedure
- Troubleshooting guide
- History of datum changes

**Quick Reference:**
- StreamBeam Site ID: 1
- Current Offset: `22.39` (raw - offset = actual level)
- Validation Range: `[-5.0, 30.0]` ft
- Dashboard: https://www.streambeam.net/Home/Gauge?siteID=1

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
     - North Chickamauga: KTNSODDY175, KTNBENTO3, KTNCLEVE20

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

7. **ocoee_correlation.py** — Ocoee Dam Cascade Correlation Page (NEW - 2025-12-23)
   - Generates correlation page showing all 3 Ocoee dams on overlapping charts
   - Visualizes water cascade: Upper (#3) → Middle (#2) → Lower (#1)
   - Three visualization views with tab navigation:
     - **Overlapping Lines**: All 3 dams on single chart (discharge)
     - **Multi-Panel Synced**: 3 stacked charts with synchronized time axis
     - **Full Metrics**: CFS + Pool elevation + Tailwater on dual y-axes
   - Time range selector: 7d/30d/90d/1yr
   - Current status cards showing CFS, pool elevation, tailwater for each dam
   - Links to individual dam detail pages
   - Output: `/site/details/ocoee-cascade.html`

8. **site_detail.py** — Site detail page generator
   - Creates individual detail pages for each gauge
   - **3-day CFS and Feet charts** with runnable threshold line (green dashed)
   - **Visual Gauge chart** (North Chickamauga only) - Shows calculated visual readings
     - Formula: `Visual = 0.69 × USGS_Stage - 1.89`
     - 1.7 ft threshold line, yellow-gradient styling
     - Detection via `is_north_chick` flag for site 03566535
   - **Level Prediction Panel** - Shows trend analysis and ETA to threshold:
     - Current level, threshold, trend (rising/falling/steady)
     - Rate of change (ft/hr) based on 8-hour analysis
     - Distance to threshold (+/- feet)
     - ETA to reach or drop below threshold
     - Updates every 60 seconds with fresh data
   - Historical section with 3d/7d/30d/90d/1yr time range selector
   - Dual-axis Chart.js charts (CFS left, gage height right)
   - Average period selector (24h/48h/3d/7d) for quick stats
   - Rainfall chart with QPF forecast overlay
   - Stats cards showing data points, max/avg CFS, max height
   - Fetches data dynamically from `/api/usgs-history/{site_id}`
   - Linked from main dashboard for deep-dive analysis

9. **drought.py** — US Drought Monitor integration
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

10. **air_quality.py** — Air Quality Index integration (Open-Meteo)
   - Fetches current air quality from Open-Meteo Air Quality API
   - API endpoint: `https://air-quality-api.open-meteo.com/v1/air-quality`
   - No authentication required (free for non-commercial use)
   - SQLite caching with configurable TTL (default 1 hour)
   - Uses lat/lon coordinates from gauges.conf.json
   - Environment variables: `AQI_CACHE`, `AQI_TTL_HOURS`
   - Cache is stored at `/data/aqi_cache.sqlite`
   - **US AQI Scale (0-500):**
     | AQI Range | Category | Color | Hex |
     |-----------|----------|-------|-----|
     | 0-50 | Good | Green | `#00e400` |
     | 51-100 | Moderate | Yellow | `#ffff00` |
     | 101-150 | Unhealthy for Sensitive Groups | Orange | `#ff7e00` |
     | 151-200 | Unhealthy | Red | `#ff0000` |
     | 201-300 | Very Unhealthy | Purple | `#8f3f97` |
     | 301-500 | Hazardous | Maroon | `#7e0023` |
   - **PM2.5 Levels (μg/m³):**
     | PM2.5 Range | Health Concern |
     |-------------|----------------|
     | 0-12.0 | Good |
     | 12.1-35.4 | Moderate |
     | 35.5-55.4 | Unhealthy for Sensitive Groups |
     | 55.5-150.4 | Unhealthy |
     | 150.5-250.4 | Very Unhealthy |
     | 250.5+ | Hazardous |
   - Reference links:
     - AQI: https://www.airnow.gov/aqi/aqi-basics/
     - PM2.5: https://www.epa.gov/pm-pollution/particulate-matter-pm-basics

11. **rainfall_history.py** — Rainfall History Storage (NEW - 2026-01-02)
   - SQLite database module for indefinite storage of daily precipitation data
   - Records rainfall from two sources:
     - **PWS (Weather Underground)** - Real-time daily totals, captured every 60 seconds
     - **Open-Meteo Historical API** - For backfilling historical data and validation
   - Database location: `/data/rainfall_history.sqlite`
   - Environment variable: `RAINFALL_HISTORY_DB`
   - **Key Functions:**
     - `init_database()` - Initialize rainfall history tables
     - `record_pws_rainfall()` - Record PWS observation with precipitation data
     - `save_daily_rainfall()` - Save daily total for a river/date
     - `get_daily_rainfall()` - Retrieve daily history for a river
     - `get_rainfall_stats()` - Get statistics (total, avg, max, rainy days)
     - `get_weekly_summary()` - Get 7-day breakdown with totals
     - `get_all_rivers_today()` - Get today's rainfall for all rivers
     - `backfill_historical_data()` - Fetch historical data from Open-Meteo
   - **Database Tables:**
     - `daily_rainfall` - Final daily totals per river/date/source
     - `rainfall_observations` - Real-time PWS observations throughout the day
     - `rainfall_river_correlation` - Links rain events to river level peaks (future analysis)
   - **Purpose:** Correlate rainfall amounts with river level rises to predict when rivers will reach min/max thresholds
   - API endpoints: `/api/rainfall`, `/api/rainfall/{river_name}`, `/api/rainfall/{river_name}/weekly`

12. **paddle_log.py** — Paddle Event Log (NEW - 2026-01-03)
   - SQLite database module for tracking successful paddle runs
   - Records paddle events with rainfall correlation data to understand rain-to-runnable patterns
   - Database location: `/data/paddle_log.sqlite`
   - **Key Functions:**
     - `init_database()` - Initialize paddle events table
     - `log_paddle_event()` - Record a paddle event with rainfall and river data
     - `get_paddle_events()` - Query events, optionally filtered by river
     - `get_river_stats()` - Get statistics for a specific river
     - `get_all_river_stats()` - Get statistics for all rivers
   - **Data Captured Per Event:**
     - River name, paddle date/time
     - CFS and feet at time of paddle
     - Rainfall in last 24h, 48h, 72h, 7 days
     - Peak CFS/feet (can be updated later)
     - Response hours (time from rain to runnable)
     - Water trend (rising/falling/steady)
     - Notes
   - **Purpose:** Build historical data to understand:
     - How much rain each river needs to become runnable
     - Typical response time from rain to runnable conditions
     - Optimal CFS/feet ranges for each river
   - API endpoints: `/api/paddle-log`, `/api/paddle-log/stats`

13. **entrypoint-api.sh** — Container orchestration (PRODUCTION)
   - Runs initial gauge check immediately on startup
   - Launches background loop to refresh data every `RUN_INTERVAL_SEC` (default 60s)
   - Starts Flask API server on port 8080
   - Serves both HTML dashboard (/) and API endpoints (/api/*)

   **entrypoint.sh** — Simple HTTP server (LEGACY)
   - Basic Python HTTP server for static file serving
   - No API endpoints, dashboard only
   - Use entrypoint-api.sh for production deployments

11. **gauges.conf.json** — Configuration file
   - SMTP settings for email alerts (server, port, credentials)
   - Site definitions with USGS site IDs and custom thresholds
   - FIPS county codes for drought monitoring (Alabama rivers only)
   - Alert behavior: `notify.mode` ("rising" or "any"), cooldown periods
   - State persistence path (`state_db`)

12. **test_visual_indicators.py** — Test suite generator
   - Generates comprehensive test HTML for all visual indicators
   - Tests all 6 Little River Canyon color zones with 22 test cases
   - Validates temperature alerts (10 cases: 35-85°F)
   - Validates wind alerts (8 cases: 0-30 mph)
   - Creates standalone HTML test file with color legend
   - Run with: `python3 test_visual_indicators.py`

13. **predictions.py** — River Predictions Module (NEW - 2025-11-30)
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
| North Chickamauga | 18 hours | 2.00" | Fast |
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
│  - Weather Underground PWS API (primary weather + precip) │
│  - NWS Observations API (fallback weather)                │
│  - StreamBeam API (Short Creek gauge)                     │
│  - TVA REST API (Hiwassee Dries / Apalachia Dam)          │
│  - Open-Meteo Historical Weather API (rainfall backfill)  │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  Background Worker (usgs_multi_alert.py)                   │
│  - Runs every 60 seconds                                   │
│  - Fetches + processes data                                │
│  - Updates SQLite state DB                                 │
│  - Saves TVA observations to tva_history.sqlite            │
│  - Saves PWS rainfall to rainfall_history.sqlite           │
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
│  - GET /api/rainfall → today's rainfall for all rivers     │
│  - GET /api/rainfall/{river} → rainfall history            │
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
- **`GET /details/{site_id}.html`** - Individual river detail page with 7d/30d/90d/1yr historical charts
- **`GET /gauges.json`** - Raw JSON data feed

### API Documentation
- **`GET /api`** - API information and endpoint listing

### Data Endpoints (for ESP32/IoT)
- **`GET /api/health`** - Health check, returns `{"status": "ok", "timestamp": "..."}`
- **`GET /api/river-levels`** - All monitored rivers with formatted data
- **`GET /api/river-levels/{site_id}`** - Single river by USGS site ID (e.g., 02399200)
- **`GET /api/river-levels/name/{name}`** - Single river by name search (case-insensitive)
- **`GET /api/predictions`** - River predictions based on QPF and historical patterns

### USGS Historical Data Endpoints (NEW - 2025-12-23)
- **`GET /api/usgs-history/{site_id}?days=7`** - Get historical USGS data for charting
  - Query param `days`: Number of days of history (1-365, default: 7)
  - Returns: CFS and gage height time series, stats (min/max/avg)
  - Data is downsampled to ~200 points for smooth charting
  - Powers the 7d/30d/90d/1yr time range selector on detail pages

### TVA Historical Data Endpoints (NEW - 2025-12-19)
- **`GET /api/tva-history/{site_code}?days=7`** - Get historical TVA observations
  - Query param `days`: Number of days of history (1-365, default: 7)
  - Returns: observations array, stats, date range
- **`GET /api/tva-history/{site_code}/stats?days=30`** - Get statistics only
  - Returns: min/max/avg for discharge, pool, tailwater

### Ocoee Cascade Correlation Endpoint (NEW - 2025-12-23)
- **`GET /api/tva-history/ocoee/combined?days=7`** - Get combined data for all 3 Ocoee dams
  - Query param `days`: Number of days of history (1-365, default: 7)
  - Returns combined time series for OCCT1, OCBT1, OCAT1
  - Each site includes: observations, stats, date_range
  - Used by the Ocoee cascade correlation page for overlapping charts

### Rainfall History Endpoints (NEW - 2026-01-02)
- **`GET /api/rainfall`** - Get today's rainfall totals for all rivers
  - Returns: date, array of rivers with precip_in, source, station_id
  - Updated every 60 seconds from PWS stations
- **`GET /api/rainfall/{river_name}?days=30`** - Get historical rainfall for a river
  - Query param `days`: Number of days of history (1-365, default: 30)
  - Returns: daily rainfall totals, statistics (total, avg, max, rainy days)
  - Example: `/api/rainfall/Little%20River?days=30`
- **`GET /api/rainfall/{river_name}/weekly`** - Get 7-day rainfall summary
  - Returns: daily breakdown with day names, week total
  - Example: `/api/rainfall/Locust%20Fork/weekly`

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
- `RAINFALL_HISTORY_DB`: Path to rainfall history SQLite database (default: /data/rainfall_history.sqlite)

### File Locations (in container)

- `/app/`: Application code
  - `usgs_multi_alert.py` - Main monitoring script
  - `qpf.py` - QPF weather forecast integration
  - `observations.py` - NWS weather observations (fallback)
  - `pws_observations.py` - PWS weather observations (primary)
  - `drought.py` - US Drought Monitor integration
  - `air_quality.py` - Air Quality Index integration (Open-Meteo)
  - `rainfall_history.py` - Rainfall history storage module
  - `paddle_log.py` - Paddle event log for tracking successful runs
  - `tva_fetch.py` - TVA dam data fetcher (Hiwassee Dries, Ocoee)
  - `tva_history.py` - TVA historical data storage module
  - `ocoee_correlation.py` - Ocoee cascade correlation page generator
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
  - `rainfall_history.sqlite` - Rainfall history (indefinite storage)
  - `paddle_log.sqlite` - Paddle event log (tracks successful runs with rainfall data)
- `/site/`: Generated output (bind mount required)
  - `index.html` - Main dashboard
  - `gauges.json` - JSON data feed
  - `test_visual_indicators.html` - Test suite
  - `details/{site_id}.html` - Individual gauge detail pages
  - `details/ocoee-cascade.html` - Ocoee dam cascade correlation page

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

### Rain Forecast Marquee

When rain is in the forecast, a scrolling marquee banner appears at the top of the main dashboard page announcing the upcoming precipitation:

| Feature | Description |
|---------|-------------|
| **Trigger** | Appears when any river has >0.25" QPF forecast |
| **Content** | Shows which rivers have rain and when (Today, Tomorrow, Day 3) |
| **Style** | Dark blue gradient background with cyan border |
| **Animation** | Smooth horizontal scroll, pauses on hover |
| **Location** | Top of page, above the river table |

**Example marquee content:**
```
☔ RAIN FORECAST: up to 0.75" TODAY, 0.50" tomorrow ☔ 🌧️ Locust Fork: 0.75" TODAY 🌧️ Short Creek: 0.50" Tomorrow...
```

**Implementation Details:**
- Aggregates QPF data from all monitored rivers
- Only shows rivers with significant rainfall (>0.25")
- Content duplicates for seamless looping animation
- Hidden when no rain is forecast (0.00" for all days)

### Current River Thresholds

| River | min | good | Data Source |
|-------|-----|------|-------------|
| Mulberry Fork | 5.0 ft | 10.0 ft | USGS |
| Locust Fork | 2.0 ft | 2.5 ft | USGS |
| Town Creek | 180 cfs | 250 cfs | USGS |
| South Sauty | 8.34 ft | 8.9 ft | USGS |
| Tellico River | 1.70 ft | 2.0 ft | USGS |
| Little River Canyon | 300 cfs | 500 cfs (uses special 6-level) | USGS |
| Short Creek | 0.5 ft | 1.0 ft | StreamBeam |
| Rush South | 4,000 cfs (2 units) | 8,000 cfs (3 units) | USGS |
| North Chickamauga | 5.2 ft (1.7 visual) | 6.6 ft (2.7 visual) | USGS |
| Hiwassee Dries | 3,000 cfs | 5,000 cfs | TVA |
| Ocoee #3 (Upper) | 1,000 cfs | 1,250 cfs | TVA |
| Ocoee #2 (Middle) | 1,000 cfs | 1,250 cfs | TVA |
| Ocoee #1 (Lower) | 800 cfs | 1,000 cfs | TVA |

### North Chickamauga Visual Gauge Conversion

North Chickamauga Creek uses a **visual gauge** at the take-out that paddlers reference, which differs from the USGS gauge reading. Rain Pursuit (rainpursuit.org) displays both values and correlates them.

**Conversion Formula:**
```
Visual (paddler) = 0.69 × USGS_Stage - 1.89
USGS_Stage = (Visual + 1.89) / 0.69
```

**Calibration Data Points:**
| Date | USGS Stage | CFS | Visual Reading |
|------|------------|-----|----------------|
| 02/25/2022 | 6.22 ft | 743 | 2.42 ft |
| 02/26/2022 | 5.34 ft | 459 | 1.81 ft |

**Threshold Conversion:**
| Paddler Visual | USGS Stage | Status |
|----------------|------------|--------|
| 1.7 ft | 5.2 ft | Runnable (min) |
| 2.7 ft | 6.6 ft | Good |

**Example:** When USGS shows 2.69 ft, visual equivalent is ~0 ft (not runnable).

**Data Source:**
- USGS Site: 03566535 (North Chickamauga Creek at Mile Straight, TN)
- Location: Soddy-Daisy, Hamilton County, TN
- PWS Station: KTNSODDY175
- Rain Pursuit: https://rainpursuit.org/stream_gauge.php?id=1008

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
| `rainfall_history.sqlite` | Daily precipitation | Permanent | PWS + Open-Meteo |

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

**Current Production Status**: Working as of 01-07-2026

**Production Deployment:**
- URL: https://docker-blue-sound-1751.fly.dev/
- Region: Dallas (dfw) - migrated from iad on 2026-01-05
- Containerfile: `Containerfile.api.simple`
- Entrypoint: `entrypoint-api.sh`
- Features: Flask API + Dashboard + ESP32 endpoints + TVA integration + Historical Charts + Rainfall History + Level Predictions
- **Total Sites Monitored**: 13 rivers

**Fly.io Reference**: See **[FLY_IO.md](FLY_IO.md)** for complete Fly.io deployment guide including:
- Basic commands reference
- Region migration procedures
- Volume management
- Troubleshooting common issues

**Recent Updates:**
- **2026-01-07: Added North Chickamauga Creek (Tennessee)**
  - New river: North Chickamauga Creek at Mile Straight, TN
  - USGS Site: 03566535
  - Location: Soddy-Daisy, Hamilton County, TN
  - PWS Weather Station: KTNSODDY175
  - **Visual Gauge Conversion**: `Visual = 0.69 × USGS_Stage - 1.89`
  - Thresholds: 5.2 ft runnable (1.7 visual), 6.6 ft good (2.7 visual)
  - Characteristics: Fast responder, ~18 hours, needs ~2" rain
  - Data source: Rain Pursuit aggregates from USGS
  - Total monitored rivers now: 13

- **2026-01-07: Added Visual Gauge Chart to North Chickamauga Detail Page**
  - New chart showing calculated visual gauge readings (above CFS chart)
  - Uses formula `Visual = 0.69 × USGS_Stage - 1.89` to convert USGS feet to visual gauge
  - Green dashed threshold line at 1.7 ft (runnable threshold)
  - Yellow-gradient styling to distinguish from other charts
  - Average period selector (24h/48h/3d/7d) for visual gauge values
  - Calibration note showing conversion formula and data points
  - Only appears on North Chickamauga (03566535) detail page
  - Implementation in `site_detail.py`: `is_north_chick` detection flag, `visual_values` calculation

- **2026-01-05: Added Rain Forecast Marquee to Main Dashboard**
  - Scrolling banner at top of page when rain is in the forecast
  - Shows which rivers have rain forecast and timing (Today, Tomorrow, Day 3)
  - Only appears when QPF > 0.25" for any river
  - Dark blue gradient background with smooth horizontal scroll animation
  - Pauses on hover for easy reading
  - Aggregates QPF data from all monitored rivers

- **2026-01-05: Migrated to Dallas (dfw) Region**
  - Forked volume from iad to dfw to preserve all historical data
  - Migration required due to persistent "insufficient memory" errors in iad region
  - All SQLite databases preserved: rainfall_history, tva_history, paddle_log, state, caches
  - Updated fly.toml `primary_region` from 'iad' to 'dfw'
  - See FLY_IO.md for complete migration procedure

- **2026-01-05: Added Vertical Grid Lines to Charts**
  - All detail page charts now have subtle vertical grid lines for better time reading
  - Changed x-axis grid from `display: false` to `color: 'rgba(0,0,0,0.08)'`
  - Increased `maxTicksLimit` from 18 to 24 for more x-axis time labels
  - Reduced font size from 10 to 9 for better label fit
  - Applied to: CFS chart, Feet chart, Historical chart

- **2026-01-05: Added LRC Flow Guide to Little River Canyon Detail Page**
  - Interactive flow guide panel with 6-level classification (from Adam Goshorn)
  - Color-coded zones: Not Runnable (<250), Good Low (250-400), Shitty Medium (400-800), Good Medium (800-1500), BEST! (1500-2500), Too High (>2500)
  - Multi-level horizontal threshold lines on CFS chart matching flow guide colors
  - Current CFS shown with matching zone badge
  - Only appears on Little River Canyon (02399200) detail page

- **2026-01-04: Added Level Prediction Panel to Detail Pages**
  - Real-time prediction of when river will reach/drop below runnable threshold
  - Shows current level, threshold, trend direction (rising ↗ / falling ↘ / steady →)
  - Calculates rate of change (ft/hr) based on 8-hour trend analysis
  - Uses 8-hour window for more stable/representative predictions than shorter periods
  - Displays distance to threshold (+/- feet) and ETA
  - Green-tinted panel when above threshold, yellow when below
  - Updates every 60 seconds with each data refresh
  - Example: "Falling ↘ at 0.015 ft/hr → ETA to 2.0 ft: ~10.7 hours"

- **2026-01-04: Added Runnable Threshold Lines to Charts**
  - Green dashed horizontal line on Feet chart at runnable threshold
  - Green dashed horizontal line on CFS chart at runnable threshold (if CFS-based)
  - Makes it easy to see when water level crosses runnable threshold
  - Legend shows "Runnable Threshold" label

- **2026-01-04: Changed Default Chart Range to 3 Days**
  - Detail page CFS and Feet charts now show 3 days instead of 7 days
  - Historical section default changed from 7 days to 3 days
  - More x-axis tick marks for better time resolution
  - Smarter time labels: "Sat 2pm" for 3-day, "Jan 4 2pm" for 7-day

- **2026-01-04: Updated Locust Fork Threshold**
  - Changed runnable threshold from 1.70 ft to 2.0 ft
  - Based on paddler experience and better reflects actual runnable conditions

- **2026-01-03: Added Paddle Event Log**
  - New `paddle_log.py` module for tracking successful paddle runs
  - Records paddle events with rainfall correlation data (24h, 48h, 72h, 7d rain)
  - Captures CFS/feet at paddle, peak values, water trend, response time
  - Purpose: Build historical data to understand rain-to-runnable patterns per river
  - New API endpoints: `/api/paddle-log`, `/api/paddle-log/stats`
  - First event logged: Locust Fork on 2026-01-03 (314 CFS, 2.44 ft, 1.0" rain in 48h)
  - Statistics show avg rain needed, typical CFS range, response hours per river

- **2026-01-03: Added Average Period Selector to Detail Pages**
  - Interactive buttons (24h, 48h, 3d, 7d) to switch average calculation period
  - Both CFS and Feet charts have independent selectors
  - Client-side JavaScript calculates averages instantly (no page reload)

- **2026-01-03: Added QPF Forecast Bars to Rainfall Chart**
  - Detail pages now show both historical rainfall and QPF forecast
  - Blue bars = historical rain (past 7 days)
  - Orange bars = QPF forecast (Today, Tomorrow, Day 3)
  - Legend distinguishes between actual and forecast data

- **2026-01-03: Added Footer with Contact Info**
  - "Michael Chanslor 2026" footer on main page and all detail pages
  - Helps paddle community identify who to contact about the site

- **2026-01-02: Added Rainfall History Tracking**
  - New `rainfall_history.py` module for indefinite precipitation storage
  - Records daily rainfall from PWS (Weather Underground) stations
  - Backfill capability from Open-Meteo Historical Weather API
  - 365 days of historical data pre-loaded for all rivers
  - New API endpoints: `/api/rainfall`, `/api/rainfall/{river_name}`, `/api/rainfall/{river_name}/weekly`
  - Database tables: `daily_rainfall`, `rainfall_observations`, `rainfall_river_correlation`
  - Purpose: Correlate rainfall amounts with river level rises for prediction
  - PWS captures `precipTotal` every 60 seconds during monitoring loop
  - Example: "0.52" rain → Little River Canyon peaks at X CFS in Y hours"

- **2025-12-31: Added Air Quality Index (AQI) Integration**
  - New `air_quality.py` module fetches data from Open-Meteo Air Quality API
  - Displays US AQI value, category, and PM2.5 concentration for each river
  - Color-coded by EPA standard (Green=Good through Maroon=Hazardous)
  - SQLite caching with 1-hour TTL
  - AQI and PM2.5 labels are clickable links to EPA explanation pages

- **2025-12-30: Fixed Short Creek StreamBeam Integration & Added History Storage**
  - Fixed offset issue: Changed `streambeam_zero_offset` from `22.39` to `0.0`
  - StreamBeam's datum changed, causing readings to fail validation (-22.86 ft outside [-5.0, 15.0])
  - Added `streambeam_history` table in `/data/state.sqlite` for sparkline support
  - New functions: `_init_streambeam_history_table()`, `_save_streambeam_history()`, `_get_streambeam_trend_data()`
  - StreamBeam readings now stored with each fetch for trend data visualization
  - Sparklines populate over time as StreamBeam provides new readings (~15 min intervals)

- **2025-12-23: Added Ocoee Dam Cascade Correlation Feature**
  - New `ocoee_correlation.py` module for generating cascade visualization page
  - New `/api/tva-history/ocoee/combined` endpoint for combined Ocoee data
  - Shows relationship between all 3 Ocoee dams: Upper (#3) → Middle (#2) → Lower (#1)
  - Three visualization views with tab navigation:
    - Overlapping Lines: All 3 dams on single chart
    - Multi-Panel Synced: 3 stacked charts with synchronized time axis
    - Full Metrics: CFS + Pool elevation + Tailwater on dual y-axes
  - Time range selector: 7d/30d/90d/1yr
  - Status cards showing current CFS, pool elevation, tailwater for each dam
  - Link added to each Ocoee detail page for easy navigation
  - URL: https://docker-blue-sound-1751.fly.dev/details/ocoee-cascade.html

- **2025-12-23: Added USGS Historical Chart Feature**
  - New `/api/usgs-history/{site_id}?days=N` endpoint for fetching historical USGS data
  - All USGS detail pages now have 7d/30d/90d/1yr time range selector
  - Interactive Chart.js visualization with dual-axis (CFS left, feet right)
  - Stats cards showing data points, max CFS, avg CFS, max height
  - Data is fetched directly from USGS IV service and downsampled for smooth charting
  - Matches the TVA historical chart feature added on 2025-12-19

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
- `SHORT_CREEK_STREAMBEAM.md` - Short Creek gauge calibration and troubleshooting
- `TVA_HIWASSEE_DRIES.md` - TVA API discovery and Hiwassee Dries integration details
- `VALIDATOR_README.md` - Dashboard validation tool documentation

**Backup Files:**
Backup files exist in backups/ directory. Several experimental/patched versions present:
- usgs_multi_alert.py.BACKUP, .b4, .b4-patch, .claude-fix
- qpf_trend.patch

These should not be committed to production branches.

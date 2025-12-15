# USGS River Levels API

REST API endpoints for fetching river monitoring data optimized for ESP32/IoT devices.

**Production URL**: https://docker-blue-sound-1751.fly.dev/

## Quick Start

### Option 1: Test Locally (requires Flask)

```bash
# Install dependencies
pip3 install flask flask-cors requests python-dateutil

# Run the background worker once to generate data
python3 usgs_multi_alert.py \
  --config gauges.conf.json \
  --cfs \
  --dump-json /tmp/site/gauges.json \
  --dump-html /tmp/site/index.html

# Update api_app.py to point to /tmp/site/gauges.json
# Then start the API server
python3 api_app.py
```

### Option 2: Build and Run with Podman/Docker

```bash
# Build the API-enabled container
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
podman build -f Containerfile.api.simple -t usgs-river-api:latest .

# Run it with persistent storage
podman run -d --name usgs-river-api \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  usgs-river-api:latest

# View logs
podman logs -f usgs-river-api

# Access locally
# Dashboard: http://localhost:8080/
# API Info: http://localhost:8080/api
```

### Option 3: Deploy to Fly.io

The `fly.toml` is already configured to use `Containerfile.api.simple`:

```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy --local-only
```

Production deployment includes:
- Main dashboard at `/`
- API endpoints at `/api/*`
- Persistent volume mounted at `/data`
- Auto-refresh every 60 seconds

## API Endpoints

### Main Dashboard
```bash
GET /
```

Returns the full HTML dashboard with sparkles, color-coded river levels, temperature/wind alerts, and interactive charts.

**Example:**
```bash
# View in browser
https://docker-blue-sound-1751.fly.dev/
```

---

### API Information
```bash
GET /api
```

Returns API documentation and available endpoints.

**Example:**
```bash
curl https://docker-blue-sound-1751.fly.dev/api
```

**Response:**
```json
{
  "name": "USGS River Levels API",
  "version": "1.1",
  "dashboard": "/",
  "endpoints": {
    "health": "/api/health",
    "all_rivers": "/api/river-levels",
    "by_site_id": "/api/river-levels/{site_id}",
    "by_name": "/api/river-levels/name/{name}",
    "predictions": "/api/predictions"
  },
  "examples": {
    "little_river": "/api/river-levels/02399200",
    "little_river_by_name": "/api/river-levels/name/little",
    "locust_fork": "/api/river-levels/02455000",
    "predictions": "/api/predictions"
  },
  "new_features": {
    "predictions": "River predictions based on QPF forecast and 90-day historical response patterns"
  }
}
```

---

### Health Check
```bash
GET /api/health
```

Returns API health status.

**Example:**
```bash
curl https://docker-blue-sound-1751.fly.dev/api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-11-19T19:45:00Z"
}
```

---

### Get All River Levels
```bash
GET /api/river-levels
```

Returns data for all monitored river sites.

**Example:**
```bash
curl https://docker-blue-sound-1751.fly.dev/api/river-levels
```

**Response:**
```json
{
  "generated_at": "2025-11-17T13:45:00-0500",
  "site_count": 6,
  "sites": [
    {
      "site_id": "02399200",
      "name": "Little River",
      "flow": ">= 450 cfs",
      "trend": "^ rising",
      "stage_ft": 1.45,
      "cfs": 450,
      "thresholds": {
        "min_ft": null,
        "min_cfs": 300,
        "good_ft": null,
        "good_cfs": 500
      },
      "qpf": {
        "today": 0.15,
        "tomorrow": 0.45,
        "day3": 0.0
      },
      "weather": {
        "temp_f": 48.5,
        "wind_mph": 8.5,
        "wind_dir": "NW"
      },
      "timestamp": "2025-11-17T18:30:00Z",
      "in_range": true,
      "display_lines": [
        "Little River",
        ">= 450 cfs ^ rising",
        "QPF Today: 0.15\"",
        "Tom:0.45\" Day3:0.00\"",
        "Max:49F Wind:8.5 NW"
      ]
    }
  ]
}
```

---

### Get Specific River by Site ID
```bash
GET /api/river-levels/{site_id}
```

Returns data for a single site by USGS site ID.

**Example (Little River Canyon):**
```bash
curl https://docker-blue-sound-1751.fly.dev/api/river-levels/02399200
```

**Response:**
```json
{
  "site_id": "02399200",
  "name": "Little River",
  "flow": ">= 450 cfs",
  "trend": "^ rising",
  "stage_ft": 1.45,
  "cfs": 450,
  "thresholds": {
    "min_ft": null,
    "min_cfs": 300,
    "good_ft": null,
    "good_cfs": 500
  },
  "qpf": {
    "today": 0.15,
    "tomorrow": 0.45,
    "day3": 0.0
  },
  "weather": {
    "temp_f": 48.5,
    "wind_mph": 8.5,
    "wind_dir": "NW"
  },
  "timestamp": "2025-11-17T18:30:00Z",
  "in_range": true,
  "display_lines": [
    "Little River",
    ">= 450 cfs ^ rising",
    "QPF Today: 0.15\"",
    "Tom:0.45\" Day3:0.00\"",
    "Max:49F Wind:8.5 NW"
  ]
}
```

---

### Get River by Name
```bash
GET /api/river-levels/name/{name}
```

Returns data for a site by name (case-insensitive partial match).

**Example:**
```bash
curl https://docker-blue-sound-1751.fly.dev/api/river-levels/name/little
```

---

### Get River Predictions
```bash
GET /api/predictions
```

Returns predictions for which rivers are likely to reach runnable levels based on QPF forecast and historical response patterns.

**Example:**
```bash
curl https://docker-blue-sound-1751.fly.dev/api/predictions
```

**Response:**
```json
{
  "generated_at": "2025-11-30T10:15:00-0600",
  "prediction_count": 7,
  "predictions": [
    {
      "site_id": "streambeam_1",
      "name": "Short Creek",
      "likelihood": 95,
      "status": "likely",
      "status_emoji": "🟢",
      "status_text": "Likely",
      "qpf_total": 1.47,
      "rain_needed": 0.65,
      "rain_surplus": 0.82,
      "responsiveness": "fast",
      "avg_response_hours": 12,
      "peak_window": {
        "earliest": "2025-12-02T12:00:00+00:00",
        "latest": "2025-12-02T18:00:00+00:00",
        "earliest_local": "Mon morning",
        "latest_local": "Mon evening"
      },
      "notes": "Small creek, first to rise, first to drop",
      "in_range": false,
      "qpf_breakdown": {
        "today": 0.23,
        "tomorrow": 0.62,
        "day3": 0.62
      }
    },
    {
      "site_id": "03572900",
      "name": "Town Creek",
      "likelihood": 84,
      "status": "likely",
      "status_emoji": "🟢",
      "status_text": "Likely",
      "qpf_total": 1.61,
      "rain_needed": 1.25,
      "rain_surplus": 0.36,
      "responsiveness": "moderate",
      "avg_response_hours": 32,
      "peak_window": {
        "earliest": "2025-12-03T06:00:00+00:00",
        "latest": "2025-12-03T18:00:00+00:00",
        "earliest_local": "Wed night",
        "latest_local": "Wed afternoon"
      },
      "notes": "Responds well to NE Alabama rain events",
      "in_range": false
    }
  ]
}
```

### Prediction Fields

| Field | Description |
|-------|-------------|
| `likelihood` | Percentage chance (0-100%) of river reaching runnable level |
| `status` | Category: `likely`, `possible`, `unlikely`, `very_unlikely`, or `running` |
| `status_emoji` | Visual indicator: 🟢 (likely), 🟡 (possible), 🟠 (unlikely), 🔴 (very unlikely), ✅ (running) |
| `qpf_total` | Total forecasted rainfall over 72 hours (inches) |
| `rain_needed` | Amount of rain typically needed to reach runnable level (inches) |
| `rain_surplus` | Difference between forecast and needed (positive = excess rain expected) |
| `responsiveness` | River speed: `fast`, `moderate`, or `slow` |
| `avg_response_hours` | Average time from rain start to peak level |
| `peak_window` | Estimated time range when river will reach peak level |
| `in_range` | `true` if river is already at/above runnable threshold |

### Prediction Algorithm

Predictions are calculated using:
1. **QPF Forecast** - NWS 72-hour rainfall totals for each river's watershed
2. **Historical Response** - Based on 90-day analysis of USGS gauge data
3. **Rain-to-Runnable** - How much rain each river typically needs

**Likelihood Formula:**
- 70%+ if QPF ≥ rain_needed
- 40-69% if QPF ≥ 75% of rain_needed
- 15-39% if QPF ≥ 50% of rain_needed
- <15% if QPF < 50% of rain_needed

---

## ESP32/Heltec Integration

The API returns a `display_lines` array optimized for the Heltec ESP32 LoRa V3 OLED display (128x64 pixels, 5 lines).

### ESP32 Example Code

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* API_URL = "https://docker-blue-sound-1751.fly.dev/api/river-levels/02399200";

void fetchRiverData() {
  HTTPClient http;
  http.begin(API_URL);

  int httpCode = http.GET();
  if (httpCode == 200) {
    String payload = http.getString();

    // Parse JSON
    DynamicJsonDocument doc(2048);
    deserializeJson(doc, payload);

    // Extract display lines
    JsonArray lines = doc["display_lines"];

    // Display on OLED
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_6x10_tr);

    u8g2.drawStr(0, 12, lines[0]);  // River name
    u8g2.drawStr(0, 25, lines[1]);  // Flow + trend
    u8g2.drawStr(0, 38, lines[2]);  // QPF today
    u8g2.drawStr(0, 51, lines[3]);  // QPF tomorrow/day3
    u8g2.drawStr(0, 64, lines[4]);  // Weather

    u8g2.sendBuffer();
  }
  http.end();
}
```

## Available River Sites

| Site ID | Name | Measurement | min | good |
|---------|------|-------------|-----|------|
| 02450000 | Mulberry Fork | Stage (ft) | 5.0 ft | 10.0 ft |
| 02455000 | Locust Fork | Stage (ft) | 1.70 ft | 2.5 ft |
| 03572900 | Town Creek | Flow (cfs) | 180 cfs | 250 cfs |
| 03572690 | South Sauty | Stage (ft) | 8.34 ft | 8.9 ft |
| 03518500 | Tellico River | Stage (ft) | 1.70 ft | 2.0 ft |
| 02399200 | Little River Canyon | Flow (cfs) | 300 cfs | 500 cfs |
| streambeam:1 | Short Creek | Stage (ft) | 0.5 ft | 1.0 ft |

## Thresholds Explained

Each river has configurable thresholds that determine its status:

| Field | Description |
|-------|-------------|
| `min_ft` / `min_cfs` | Minimum level for river to be "runnable" (IN status) |
| `good_ft` / `good_cfs` | Level at which conditions are "good/ideal" (GOOD status) |

### Dashboard Color Coding

| Status | Condition | Color |
|--------|-----------|-------|
| **OUT** | Below min threshold | Gray |
| **IN** | At/above min, below good | Yellow |
| **GOOD** | At/above good threshold | Light Green |

**Note:** Little River Canyon uses a special 6-level classification based on expert paddler knowledge (Adam Goshorn):

| CFS Range | Status | Color |
|-----------|--------|-------|
| < 250 | Not runnable | Gray |
| 250-400 | Good low | Yellow |
| 400-800 | Shitty medium | Brown |
| 800-1,500 | Good medium | Light Green |
| 1,500-2,500 | Good high (BEST!) | Green |
| 2,500+ | Too high | Red |

## Data Update Frequency

River data is refreshed every 60 seconds by the background worker. API responses are served from the cached `gauges.json` file.

## Weather Data Sources

Weather data is fetched from two sources with automatic fallback:

1. **Primary: Weather Underground PWS** (Personal Weather Stations)
   - Hyperlocal weather data from nearby personal weather stations
   - Each river has a chain of 4 PWS stations to try in order
   - Uses embedded public API key (no account required)

2. **Fallback: NWS Airport Stations**
   - Official National Weather Service airport stations
   - Used only when all PWS stations fail
   - Stations: KCMD (Cullman), KBFZ (Albertville), K4A9 (Fort Payne), etc.

PWS Station Mapping (from `pws_observations.py`):
| River | PWS Stations (in fallback order) |
|-------|----------------------------------|
| Locust Fork | KALBLOUN24, KALBLOUN23, KALHANCE17, KALONEON42 |
| Short Creek | KALGUNTE26, KALALBER97, KALALBER66, KALALBER69 |
| Town Creek | KALFYFFE7, KALFYFFE11, KALALBER111, KALGROVE15 |
| South Sauty | KALLANGS7, KALGROVE15, KALFYFFE11, KALRAINS14 |
| Little River Canyon | KALCEDAR14, KALGAYLE19, KALGAYLE16, KALGAYLE7 |
| Mulberry Fork | KALHAYDE19, KALHAYDE21, KALHAYDE13, KALWARRI54 |

## Drought Data

The dashboard displays US Drought Monitor status for Alabama rivers (Tellico River in TN is excluded). Drought data is fetched by county FIPS code and cached for 12 hours.

**Data Source:** [US Drought Monitor](https://droughtmonitor.unl.edu/)

**County FIPS Mapping:**
| County | FIPS | Rivers |
|--------|------|--------|
| Blount County, AL | 01009 | Mulberry Fork, Locust Fork |
| DeKalb County, AL | 01049 | Town Creek, Little River Canyon |
| Marshall County, AL | 01095 | South Sauty, Short Creek |

**Drought Level Colors (on dashboard):**
| Level | Description | Color |
|-------|-------------|-------|
| D0 | Abnormally Dry | Orange (#e89b3c) |
| D1 | Moderate Drought | Tan (#fcd37f) |
| D2 | Severe Drought | Dark Orange (#ffaa00) |
| D3 | Extreme Drought | Red (#e60000) |
| D4 | Exceptional Drought | Dark Red (#730000) |

**Note:** Drought status is displayed on the HTML dashboard only. It is not currently exposed via the JSON API endpoints.

## Error Responses

### 503 Service Unavailable
```json
{
  "error": "Data not available",
  "message": "Unable to load river data. Background worker may not be running."
}
```

### 404 Not Found
```json
{
  "error": "Site not found",
  "message": "No data available for site 99999999",
  "available_sites": ["02455000", "03572900", "03572690", "03518500", "02399200"]
}
```

## CORS Support

CORS is enabled for all origins, making the API accessible from web applications.

## Architecture

The system uses a dual-service architecture:

```
┌─────────────────────────────────────────┐
│  Background Worker (every 60s)          │
│  - Fetches USGS river data              │
│  - Fetches PWS weather (primary)        │
│  - Falls back to NWS weather if needed  │
│  - Fetches NWS QPF forecast data        │
│  - Fetches US Drought Monitor data      │
│  - Generates gauges.json                │
│  - Generates index.html dashboard       │
│  - Updates SQLite state DB              │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  Flask API Server (port 8080)           │
│  - Serves HTML dashboard at /           │
│  - Serves API info at /api              │
│  - Serves ESP32 data at /api/river-*    │
│  - Reads from cached gauges.json        │
└─────────────────────────────────────────┘
                 ↓
        ┌────────┴────────┐
        ↓                 ↓
  Web Browser        ESP32 Device
  (dashboard)        (API client)
```

**Key Features:**
- **Fast responses**: Flask reads from pre-generated JSON (no external API calls)
- **Live updates**: Background worker refreshes data every 60 seconds
- **Persistent state**: SQLite database tracks alert state and cooldowns
- **Dual interfaces**: HTML dashboard for humans, JSON API for devices
- **Production-ready**: Runs on Fly.io with persistent volume storage

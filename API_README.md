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
  "version": "1.0",
  "dashboard": "/",
  "endpoints": {
    "health": "/api/health",
    "all_rivers": "/api/river-levels",
    "by_site_id": "/api/river-levels/{site_id}",
    "by_name": "/api/river-levels/name/{name}"
  },
  "examples": {
    "little_river": "/api/river-levels/02399200",
    "little_river_by_name": "/api/river-levels/name/little",
    "locust_fork": "/api/river-levels/02455000"
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

| Site ID | Name | Measurement |
|---------|------|-------------|
| 02455000 | Locust Fork | Stage (ft) |
| 03572900 | Town Creek | Stage (ft) |
| 03572690 | South Sauty | Stage (ft) |
| 03518500 | Tellico River | Stage (ft) |
| 02399200 | Little River | Flow (cfs) |
| streambeam:1 | Short Creek | Stage (ft) |

## Data Update Frequency

River data is refreshed every 60 seconds by the background worker. API responses are served from the cached `gauges.json` file.

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
│  - Fetches NWS weather/QPF data         │
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

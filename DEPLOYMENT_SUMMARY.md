# USGS River Levels - Deployment Summary

**Last Updated**: December 15, 2025
**Production URL**: https://docker-blue-sound-1751.fly.dev/
**Status**: ✅ Fully Operational

---

## Quick Access Links

| Resource | URL |
|----------|-----|
| **Dashboard** | https://docker-blue-sound-1751.fly.dev/ |
| **API Info** | https://docker-blue-sound-1751.fly.dev/api |
| **Health Check** | https://docker-blue-sound-1751.fly.dev/api/health |
| **Little River API** | https://docker-blue-sound-1751.fly.dev/api/river-levels/02399200 |
| **All Rivers API** | https://docker-blue-sound-1751.fly.dev/api/river-levels |

---

## Current Architecture

### System Components

```
┌──────────────────────────────────────────────────┐
│  Fly.io Cloud (docker-blue-sound-1751)          │
│  - Region: iad (US East)                         │
│  - VM: 512MB RAM, 1 shared CPU                   │
│  - Storage: Persistent volume at /data           │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│  Container: Containerfile.api.simple             │
│  - Base: Ubuntu 22.04                            │
│  - Entrypoint: entrypoint-api.sh                 │
│  - Port: 8080 (internal)                         │
└──────────────────────────────────────────────────┘
                      ↓
        ┌─────────────┴─────────────┐
        ↓                           ↓
┌────────────────┐          ┌───────────────┐
│ Background     │          │ Flask API     │
│ Worker         │          │ Server        │
│ (every 60s)    │          │ (port 8080)   │
└────────────────┘          └───────────────┘
        ↓                           ↓
    Generates:               Serves:
    - gauges.json            - Dashboard (/)
    - index.html             - API (/api/*)
    - site_*.html            - JSON data
```

---

## Features

### ✨ Web Dashboard Features
- **Real-time Updates**: Refreshes every 60 seconds
- **Color-Coded Rivers**: Multi-level classification for Little River Canyon
- **Visual Alerts**: Temperature < 55°F (blue), Wind > 10mph (yellow)
- **Trend Indicators**: 8-hour rising/falling/steady analysis
- **Historical Charts**: 7-day sparkline graphs
- **Detail Pages**: Individual river pages with Chart.js visualizations
- **Weather Integration**: Temperature and wind from NWS observations
- **Precipitation Forecast**: 3-day QPF data from NWS

### 🔌 API Features
- **REST Endpoints**: JSON data for all monitored rivers
- **ESP32 Optimized**: 5-line display format for OLED screens
- **CORS Enabled**: Accessible from web applications
- **Fast Responses**: ~10ms (reads from cached JSON)
- **Health Checks**: Built-in health monitoring
- **Search by Name**: Case-insensitive partial matching

---

## Monitored Rivers

| Site ID | Name | Measurement | Location | Min Threshold |
|---------|------|-------------|----------|---------------|
| 02455000 | Locust Fork | Stage | AL | 1.70 ft |
| 03572900 | Town Creek | Stage | AL | 2.00 ft |
| 03572690 | South Sauty | Stage | AL | 8.34 ft |
| 03518500 | Tellico River | Stage | TN | 1.70 ft |
| 02399200 | Little River Canyon | Flow | AL | 300 cfs |
| streambeam:1 | Short Creek | Stage | AL | 0.5 ft |

---

## Configuration

### fly.toml
```toml
app = 'docker-blue-sound-1751'
primary_region = 'iad'

[build]
  dockerfile = "Containerfile.api.simple"

[env]
  RUN_INTERVAL_SEC = "60"
  NWS_UA = "mdchansl-usgs-alert/1.0"
  QPF_TTL_HOURS = "3"
  QPF_CACHE = "/data/qpf_cache.sqlite"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1

[mounts]
  source = "usgs_data"
  destination = "/data"

[[vm]]
  memory = '512mb'
  cpu_kind = 'shared'
  cpus = 1
```

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `RUN_INTERVAL_SEC` | 60 | Data refresh interval |
| `NWS_UA` | mdchansl-usgs-alert/1.0 | NWS API User-Agent |
| `NWS_CONTACT` | michael.chanslor@gmail.com | NWS API contact |
| `QPF_TTL_HOURS` | 3 | QPF cache duration |
| `QPF_CACHE` | /data/qpf_cache.sqlite | QPF cache location |
| `CONFIG_PATH` | /app/gauges.conf.json | Config file path |
| `SITE_DIR` | /site | Output directory |
| `PORT` | 8080 | Flask server port |

---

## Deployment Process

### Production Deployment (Fly.io)

```bash
# Navigate to project directory
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker

# Deploy to Fly.io (uses local Docker/Podman)
fly deploy --local-only

# Monitor deployment
fly status

# View logs
fly logs

# Check health
curl https://docker-blue-sound-1751.fly.dev/api/health
```

#### Rollback Process

```bash
# List previous releases
fly releases

# Rollback to previous version
fly releases rollback <version>
```

---

### Local Deployment (Systemd)

For auto-start on boot using Podman Quadlet:

**1. Create systemd unit file**:
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

EnvironmentFile=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/.env_creds

Environment=BIND_HOST=0.0.0.0
Environment=RUN_INTERVAL_SEC=60
Environment=QPF_TTL_HOURS=3
Environment=QPF_CACHE=/data/qpf_cache.sqlite
Environment=SITE_DIR=/site
Environment=PORT=8080
Environment=NWS_UA=mdchansl-usgs-alert/1.0
Environment=NWS_CONTACT=michael.chanslor@gmail.com

Volume=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data:/data:Z
Volume=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-site:/site:Z

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=default.target
EOF
```

**2. Build the image**:
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
podman build -f Containerfile.api.simple -t usgs-api:latest .
```

**3. Enable and start**:
```bash
systemctl --user daemon-reload
systemctl --user enable --now usgs-alert.service
loginctl enable-linger "$USER"
```

**4. Verify**:
```bash
systemctl --user status usgs-alert.service
```

**5. Access**:
- Find your IP: `ip addr show | grep "inet "`
- Dashboard: http://YOUR_IP:8080/
- API: http://YOUR_IP:8080/api

**Note**: Use your machine's IP address (not `localhost`) for reliable access.

#### Service Management

```bash
# View logs
journalctl --user -u usgs-alert.service -f

# Restart service
systemctl --user restart usgs-alert.service

# Stop service
systemctl --user stop usgs-alert.service

# Disable auto-start
systemctl --user disable usgs-alert.service
```

---

## File Structure

```
/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/
├── Core Application
│   ├── usgs_multi_alert.py      # Main monitoring script
│   ├── api_app.py               # Flask REST API server
│   ├── qpf.py                   # NWS precipitation forecast
│   ├── observations.py          # NWS weather observations
│   ├── site_detail.py           # Detail page generator
│   └── streambeam_multi_scrape.py # StreamBeam integration
│
├── Container Configuration
│   ├── Containerfile.api.simple # ⭐ PRODUCTION (Ubuntu + Flask)
│   ├── Containerfile            # Legacy (Alpine, no API)
│   ├── Containerfile.cloud      # Cloud-optimized (Alpine)
│   ├── Containerfile.cloud.api  # Cloud + API (Alpine)
│   ├── Containerfile.ubuntu     # Ubuntu base (no API)
│   ├── entrypoint-api.sh        # ⭐ PRODUCTION entrypoint
│   └── entrypoint.sh            # Legacy entrypoint
│
├── Configuration
│   ├── gauges.conf.cloud.json   # ⭐ PRODUCTION config
│   ├── gauges.conf.json         # Local development config
│   ├── streambeam_sites.conf.json # StreamBeam site config
│   └── fly.toml                 # Fly.io deployment config
│
├── Documentation
│   ├── CLAUDE.md                # Project overview for AI
│   ├── API_README.md            # REST API documentation
│   ├── CONTAINERFILES.md        # Container build guide
│   ├── DEPLOYMENT_SUMMARY.md    # This file
│   ├── README.md                # General project info
│   ├── VALIDATOR_README.md      # Dashboard validator docs
│   └── VALIDATION_QUICKSTART.md # Quick validation guide
│
├── Testing
│   ├── test_visual_indicators.py    # Visual indicator test generator
│   ├── validate_dashboard.py        # Dashboard HTML validator
│   └── demo-validation.sh           # Validation demo script
│
└── Data (runtime/persistent)
    ├── usgs-data/               # SQLite databases (persistent)
    │   ├── state.sqlite         # Alert state tracking
    │   └── qpf_cache.sqlite     # QPF data cache
    │
    └── usgs-site/               # Generated output
        ├── index.html           # Main dashboard
        ├── gauges.json          # API data source
        ├── test_visual_indicators.html # Test page
        └── details/             # Individual river pages
            ├── site_02399200.html
            ├── site_02455000.html
            └── ...
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# API health check
curl https://docker-blue-sound-1751.fly.dev/api/health

# Expected response:
# {"status": "ok", "timestamp": "2025-11-19T20:00:00Z"}
```

### Log Monitoring

```bash
# Real-time logs
fly logs

# Search for errors
fly logs | grep -i error

# Check specific time period
fly logs --since=1h
```

### Resource Usage

```bash
# Check VM status
fly status

# Check machine metrics
fly machine status

# View volume status
fly volumes list
```

### Common Issues

**Issue**: Dashboard shows "Loading..."
- **Cause**: Background worker hasn't completed first run
- **Fix**: Wait 30-60 seconds, refresh page
- **Check**: `fly logs` for "initial run failed"

**Issue**: API returns 503 Service Unavailable
- **Cause**: gauges.json file not generated yet
- **Fix**: Wait for first data refresh cycle
- **Check**: `fly ssh console` → `ls -la /site/gauges.json`

**Issue**: No weather data showing
- **Cause**: NWS_UA or NWS_CONTACT not set
- **Fix**: Set environment variables in fly.toml
- **Check**: Logs for "QPF client initialization failed"

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| **API Response Time** | ~10ms (cached) |
| **Data Refresh Rate** | 60 seconds |
| **Dashboard Load Time** | ~500ms |
| **Container Startup** | ~30 seconds |
| **Memory Usage** | ~150MB (typical) |
| **Image Size** | ~450MB |

---

## Security Considerations

1. **Secrets Management**:
   - SMTP credentials in `gauges.conf.cloud.json`
   - Consider using Fly.io secrets: `fly secrets set KEY=VALUE`

2. **API Rate Limiting**:
   - No rate limiting currently implemented
   - Consider adding Flask-Limiter for production

3. **CORS Policy**:
   - Currently allows all origins
   - Restrict in production if needed

4. **HTTPS**:
   - Enforced by Fly.io (force_https = true)
   - Automatic TLS certificate management

---

## Future Enhancements

- [ ] Add authentication for API endpoints
- [ ] Implement rate limiting
- [ ] Add WebSocket support for real-time updates
- [ ] Create mobile app using API
- [ ] Add more river sites
- [ ] Implement alert notifications via webhook
- [ ] Add Grafana dashboard for metrics
- [ ] Support for additional weather APIs

---

## Support & Troubleshooting

### Documentation
- **API Guide**: See `API_README.md`
- **Container Guide**: See `CONTAINERFILES.md`
- **Validation**: See `VALIDATOR_README.md`

### Logs & Debugging
```bash
# SSH into running container
fly ssh console

# Check generated files
ls -la /site/

# View gauges.json
cat /site/gauges.json | jq

# Check Python processes
ps aux | grep python

# Check Flask logs
tail -f /tmp/flask.log  # if logging to file
```

### Contact
- **Email**: michael.chanslor@gmail.com
- **Project**: USGS Multi-Site River Gauge Alert System
- **Repository**: (add your repo URL here)

---

## Changelog

### 2026-01-05 - Rain Forecast Marquee
- ✅ Added scrolling rain forecast banner at top of main dashboard
- ✅ Appears when any river has >0.25" QPF forecast
- ✅ Shows which rivers have rain and timing (Today, Tomorrow, Day 3)
- ✅ Dark blue gradient with smooth horizontal scroll animation
- ✅ Pauses on hover for easy reading
- ✅ Hidden when no rain is forecast

### 2025-12-15 - Sparkline Threshold-Based Coloring & Drought Monitor
- ✅ Changed sparkline bars to show runnable status instead of rising/falling
- ✅ Green bars = at or above threshold (runnable)
- ✅ Red bars = below threshold (not runnable)
- ✅ CFS-based rivers (Town Creek, Little River Canyon) now use CFS data in sparklines
- ✅ Removed gray "steady" coloring for simpler visual feedback
- ✅ Added US Drought Monitor integration for Alabama rivers
- ✅ New `drought.py` module fetches county-level drought status by FIPS code
- ✅ Drought levels D0-D4 displayed with emoji and color coding:
  - D0: Abnormally Dry (orange `#e89b3c`)
  - D1: Moderate Drought (tan `#fcd37f`)
  - D2: Severe Drought (dark orange `#ffaa00`)
  - D3: Extreme Drought (red `#e60000`)
  - D4: Exceptional Drought (dark red `#730000`)
- ✅ Tellico River (TN) excluded from drought monitoring
- ✅ SQLite caching with 12-hour TTL for drought data
- ✅ FIPS codes added to config: Blount (01009), DeKalb (01049), Marshall (01095)

### 2025-11-19 - Flask API Integration
- ✅ Added Flask REST API (`api_app.py`)
- ✅ Created ESP32-optimized endpoints
- ✅ Moved dashboard from API root to Flask-served HTML
- ✅ Updated to `Containerfile.api.simple`
- ✅ Deployed to production with dual-service architecture
- ✅ Updated all documentation

### 2025-11-01 - Visual Indicators
- ✅ Added multi-level Little River Canyon classification
- ✅ Added temperature alerts (< 55°F)
- ✅ Added wind alerts (> 10 mph)
- ✅ Created test suite generator

### 2025-10-29 - Initial Production Release
- ✅ Basic dashboard deployment
- ✅ USGS data integration
- ✅ NWS QPF integration
- ✅ Email alerts

---

**Status**: 🎉 All systems operational!

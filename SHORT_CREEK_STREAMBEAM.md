# Short Creek StreamBeam Gauge

StreamBeam Site ID: **1**
Location: Short Creek near Hustleville Road, Marshall County, AL
Dashboard: https://www.streambeam.net/Home/Gauge?siteID=1

## Current Configuration (2025-12-30)

```json
{
  "source": "streambeam",
  "streambeam_site_id": "1",
  "streambeam_zero_offset": 22.39,
  "streambeam_floor_at_zero": false,
  "streambeam_min_valid_ft": -5.0,
  "streambeam_max_valid_ft": 30.0,
  "streambeam_max_change_ft": 5.0,
  "name": "Short Creek",
  "min_ft": 0.5,
  "good_ft": 1.0,
  "lat": 34.3580,
  "lon": -86.2950,
  "fips": "01095"
}
```

## How the Offset Works

StreamBeam returns **raw sensor readings** (e.g., 21.85 ft) that need to be converted to actual creek level.

```
Actual Creek Level = Raw StreamBeam Reading - Offset
                   = 21.85 - 22.39
                   = -0.54 ft
```

The offset of **22.39** was determined by matching StreamBeam readings to the visual staff gauge on-site.

## Thresholds

| Level | Threshold | Status |
|-------|-----------|--------|
| Below 0.5 ft | OUT | Not runnable |
| 0.5 - 1.0 ft | IN | Runnable |
| Above 1.0 ft | GOOD | Ideal conditions |

## Known Issues & History

### Issue: Datum Fluctuations

StreamBeam's datum has changed multiple times, causing the offset to become invalid:

| Date | Problem | Solution |
|------|---------|----------|
| 2022-01-06 | StreamBeam shifted datum by 0.47 ft | Offset adjusted |
| 2025-12-30 | Readings showed -22.86 ft (invalid) | Reset offset to 0.0 temporarily |
| 2025-12-30 | Readings showed 21.85 ft raw | Restored offset to 22.39 |

**When readings look wrong**, it's usually because StreamBeam changed their datum again.

### Issue: Database Lock (Fixed 2025-12-30)

The sparkline history wasn't saving due to SQLite database locks. Fixed by sharing the main database connection instead of opening new connections.

### Issue: Intermittent Data

StreamBeam sometimes returns null/missing readings. The system:
1. Validates readings are within [-5.0, 30.0] ft range
2. Caches "last known good" value for fallback
3. Marks stale data with "⚠ stale" indicator

## Sparkline/History Storage

History is stored in SQLite for trend visualization:

**Table:** `streambeam_history` in `/data/state.sqlite`

```sql
CREATE TABLE streambeam_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_name TEXT NOT NULL,
    stage_ft REAL NOT NULL,
    timestamp TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(site_name, timestamp)
);
```

StreamBeam updates approximately every **15 minutes**. The sparkline requires at least 2 data points to display.

## Recalibration Procedure

If readings appear wrong (way too high, way too low, or negative when creek is up):

### Step 1: Get Current Raw Reading
```bash
curl -s "https://www.streambeam.net/Home/Gauge?siteID=1" | grep -oP 'Last Reading: \K[\d.]+'
```

### Step 2: Get Visual Staff Gauge Reading
Go to the creek and read the painted staff gauge near Martling Rd bridge.

### Step 3: Calculate New Offset
```
new_offset = StreamBeam_raw - Visual_gauge_reading
```

Example: If StreamBeam shows 21.85 ft and staff gauge shows -0.54 ft:
```
new_offset = 21.85 - (-0.54) = 22.39
```

### Step 4: Update Configuration

Edit both config files:
- `gauges.conf.json` (local development)
- `gauges.conf.cloud.json` (production)

```json
"streambeam_zero_offset": 22.39,
```

### Step 5: Deploy

**Local:**
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
systemctl --user restart usgs-alert.service
```

**Fly.io:**
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy -a docker-blue-sound-1751 --local-only
```

## Debugging

### Check Current Status
```bash
# Container logs
podman logs systemd-usgs-alert 2>&1 | grep -i "streambeam\|short"

# Database history
podman exec systemd-usgs-alert python3 -c "
import sqlite3
conn = sqlite3.connect('/data/state.sqlite')
for row in conn.execute('SELECT * FROM streambeam_history ORDER BY timestamp DESC LIMIT 10'):
    print(row)
"
```

### Check Raw StreamBeam Response
```bash
curl -s "https://www.streambeam.net/Home/Gauge?siteID=1" | grep -i "reading"
```

### Force History Table Recreation
If the history table is missing or corrupted:
```bash
podman exec systemd-usgs-alert python3 -c "
import sqlite3
conn = sqlite3.connect('/data/state.sqlite')
conn.execute('DROP TABLE IF EXISTS streambeam_history')
conn.execute('''CREATE TABLE streambeam_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_name TEXT NOT NULL,
    stage_ft REAL NOT NULL,
    timestamp TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(site_name, timestamp)
)''')
conn.commit()
print('Table recreated')
"
```

## Weather Stations (PWS)

Short Creek uses these Weather Underground Personal Weather Stations (in priority order):
1. KALGUNTE26 - Guntersville
2. KALALBER97 - Albertville
3. KALALBER66 - Albertville
4. KALALBER69 - Albertville

## Files Reference

| File | Purpose |
|------|---------|
| `streambeam_multi_scrape.py` | Fetches data from StreamBeam website |
| `usgs_multi_alert.py` | Main script with `_save_streambeam_history()` |
| `gauges.conf.json` | Local config with offset settings |
| `gauges.conf.cloud.json` | Production config |
| `short_creek_log.txt` | Debug log of all readings |

## Contact

StreamBeam Gauging: http://www.streambeam.net/#contact
Facebook Messenger: https://www.messenger.com/t/StreamBeamGauging

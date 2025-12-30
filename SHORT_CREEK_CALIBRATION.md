# Short Creek StreamBeam Calibration Guide

## Quick Reference

**Current Status**: WORKING - Using raw StreamBeam readings (offset 0.0)
**Last Updated**: 2025-12-30
**StreamBeam Site**: https://www.streambeam.net/Home/Gauge?siteID=1

---

## Current Configuration

### gauges.conf.cloud.json (Production)
```json
{
  "source": "streambeam",
  "streambeam_site_id": "1",
  "streambeam_zero_offset": 0.0,
  "streambeam_floor_at_zero": false,
  "streambeam_min_valid_ft": -5.0,
  "streambeam_max_valid_ft": 15.0,
  "streambeam_max_change_ft": 5.0,
  "name": "Short Creek",
  "min_ft": 0.5,
  "good_ft": 1.0,
  "min_cfs": null,
  "lat": 34.3580,
  "lon": -86.2950,
  "fips": "01095"
}
```

### gauges.conf.json (Local Dev)
```json
{
  "source": "streambeam",
  "streambeam_site_id": "1",
  "streambeam_zero_offset": 0.0,
  "streambeam_floor_at_zero": false,
  "streambeam_min_valid_ft": -5.0,
  "streambeam_max_valid_ft": 15.0,
  "streambeam_max_change_ft": 5.0,
  "name": "Short Creek",
  "min_ft": 0.5,
  "good_ft": 1.0,
  "min_cfs": null,
  "lat": 34.3580,
  "lon": -86.2950,
  "fips": "01095"
}
```

---

## What Happened on 2025-12-30

### Issue
Short Creek was completely missing from the dashboard/API. Logs showed:
```
[ERROR] StreamBeam reading -22.86 ft is outside valid range [-5.0, 15.0] - rejecting as bad data
[WARN] No last known good value for Short Creek, skipping
```

### Root Cause
The `streambeam_zero_offset` was set to `22.39`, but StreamBeam's datum had changed. Raw readings were near `0` (e.g., `-0.47 ft`), and subtracting `22.39` produced `-22.86 ft` which failed validation.

### Fix Applied
1. Changed `streambeam_zero_offset` from `22.39` to `0.0` in both config files
2. Added StreamBeam history storage for sparkline/trend data support

### New Feature: StreamBeam History Storage
StreamBeam readings are now stored in SQLite for sparkline visualization:
- Table: `streambeam_history` in `/data/state.sqlite`
- Each unique reading (by timestamp) is stored
- `_get_streambeam_trend_data()` fetches recent readings for sparklines
- Sparklines populate over time as StreamBeam provides new readings (~15 min intervals)

---

## Background: What Happened on 2025-11-25

### Timeline:
1. **Initial State**: Offset was `21.85 ft`, which made StreamBeam's 21.85 reading show as 0.0 ft
2. **Goal**: Reset to see raw readings for proper calibration after rain
3. **Issue Discovered**: StreamBeam developer doing data conversions
4. **Readings During Conversion**:
   - Browser: 21.85 ft at 11:00 AM CST
   - Our scraper: -9.23 ft at 10:45 AM CST
   - Inconsistency due to caching/server-side conversions in progress

### Decision:
- Leave offset at 0.0 and floor at false
- Monitor for 24-48 hours until StreamBeam conversions stabilize
- Then go on-site to calibrate properly

---

## How to Calibrate (When Ready)

### Step 1: Wait for Stability
Monitor the StreamBeam website and your dashboard for consistent readings over 24-48 hours.

**Check these URLs:**
- StreamBeam: https://www.streambeam.net/Home/Gauge?siteID=1
- Your Dashboard: https://docker-blue-sound-1751.fly.dev/
- Your API: https://docker-blue-sound-1751.fly.dev/api/river-levels/name/short

### Step 2: Go On-Site
Bring:
- Smartphone/device to check StreamBeam website
- Notebook to record measurements
- Staff gauge or known reference point

### Step 3: Record Measurements
At the exact same time, record:
1. **StreamBeam Reading**: What the website shows (e.g., 21.85 ft)
2. **Actual Creek Level**: What your staff gauge/reference shows (e.g., 0.5 ft)

### Step 4: Calculate Offset
```
offset = StreamBeam_reading - Actual_level

Example:
StreamBeam shows: 21.85 ft
Staff gauge shows: 0.5 ft
Offset = 21.85 - 0.5 = 21.35 ft
```

### Step 5: Update Configuration Files

Edit **both** files:
- `gauges.conf.json` (local)
- `gauges.conf.cloud.json` (production)

Update the Short Creek section:
```json
{
  "source": "streambeam",
  "streambeam_site_id": "1",
  "streambeam_zero_offset": 21.35,     # ← Your calculated offset
  "streambeam_floor_at_zero": true,    # ← Set to true to prevent negatives
  "name": "Short Creek",
  "min_ft": 0.5,
  "min_cfs": null,
  "lat": 34.3580,
  "lon": -86.2950
}
```

### Step 6: Deploy to Production
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy -a docker-blue-sound-1751 --local-only
```

### Step 7: Verify
Wait 60 seconds (one refresh cycle), then check:
```bash
# Check dashboard
open https://docker-blue-sound-1751.fly.dev/

# Check API
curl https://docker-blue-sound-1751.fly.dev/api/river-levels/name/short | jq '.stage_ft'
```

Should now show the calibrated reading that matches your staff gauge!

---

## Understanding the Math

### How the Offset Works:
```
Adjusted_Reading = Raw_StreamBeam_Reading - Offset

Example with offset = 21.35:
- StreamBeam shows 21.85 ft → Dashboard shows 0.5 ft (21.85 - 21.35)
- StreamBeam shows 22.85 ft → Dashboard shows 1.5 ft (22.85 - 21.35)
- StreamBeam shows 20.85 ft → Dashboard shows -0.5 ft (would be floored to 0.0 if floor_at_zero=true)
```

### Floor at Zero:
- `true`: Prevents negative readings (e.g., -0.5 becomes 0.0)
- `false`: Allows negative readings for debugging

---

## Command-Line Monitoring Tool

A dedicated monitoring script is available: **`short_creek_monitor.sh`**

### Quick Start:
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker

# Show current reading
./short_creek_monitor.sh

# Compare all data sources
./short_creek_monitor.sh compare

# Continuously monitor (every 60 seconds)
./short_creek_monitor.sh monitor

# Monitor every 30 seconds
./short_creek_monitor.sh monitor 30

# Log reading to file
./short_creek_monitor.sh log

# Show all available commands
./short_creek_monitor.sh help
```

### Example Output:
```
==================================================
    SHORT CREEK GAUGE MONITOR
==================================================

📊 CURRENT READING (Production API):
--------------------------------------------------
Site:      Short Creek
Stage:     21.85 ft
Flow:      N/A
Trend:     -> None
In Range:  true
Timestamp: 2025-11-25T11:00:00-06:00

Weather:
  Temp:    N/A
  Wind:    16.6 mph S

Rainfall Forecast (QPF):
  Today:    0.78"
  Tomorrow: 0.0"
  Day 3:    0.0"

💾 LOCAL STATE DATABASE:
--------------------------------------------------
Site ID          Last Stage    Last Timestamp             In Range
---------------  ------------  -------------------------  --------
1                0.00          2025-11-05T07:14:00-06:00  NO
```

### Automated Logging:
To track readings over time, set up a cron job:
```bash
# Edit crontab
crontab -e

# Add this line to log every 15 minutes
*/15 * * * * cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker && ./short_creek_monitor.sh log >> /tmp/short_creek_cron.log 2>&1
```

This creates a log file (`short_creek_log.txt`) with timestamped readings you can analyze later.

---

## Monitoring Tips

### Watch for Changes:
During the next 24-48 hours, note if StreamBeam readings:
- Stay constant (good - gauge is stable)
- Jump suddenly (bad - conversion still in progress)
- Gradually increase with rain (good - gauge working correctly)

### What You're Looking For:
With rain coming to the Southeast, you should see:
1. StreamBeam reading gradually **increase** as water rises
2. Your dashboard showing the **same trend** (since offset is 0.0)
3. No sudden jumps or negative values

### Red Flags:
- Reading jumps by >5 ft suddenly (conversion issue)
- Reading goes negative and stays there (datum shift)
- Reading stops updating for >2 hours (connectivity issue)

---

## Historical Context

### Original Offset (21.85 ft):
This was likely set when:
- Creek was at "zero" (dry or very low)
- StreamBeam showed 21.85 ft
- Someone wanted dashboard to show 0.0 ft for that condition

### After StreamBeam Conversions:
This offset may no longer be valid. The new zero point might be different.

**That's why we're resetting to 0.0 and recalibrating from scratch.**

---

## Troubleshooting

### "Dashboard still shows old reading after deploy"
Wait 60 seconds for the background worker to refresh data.

### "Scraper getting different value than browser"
Check:
1. Caching - Clear browser cache, check in incognito
2. Timing - Compare timestamps (API might be older)
3. Conversion in progress - Wait 24 hours

### "Negative readings on dashboard"
This is expected with offset=0.0 and floor=false during monitoring phase.
After calibration, set `floor_at_zero: true` to prevent this.

### "Need to revert to old offset"
```json
"streambeam_zero_offset": 21.85,
"streambeam_floor_at_zero": true
```
Then redeploy.

---

## Contact

If StreamBeam gauge has issues, contact StreamBeam developer directly.
Gauge page: https://www.streambeam.net/Home/Gauge?siteID=1

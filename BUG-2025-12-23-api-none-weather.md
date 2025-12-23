# BUG: API /api/river-levels returning 500 Internal Server Error

**Date Discovered:** 2025-12-23
**Date Fixed:** 2025-12-23
**Severity:** High (broke ESP32 data feed)
**Affected Endpoint:** `/api/river-levels`

## Symptoms

- ESP32 external LED display stopped receiving API data
- `/api/river-levels` endpoint returned HTTP 500 Internal Server Error
- Individual river endpoints like `/api/river-levels/02399200` still worked
- `/api/health` still returned OK

## Root Cause

In `api_app.py` line 138, the `format_for_display()` function built the weather display line with this code:

```python
f"Max:{temp_f:.0f}F Wind:{wind_mph:.1f} {wind_dir}" if temp_f else "Weather: N/A"
```

The condition only checked if `temp_f` was truthy before attempting to format. However, `wind_mph` could also be `None` for some sites (particularly TVA dam sites like Hiwassee Dries or Ocoee dams when weather station data was unavailable).

When Python tried to format `None` with `.1f`, it threw:
```
TypeError: unsupported format string passed to NoneType.__format__
```

This crashed the entire `/api/river-levels` endpoint because it iterates through ALL sites and formats each one. A single site with `None` weather data broke the entire response.

## Why Individual Endpoints Still Worked

The individual river endpoint `/api/river-levels/{site_id}` worked because it only formatted ONE site. If that specific site had valid weather data, it succeeded. The bug only manifested when iterating through all 12 sites, where at least one had `None` for `wind_mph`.

## The Fix

Changed line 138 in `api_app.py` from:

```python
f"Max:{temp_f:.0f}F Wind:{wind_mph:.1f} {wind_dir}" if temp_f else "Weather: N/A"
```

To:

```python
f"Max:{temp_f:.0f}F Wind:{wind_mph:.1f} {wind_dir}" if (temp_f is not None and wind_mph is not None and wind_dir) else "Weather: N/A"
```

This ensures ALL three weather values are present before attempting to format the string.

## Verification

After deploying the fix:

| Endpoint | Before Fix | After Fix |
|----------|------------|-----------|
| `/api/health` | 200 OK | 200 OK |
| `/api/river-levels` | 500 Error | 200 OK (12 sites) |
| `/api/river-levels/02399200` | 200 OK | 200 OK |
| `/api/river-levels/name/short` | 200 OK | 200 OK |

## Lessons Learned

1. When formatting multiple optional values in a single f-string, check ALL values, not just one
2. The `/api/river-levels` endpoint should have better error handling to return partial data if one site fails
3. Consider adding a try/except around `format_for_display()` to gracefully handle individual site failures

## Files Modified

- `api_app.py` - Line 138, added null checks for wind_mph and wind_dir

## Deployment

```bash
/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/deploy.sh
```

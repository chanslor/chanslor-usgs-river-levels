# StreamBeam API Investigation - Short Creek (Site ID 1)

**Date**: 2025-11-25
**Issue**: Discrepancy between scraped data and browser display

---

## Problem Discovery

### What We Observed:
- **Browser shows**: 4.22 ft (current reading)
- **Our scraper gets**: 21.85 ft (stale reading)
- **Difference**: ~17.63 ft

### Root Cause:
StreamBeam developer performed datum conversion on backend, but:
1. ✅ **API endpoint updated** - Shows new converted values
2. ❌ **Static HTML not updated** - Still shows old "Last Reading" text
3. 🔧 **Our scraper** - Reads static HTML via regex, misses the real data

---

## StreamBeam Data Architecture

### Page Structure:
```
https://www.streambeam.net/Home/Gauge?siteID=1
│
├── Static HTML (Server-side rendered)
│   └── "Last Reading: 21.85 ft at 2025-11-25 11:15 AM CST"  ← OLD DATA (stale)
│
└── JavaScript (Client-side loaded)
    └── AJAX call to: /Gauge/GetGauge72HourLevelData?siteID=1  ← REAL DATA (current)
```

### How Browsers See Current Data:
1. Browser loads page HTML
2. JavaScript executes
3. AJAX call to `/Gauge/GetGauge72HourLevelData?siteID=1`
4. Response updates page with real-time data
5. User sees **4.22 ft** (from API)

### How Our Scraper Sees Stale Data:
1. Scraper fetches HTML
2. Regex searches for "Last Reading: X.XX ft"
3. Finds static HTML text: **21.85 ft**
4. Returns stale value
5. Never executes JavaScript or calls API

---

## StreamBeam API Endpoint

### Endpoint URL:
```
https://www.streambeam.net/Gauge/GetGauge72HourLevelData?siteID=1
```

### Response Format:
```json
{
  "xData": [
    "2025-11-22T14:30",
    "2025-11-22T14:45",
    ...
    "2025-11-24T22:00"
  ],
  "datasets": [
    {
      "name": "Level",
      "data": [
        3.84,
        3.85,
        ...
        4.22
      ],
      "unit": "ft",
      "type": "area",
      "valueDecimals": 2
    }
  ]
}
```

### Latest Reading Extraction:
```python
# Last element in data array = most recent reading
latest_reading = response["datasets"][0]["data"][-1]
latest_timestamp = response["xData"][-1]

# Example:
# latest_reading = 4.22
# latest_timestamp = "2025-11-24T22:00"
```

---

## Data Conversion Analysis

### Sample Data Points (Nov 22-24, 2025):
```
Timestamp            | Reading (ft)
---------------------+-------------
2025-11-22 14:30    | 3.84
2025-11-22 21:00    | 4.22
2025-11-22 22:15    | 6.74  ← spike (rain event?)
2025-11-23 03:30    | 4.31
2025-11-23 20:30    | 4.34
2025-11-24 20:30    | -2.02 ← anomaly (sensor error?)
2025-11-24 22:00    | 4.22  ← LATEST
```

### Observations:
- **Typical range**: 3.84 - 4.34 ft
- **Spike observed**: 6.74 ft (possible rain event on Nov 22)
- **Anomaly**: -2.02 ft (sensor malfunction or data error)
- **Current stable level**: ~4.22 ft

### Datum Conversion:
```
Old reading (static HTML): 21.85 ft
New reading (API):         4.22 ft
Implied offset applied:   -17.63 ft

This matches the datum shift mentioned on the gauge page:
"The datum for this gauge was shifted by .47ft on 1/6/22"

However, this appears to be a SECOND conversion with much larger offset.
Developer confirmed they are "doing conversions" - likely adjusting
to match a new staff gauge installation or resurvey.
```

---

## Recommended Fix Options

### Option 1: Update Scraper to Use API (RECOMMENDED)
**Pros:**
- Gets real-time data (what browsers see)
- No HTML parsing fragility
- Faster response (direct JSON)
- More reliable timestamps

**Cons:**
- Different URL pattern
- Need to handle JSON parsing
- May break if API changes

**Implementation:**
```python
# In streambeam_multi_scrape.py

API_URL_TMPL = "https://www.streambeam.net/Gauge/GetGauge72HourLevelData?siteID={site_id}"

def fetch_api_data(site_id: str, timeout: int = 25):
    url = API_URL_TMPL.format(site_id=site_id)
    req = urllib.request.Request(url, headers={...})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))

    # Extract latest reading
    latest_value = data["datasets"][0]["data"][-1]
    latest_timestamp = data["xData"][-1]

    return {
        "raw_value_ft": latest_value,
        "observed_at_local": format_timestamp(latest_timestamp),
        "units": "ft"
    }
```

### Option 2: Wait for StreamBeam to Fix Static HTML
**Pros:**
- No code changes needed
- Scraper keeps working as-is

**Cons:**
- Unknown timeline (could be days/weeks)
- Data will be stale until fixed
- Developer may never update static text if dynamic load works

### Option 3: Hybrid Approach
Try API first, fall back to HTML scraping if API fails.

---

## Action Items

### Immediate (Do Now):
1. ✅ Document the issue (this file)
2. ⏳ Wait 24-48 hours to see if static HTML gets updated
3. ⏳ Monitor API endpoint for stability

### Short Term (Within Week):
1. ⬜ Update `streambeam_multi_scrape.py` to use API endpoint
2. ⬜ Add fallback to HTML scraping for resilience
3. ⬜ Test with Short Creek (site_id=1)
4. ⬜ Deploy to production

### Long Term (Future):
1. ⬜ Check if other StreamBeam gauges need API approach
2. ⬜ Consider caching API responses (they update every 15min typically)
3. ⬜ Add error handling for anomalous readings (like -2.02 ft)

---

## Testing Plan

### Verify API Endpoint:
```bash
# Test API directly
curl -s "https://www.streambeam.net/Gauge/GetGauge72HourLevelData?siteID=1" | jq '.'

# Extract latest reading
curl -s "https://www.streambeam.net/Gauge/GetGauge72HourLevelData?siteID=1" | \
  jq -r '.datasets[0].data[-1]'

# Extract latest timestamp
curl -s "https://www.streambeam.net/Gauge/GetGauge72HourLevelData?siteID=1" | \
  jq -r '.xData[-1]'
```

### Compare Sources:
```bash
# Use monitoring tool
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
./short_creek_monitor.sh compare
```

---

## Reference Links

- StreamBeam Gauge Page: https://www.streambeam.net/Home/Gauge?siteID=1
- StreamBeam API Endpoint: https://www.streambeam.net/Gauge/GetGauge72HourLevelData?siteID=1
- Production Dashboard: https://docker-blue-sound-1751.fly.dev/
- Production API: https://docker-blue-sound-1751.fly.dev/api/river-levels/name/short

---

## Notes

- StreamBeam developer confirmed conversions are in progress (2025-11-25)
- Static HTML last updated: 2025-11-25 11:15 AM CST (shows 21.85 ft)
- API last updated: 2025-11-24 22:00 (shows 4.22 ft)
- Time gap suggests API is updating but HTML generation script is broken or disabled
- Rain forecast today: 0.78" - good opportunity to verify gauge is working with new datum

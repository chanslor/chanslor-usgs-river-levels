# Ocoee River TVA API Research

**Research Date:** 2025-12-21
**Status:** COMPLETE - All three Ocoee dams integrated into production dashboard!
**Production URL:** https://docker-blue-sound-1751.fly.dev/

## Executive Summary

The **TVA REST API WORKS** for all three Ocoee dams using the same pattern as Hiwassee (HADT1). Real-time discharge (CFS), pool elevation, and tailwater elevation are available.

| Dam | Site Code | API Status | Current CFS |
|-----|-----------|------------|-------------|
| Ocoee #3 (Upper) | **OCCT1** | ✅ Working | 1,081 |
| Ocoee #2 (Middle) | **OCBT1** | ✅ Working | 1,071 |
| Ocoee #1 (Parksville) | **OCAT1** | ✅ Working | 713 |

---

## TVA API Endpoints

### Ocoee #3 (Upper Dam) - OCCT1

**Location:** Upper Ocoee, above flume
**API Endpoint:**
```
https://www.tva.com/RestApi/observed-data/OCCT1.json
```

**Sample Response:**
```json
{
    "Day": "12/21/2025",
    "Time": "7 PM EST",
    "ReservoirElevation": "1,432.10",
    "TailwaterElevation": "1,118.50",
    "AverageHourlyDischarge": "1,081"
}
```

**Data Available:**
- ReservoirElevation (ft) - pool level above dam
- TailwaterElevation (ft) - water level below dam
- AverageHourlyDischarge (CFS) - release rate

---

### Ocoee #2 (Middle Dam) - OCBT1 ⭐ YOUR PUT-IN

**Location:** Middle Ocoee, the main whitewater section
**API Endpoint:**
```
https://www.tva.com/RestApi/observed-data/OCBT1.json
```

**Sample Response:**
```json
{
    "Day": "12/21/2025",
    "Time": "7 PM EST",
    "ReservoirElevation": "1,096.09",
    "TailwaterElevation": "842.21",
    "AverageHourlyDischarge": "1,071"
}
```

**Typical Recreation Releases:**
- Standard release: **1,250 CFS** (scheduled whitewater releases)
- Current reading shows active release of ~1,071 CFS

---

### Ocoee #1 (Parksville Dam) - OCAT1

**Location:** Lower Ocoee, Parksville Reservoir
**API Endpoint:**
```
https://www.tva.com/RestApi/observed-data/OCAT1.json
```

**Sample Response:**
```json
{
    "Day": "12/21/2025",
    "Time": "7 PM EST",
    "ReservoirElevation": "828.05",
    "TailwaterElevation": "714.98",
    "AverageHourlyDischarge": "713"
}
```

---

## Integration with River Gauge System (COMPLETED)

All three Ocoee dams have been added to the dashboard:

### Configuration in `gauges.conf.cloud.json`:
```json
{
    "source": "tva",
    "tva_site_code": "OCBT1",
    "name": "Ocoee #2 (Middle)",
    "include_discharge": true,
    "min_cfs": 1000,
    "good_cfs": 1250,
    "lat": 35.093,
    "lon": -84.510
}
```

### Modified Files:
- `tva_fetch.py` - Added TVA_SITES entries and TVA_DISPLAY_CONFIG for site-specific text
- `pws_observations.py` - Added PWS station fallback chains
- `site_detail.py` - Added get_location_links() for map links
- `usgs_multi_alert.py` - Added tva_urls for correct TVA page links

### PWS Weather Stations for Ocoee:
- KTNBENTO3 (Benton, TN) - primary
- KNCMURPH4 (Murphy, NC)
- KTNCLEVE20 (Cleveland, TN)

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  TVA REST API                                           │
│  https://www.tva.com/RestApi/observed-data/*.json       │
└─────────────────────────────────────────────────────────┘
          │
          ├── OCCT1 → Ocoee #3 (Upper Dam)
          │           Pool: ~1,432 ft | CFS: 0-1,200
          │
          ├── OCBT1 → Ocoee #2 (Middle Dam) ← YOUR PUT-IN
          │           Pool: ~1,096 ft | CFS: 0-1,500+
          │
          └── OCAT1 → Ocoee #1 (Parksville)
                      Pool: ~828 ft | CFS: varies
```

---

## Release Pattern (from today's data)

Looking at today's (12/21/2025) data, the release pattern shows:

| Time | Ocoee #3 | Ocoee #2 | Ocoee #1 |
|------|----------|----------|----------|
| Noon | 0 cfs | 79 cfs | 6 cfs |
| 1 PM | 0 cfs | 79 cfs | 0 cfs |
| 2 PM | 0 cfs | 76 cfs | 5 cfs |
| 3 PM | 0 cfs | 76 cfs | 593 cfs |
| 4 PM | 0 cfs | 74 cfs | 0 cfs |
| 5 PM | 11 cfs | 74 cfs | 0 cfs |
| 6 PM | 1,079 cfs | 483 cfs | 8 cfs |
| 7 PM | 1,081 cfs | 1,071 cfs | 713 cfs |

**Observation:** Releases cascade down - #3 starts, then #2 follows, then #1

---

## Comparison to Hiwassee

| Feature | Hiwassee (HADT1) | Ocoee #2 (OCBT1) |
|---------|------------------|------------------|
| API Pattern | Same | Same |
| CFS Available | ✅ Yes | ✅ Yes |
| Pool Elevation | ✅ Yes | ✅ Yes |
| Tailwater Elevation | ✅ Yes | ✅ Yes |
| Update Frequency | Hourly | Hourly |
| Integration Effort | Reference | Identical |

---

## Additional USGS/NOAA Gauges

For supplementary data:

| Gauge | Location | Data | API |
|-------|----------|------|-----|
| CPHT1 / USGS 03559500 | Copperhill (upstream) | Stage + CFS | NOAA/USGS |
| OCET1 | Below all dams | Stage only | NOAA |

---

## References

- [TVA Ocoee 1 Lake Info](https://www.tva.com/environment/lake-levels/ocoee-1)
- [TVA Ocoee 2 Lake Info](https://www.tva.com/environment/lake-levels/ocoee-2)
- [TVA Ocoee 3 Lake Info](https://www.tva.com/environment/lake-levels/ocoee-3)
- [TVA Recreation Release Calendar](https://www.tva.com/environment/lake-levels/ocoee-2/recreation-release-calendar)
- [American Whitewater - Ocoee](https://www.americanwhitewater.org/content/River/detail/id/1780)

---

## Conclusion

**Integration Complete!** All three Ocoee dams are now live in production:

| Dam | Site Code | Detail Page |
|-----|-----------|-------------|
| Ocoee #3 (Upper) | OCCT1 | [OCCT1.html](https://docker-blue-sound-1751.fly.dev/details/OCCT1.html) |
| Ocoee #2 (Middle) | OCBT1 | [OCBT1.html](https://docker-blue-sound-1751.fly.dev/details/OCBT1.html) |
| Ocoee #1 (Lower) | OCAT1 | [OCAT1.html](https://docker-blue-sound-1751.fly.dev/details/OCAT1.html) |

**Features:**
- Real-time CFS, pool elevation, tailwater elevation
- 12-hour trend sparklines on main dashboard
- Full detail pages with 3-day forecast panels
- Historical data stored indefinitely in SQLite
- PWS weather from Benton/Murphy/Cleveland stations
- **NEW: Cascade Correlation Page** - See all 3 dams together

---

## Ocoee Cascade Correlation Page (NEW - 2025-12-23)

A dedicated visualization page showing the relationship between all 3 Ocoee dams, visualizing how water cascades downstream during heavy rain or scheduled releases.

**Live Page:** [ocoee-cascade.html](https://docker-blue-sound-1751.fly.dev/details/ocoee-cascade.html)

### Water Flow Direction
```
OCCT1 (Ocoee #3 - Upper)   [Red]
    ↓ water flows downstream
OCBT1 (Ocoee #2 - Middle)  [Yellow]  ← YOUR PUT-IN
    ↓
OCAT1 (Ocoee #1 - Lower)   [Green]
```

### Visualization Views

The cascade page includes **THREE** visualization modes accessible via tab navigation:

| View | Description |
|------|-------------|
| **Overlapping Lines** | All 3 dams' data as separate colored lines on one chart - easy to see when one dam spikes and how it affects downstream |
| **Multi-Panel Synced** | 3 stacked rows (one per dam) with synchronized time axis - cleaner separation, easier to read individual dams |
| **Full Metrics** | Discharge + Pool elevation + Tailwater on dual axes - complete picture of dam operations |

### Data Displayed

All three metrics available from TVA:
- **Discharge (CFS)** - Water release rate
- **Pool Elevation (ft)** - Lake level behind dam
- **Tailwater (ft)** - Water level below dam (rises when spillway runs)

### API Endpoint

```bash
# Get combined data for all 3 Ocoee dams
curl "https://docker-blue-sound-1751.fly.dev/api/tva-history/ocoee/combined?days=7"
```

Returns combined observations, stats, and date range for all 3 sites in a single request.

### Implementation Files

| File | Description |
|------|-------------|
| `ocoee_correlation.py` | Page generator module (~700 lines) |
| `api_app.py` | Combined endpoint `/api/tva-history/ocoee/combined` |
| `tva_fetch.py` | Added link to cascade page from individual dam pages |
| `usgs_multi_alert.py` | Generates cascade page and passes pool/tailwater data |

### Navigation

Each Ocoee detail page (OCCT1, OCBT1, OCAT1) has a link at the bottom:
> 📊 **View All 3 Ocoee Dams Together** → See the cascade correlation between Upper, Middle, and Lower Ocoee

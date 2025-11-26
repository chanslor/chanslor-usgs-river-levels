# Short Creek On-Site Calibration Guide

**Date**: 2025-11-25
**Status**: Ready for on-site inspection

---

## Current Situation

### What We Know:
1. **Our scraper reads**: 21.85 ft (from StreamBeam static HTML)
2. **Browser shows**: 4.22 ft (from StreamBeam dynamic API)
3. **Difference**: ~17.63 ft (StreamBeam applied datum conversion)

### Decision:
✅ **Keep scraper as-is** (reading 21.85 ft from HTML)
✅ **Visual inspection on-site** to determine proper offset
✅ **Then apply single offset** to get accurate readings

---

## On-Site Calibration Checklist

### What to Bring:
- [ ] Smartphone/device to check StreamBeam website
- [ ] Notebook and pen for measurements
- [ ] Camera for photos (optional but helpful)
- [ ] This guide (printed or on phone)

### At the Gauge Location:

#### Step 1: Check Staff Gauge
- [ ] Locate the visual staff gauge (painted markings)
- [ ] Read the current water level: **______ ft**
- [ ] Take photo of staff gauge reading

#### Step 2: Check StreamBeam Website
- [ ] Open: https://www.streambeam.net/Home/Gauge?siteID=1
- [ ] Note the reading shown in browser: **______ ft**
- [ ] Note the timestamp: **____________**

#### Step 3: Check Our Dashboard
- [ ] Open: https://docker-blue-sound-1751.fly.dev/
- [ ] Note Short Creek reading: **______ ft**
- [ ] Note the timestamp: **____________**

#### Step 4: Record All Three Values

| Source | Reading | Time | Notes |
|--------|---------|------|-------|
| Staff Gauge (actual) | _____ ft | _____ | Ground truth |
| StreamBeam Browser | _____ ft | _____ | What users see |
| Our Dashboard | _____ ft | _____ | What we scrape |

---

## Calculation Worksheet

### Scenario A: Use Staff Gauge as Truth
```
Staff Gauge Reading:     _____ ft  (actual water level)
Our Dashboard Shows:     21.85 ft  (what scraper gets)

Offset Calculation:
  offset = Dashboard_reading - Staff_gauge_reading
  offset = 21.85 - _____ = _____ ft

Example:
  If staff gauge shows 0.5 ft:
  offset = 21.85 - 0.5 = 21.35 ft
```

### Scenario B: Use StreamBeam Browser as Truth
```
StreamBeam Browser Shows: _____ ft  (likely 4.22 ft)
Our Dashboard Shows:      21.85 ft  (what scraper gets)

Offset Calculation:
  offset = Dashboard_reading - Browser_reading
  offset = 21.85 - _____ = _____ ft

Example:
  If browser shows 4.22 ft:
  offset = 21.85 - 4.22 = 17.63 ft
```

### Which to Use?

**Recommendation**: Use **Staff Gauge** as the source of truth.

**Why?**
- Physical gauge is the reference standard
- StreamBeam's browser value may have their own offset applied
- Staff gauge = what you see = what kayakers need to know

---

## Reporting Back

### Template Message:
```
Short Creek calibration data:

Staff Gauge:      _____ ft (what I see on painted gauge)
StreamBeam Web:   _____ ft (what browser shows)
Our Dashboard:    21.85 ft (what scraper got)

Calculated offset: _____ ft

Weather conditions: _____________________
Creek appearance: _______________________
Any rain recently: ______________________
```

### Quick Command to Check Current Reading:
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
./short_creek_monitor.sh current
```

---

## After On-Site Inspection

Once you report the measurements, we'll:

1. **Calculate the offset** based on staff gauge reading
2. **Update config files** (both gauges.conf.json and gauges.conf.cloud.json)
3. **Set floor_at_zero** to `true` (prevent negative readings)
4. **Deploy to production**: `fly deploy -a docker-blue-sound-1751 --local-only`
5. **Verify** the dashboard shows accurate readings
6. **Update documentation** with final calibration notes

---

## Known Issues to Watch For

### Issue 1: Static HTML vs Dynamic API
- HTML shows: 21.85 ft (stale)
- API shows: 4.22 ft (current)
- Our scraper uses HTML (by design for now)

**Impact**: If StreamBeam fixes their HTML, our reading might suddenly jump!

**Mitigation**: We'll notice the jump and can recalibrate quickly.

### Issue 2: Datum Conversions
StreamBeam developer said "doing conversions" - they may apply more changes.

**Impact**: Readings could shift again.

**Mitigation**: We're recording today's calibration so we can detect future changes.

### Issue 3: Sensor Anomalies
API showed -2.02 ft reading on Nov 24 (sensor glitch).

**Impact**: Occasional bad readings possible.

**Mitigation**: System already has threshold logic (min_ft: 0.5) to ignore too-low readings.

---

## Expected Results After Calibration

### If Staff Gauge Shows 0.5 ft:
```
Before calibration:
  Dashboard: 21.85 ft (raw)

After calibration (offset = 21.35):
  Dashboard: 0.5 ft (calibrated)

Alert threshold: 0.5 ft
  Status: IN RANGE (runnable!)
```

### If Staff Gauge Shows 0.2 ft:
```
After calibration (offset = 21.65):
  Dashboard: 0.2 ft (calibrated)

Alert threshold: 0.5 ft
  Status: OUT OF RANGE (too low)
```

---

## Safety Notes

- Check weather before driving out (rain = slippery conditions)
- Watch for creek rise if rain is falling
- Take photos for documentation
- Note any debris or obstructions near gauge

---

## Questions to Answer While There

1. **Does the staff gauge look correct?** (painted clearly, not damaged)
2. **Is the sensor visible?** (ultrasonic sensor should be mounted above water)
3. **Any recent changes?** (new gauge installation, moved sensor, etc.)
4. **Creek condition?** (clear, muddy, debris-filled)
5. **Access difficulty?** (easy to check again in future?)

---

## Contact Info

If you find anything unexpected or have questions while on-site, you can:
- Take detailed photos
- Note exact readings with timestamps
- Check if there are any signs/notes posted at the gauge

---

## Reference

- **Gauge Page**: https://www.streambeam.net/Home/Gauge?siteID=1
- **Our Dashboard**: https://docker-blue-sound-1751.fly.dev/
- **API Investigation**: See STREAMBEAM_API_FINDINGS.md
- **Monitoring Tool**: ./short_creek_monitor.sh

---

## Post-Calibration Documentation

Once calibrated, we'll update:
- ✅ SHORT_CREEK_CALIBRATION.md (mark as calibrated)
- ✅ CLAUDE.md (remove "UNCALIBRATED" warning)
- ✅ Config files (set final offset)
- ✅ Add timestamp and staff gauge reading to permanent record

Drive safe and happy paddling! 🛶

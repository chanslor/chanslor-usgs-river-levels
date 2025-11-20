# River Dashboard Validator - Quick Start 🚀

One-line commands for validating your river gauge dashboard!

## From Your Laptop 💻

### Test Live Deployment
```bash
# Full validation of live site
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev

# Check specific river
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --site "Town Creek"
```

### Test Local File
```bash
# Validate local HTML
python3 validate_dashboard.py usgs-site/index.html
```

## After Deploy Workflow 🔄

```bash
# 1. Deploy
fly deploy

# 2. Wait & validate
sleep 10 && python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev
```

## Quick Checks ✅

```bash
# Is the site up?
curl -I https://docker-blue-sound-1751.fly.dev

# Validate with timeout
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --timeout 60

# Check just one river
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --site "Little River"
```

## What Gets Validated? 📋

✅ River names & USGS links
✅ Water level measurements (feet & CFS)
✅ Timestamps
✅ Sparkline trend charts
✅ Weather data (temp & wind)
✅ **City abbreviations** (ALBVL, HNTSV, etc.) ⭐ NEW!
✅ Rainfall forecasts
✅ Threshold indicators

## Success Criteria 🎯

- **A+ (100%)** = 🎉 Perfect! All features present
- **A (90-99%)** = ⭐ Excellent! Minor optionals missing
- **B (80-89%)** = ✅ Good! Core features working
- **< 80%** = ⚠️ Needs attention

## Common Issues & Fixes 🔧

**Site not responding?**
```bash
fly status  # Check if app is running
fly logs    # Check for errors
```

**Slow connection?**
```bash
python3 validate_dashboard.py https://your-app.fly.dev --timeout 60
```

**Want to test new city labels?**
```bash
# Look for the ⭐ City abbreviation label checkmark!
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev | grep "⭐"
```

---

**Pro Tip:** Bookmark this file and keep validate_dashboard.py on your laptop!
You can test your deployment from anywhere with just one command. 🌊🚣‍♂️

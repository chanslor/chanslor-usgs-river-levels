# River Gauge Dashboard Validator 🌊🔍

A fun, colorful validation tool for testing your river gauge dashboard HTML output!
Supports both **local files** and **remote URLs** - perfect for validating live deployments!
Features emojis, colored checkmarks, and comprehensive data validation.

## Features

✅ **Local & Remote Testing** - Test both local files and live deployments:
- 📁 Local HTML files on your machine
- 🌐 Remote URLs (HTTP/HTTPS) - test your Fly.io, Heroku, or any web deployment
- 🔒 SSL/TLS support for HTTPS
- ⏱️ Configurable timeout for slow connections

✅ **Comprehensive Validation** - Checks all critical data elements:
- 🌊 River names and links
- 📏 Feet measurements
- 💧 CFS (discharge) data
- 🕐 Timestamps
- 📊 12-hour sparkline charts
- 📈 Trend indicators (rising/falling/steady)
- 🌡️💨 Weather observations (temperature & wind)
- ⭐ City abbreviation labels (NEW!)
- 🏔️ Secondary weather stations (valley trend data)
- 🌧️ Rainfall forecasts (QPF)
- 🎯 Threshold information

✨ **Beautiful Output** - Colorful terminal output with:
- ✅ Green checkmarks for passing tests
- ❌ Red crosses for failing tests
- ⚠️ Yellow warnings for optional features
- 🎉 Special celebration emoji for perfect scores
- Letter grades (A+, A, B, C, D)

## Usage

### 🌐 Remote URL Testing (Live Deployments)

Test your live deployment from anywhere! Perfect for validating Fly.io, AWS, Heroku, or any web host:

```bash
# Test your Fly.io deployment
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev

# Test a specific site on your deployment
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --site "Town Creek"

# Test with custom timeout (useful for slow connections)
python3 validate_dashboard.py https://your-app.com --timeout 60

# Quick check from your laptop after deploying
python3 validate_dashboard.py https://your-app.fly.dev
```

### 📁 Local File Testing

```bash
# Basic validation (all sites)
python3 validate_dashboard.py usgs-site/index.html

# Validate a specific site
python3 validate_dashboard.py usgs-site/index.html --site "Town Creek"

# Verbose mode
python3 validate_dashboard.py usgs-site/index.html --verbose

# Disable colors (for CI/CD)
python3 validate_dashboard.py usgs-site/index.html --no-color
```

## Example Output

### Remote URL Testing
```
======================================================================
   🌊 River Gauge Dashboard Validator 🚀
======================================================================

🚀 Fetching remote dashboard from: https://docker-blue-sound-1751.fly.dev
✅ Successfully fetched (HTTP 200)

🚀 Parsing dashboard HTML...

✅ Found 6 sites!

──────────────────────────────────────────────────────────────────────
🌊 Town Creek [in]
──────────────────────────────────────────────────────────────────────
  ✅ 🌊 River name
  ✅ 📏 Feet measurement
  ✅ 🕐 Timestamp
  ✅ 🎯 Threshold info
  ✅ 💧 CFS data (1,250)
  ✅ 📊 12hr Sparkline chart
  ✅ 📈 Trend indicator
  ✅ 🌡️💨 Weather observations
  ✅ ⭐ City abbreviation label
  ✅ 🏔️ Secondary weather (valley)
  ✅ 🌧️ Rainfall forecast (QPF)

  🎉 Score: 11/11 (100%)

======================================================================
📊 Overall Summary
======================================================================

  🎯 Total Sites: 4
  🎉 Perfect Sites: 1/4
  ⭐ Overall Score: 40/44
  📊 Overall Grade: A ⭐ EXCELLENT! (90.9%)

======================================================================
```

## Exit Codes

- **0**: Success (≥80% overall score)
- **1**: Needs improvement (<80% overall score)
- **1**: Error (file not found, parse error, etc.)

## Real-World Usage Examples

### 🚀 Test After Deploying to Fly.io

```bash
# Deploy your app
fly deploy

# Wait a moment for it to start
sleep 5

# Validate the live deployment
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev

# Check specific site
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --site "Little River"
```

### 💻 Development Workflow

```bash
# 1. Make code changes
vim usgs_multi_alert.py

# 2. Test locally
python3 usgs_multi_alert.py --config gauges.conf.json --cfs \
  --dump-html /tmp/test.html --trend-hours 8

# 3. Validate local output
python3 validate_dashboard.py /tmp/test.html

# 4. Deploy to production
fly deploy

# 5. Validate production deployment
python3 validate_dashboard.py https://your-app.fly.dev
```

### 🔄 Scheduled Validation (Cron)

Monitor your live site automatically:

```bash
# Add to crontab (check every hour)
0 * * * * python3 /path/to/validate_dashboard.py https://docker-blue-sound-1751.fly.dev --no-color >> /var/log/river-validation.log 2>&1
```

### 🌐 Test Multiple Deployments

```bash
# Test staging
python3 validate_dashboard.py https://staging-app.fly.dev

# Test production
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev

# Compare results
```

## Integration with CI/CD

Use in automated testing pipelines:

```bash
# Local validation (before deploy)
python3 usgs_multi_alert.py --config gauges.conf.json --cfs \
  --dump-html usgs-site/index.html --trend-hours 8

python3 validate_dashboard.py usgs-site/index.html --no-color

# Deploy
fly deploy

# Remote validation (after deploy)
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --no-color

# Exit code indicates pass/fail
if [ $? -eq 0 ]; then
  echo "✅ Dashboard validation passed!"
else
  echo "❌ Dashboard validation failed!"
  exit 1
fi
```

### GitHub Actions Example

```yaml
name: Validate Dashboard

on:
  push:
    branches: [ main ]
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Validate Live Dashboard
        run: |
          python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --no-color
```

## What It Checks

### Core Data (Required)
- River name must be present and linked to USGS
- Feet measurement must be present and numeric
- Timestamp must be present and formatted correctly
- Threshold information must be displayed

### Optional Data
- **CFS**: Discharge data (some sites may not have this)
- **Sparkline**: 12-hour visual chart showing runnable status (green = at/above threshold, red = below)
- **Trend**: Rising/falling/steady indicator with colored text
- **Weather**: Temperature and wind observations
- **City Labels**: Friendly abbreviations (ALBVL, HNTSV, etc.) instead of airport codes
- **Secondary Weather**: Valley trend data for lake paddling sites
- **QPF**: Quantitative Precipitation Forecast (rainfall prediction)

## Testing Your Changes

After modifying the dashboard code, always validate:

```bash
# Test with sample data
python3 validate_dashboard.py test-sample-dashboard.html

# Test with real data
python3 usgs_multi_alert.py --config gauges.conf.json --cfs \
  --dump-html /tmp/test.html --trend-hours 8 && \
python3 validate_dashboard.py /tmp/test.html
```

## Troubleshooting

### Remote URL Issues

**"URL Error: Name or service not known"**
- Check that your app is deployed and running
- Verify the URL is correct (try opening in browser first)
- Check DNS/network connectivity

**"HTTP Error 502/503: Bad Gateway/Service Unavailable"**
- App might be starting up (wait 10-30 seconds and try again)
- Container might be crashed (check `fly logs` or your hosting logs)

**Timeout errors**
- Increase timeout: `--timeout 60`
- Check if your app is responding slowly
- Verify your hosting service is operational

**SSL Certificate errors**
- URL might be HTTP instead of HTTPS
- Try with HTTP if HTTPS fails: `http://your-app.fly.dev`

### Local File Issues

**"No sites found in HTML!"**
- Check that the HTML file contains a `<tbody>` element with river data
- Verify the HTML structure matches the expected format

### Low Scores

- Run with `--site "Site Name"` to focus on a specific site
- Check for missing data elements in the HTML
- Verify weather station mappings are correct
- Ensure QPF client is initialized (needs NWS_UA and NWS_CONTACT env vars)

### Testing Tips

```bash
# Quick connectivity check
curl -I https://docker-blue-sound-1751.fly.dev

# Test with increased verbosity
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --verbose

# Check specific site after deployment
fly deploy && sleep 10 && python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --site "Town Creek"
```

## Fun Facts

- 🎨 Uses ANSI color codes for terminal styling
- 🏗️ Built with Python's HTMLParser (no external dependencies!)
- 🚀 Fast and lightweight
- 🎯 Specifically validates the new city abbreviation labels
- 🌈 Makes testing enjoyable for your kayak crew!

---

Made with ❤️ for paddlers who care about water levels! 🚣‍♂️

#!/usr/bin/env python3
"""
Generate detailed Google Analytics-style dashboard pages for individual river sites.
Shows 7-day charts for CFS, water level (feet), and temperature/wind history.
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
import html

# Import TVA forecast generator (optional - only for TVA sites)
try:
    from tva_fetch import generate_tva_forecast_html
    TVA_FORECAST_AVAILABLE = True
except ImportError:
    TVA_FORECAST_AVAILABLE = False

def calculate_wind_chill(temp_f, wind_mph):
    """
    Calculate wind chill temperature using NWS formula.

    Wind chill is only valid for:
    - Temperature <= 50°F
    - Wind speed >= 3 mph

    Formula: WC = 35.74 + 0.6215T - 35.75(V^0.16) + 0.4275T(V^0.16)
    Where T = air temperature in °F, V = wind speed in mph

    Returns:
        Tuple of (wind_chill_temp, emoji, description) or (None, None, None) if not applicable
    """
    if temp_f is None or wind_mph is None:
        return None, None, None

    # Wind chill only applies when temp <= 50°F and wind >= 3 mph
    if temp_f > 50 or wind_mph < 3:
        return None, None, None

    # NWS Wind Chill Formula
    wind_chill = (35.74 + 0.6215 * temp_f -
                  35.75 * (wind_mph ** 0.16) +
                  0.4275 * temp_f * (wind_mph ** 0.16))

    # Fun emoji ranges based on wind chill
    if wind_chill < 0:
        emoji = "❄️🥶"
        desc = "Dangerous!"
    elif wind_chill < 10:
        emoji = "🥶"
        desc = "Extreme Cold"
    elif wind_chill < 20:
        emoji = "🧊"
        desc = "Very Cold"
    elif wind_chill < 32:
        emoji = "🌬️"
        desc = "Freezing"
    elif wind_chill < 40:
        emoji = "😬"
        desc = "Chilly"
    else:
        emoji = "🌡️"
        desc = "Cool"

    return wind_chill, emoji, desc

def get_location_links(site_id, tva_site_code):
    """
    Get location links HTML for a river site.

    Args:
        site_id: USGS site ID or empty string
        tva_site_code: TVA site code (e.g., 'HADT1', 'OCBT1') or None

    Returns:
        HTML string with location links
    """
    # TVA sites
    if tva_site_code == "HADT1":
        return (' <a href="https://www.google.com/maps/place/35%C2%B010%2724.7%22N+84%C2%B023%2701.4%22W/@35.1713452,-84.38115,16.39z" '
                'target="_blank" class="location-link">📍 Put in</a> '
                '<a href="https://www.google.com/maps/place/35%C2%B010%2752.5%22N+84%C2%B026%2719.1%22W/@35.1816932,-84.4346579,16.39z" '
                'target="_blank" class="location-link">🏁 Take out</a>')

    if tva_site_code == "OCCT1":
        return (' <a href="https://www.google.com/maps/place/Ocoee+Whitewater+Center/@35.0619844,-84.4296477,17z" '
                'target="_blank" class="location-link">📍 Upper Ocoee Put-in (Olympic)</a> '
                '<a href="https://www.tva.com/environment/lake-levels/ocoee-3" '
                'target="_blank" class="location-link">📅 Upper Ocoee Info</a>')

    if tva_site_code == "OCBT1":
        return (' <a href="https://maps.app.goo.gl/5cD9XmDBaiu6kZVy9" '
                'target="_blank" class="location-link">📍 Middle Ocoee Put-in</a> '
                '<a href="https://maps.app.goo.gl/nzEjdqdPwLac6nMp8" '
                'target="_blank" class="location-link">🏁 Take-out</a> '
                '<a href="https://www.tva.com/environment/lake-levels/ocoee-2/recreation-release-calendar" '
                'target="_blank" class="location-link">📅 Middle Ocoee Release Schedule</a>')

    if tva_site_code == "OCAT1":
        return (' <a href="https://www.google.com/maps/place/Parksville+Lake/@35.0950,-84.6470,15z" '
                'target="_blank" class="location-link">📍 Parksville Dam</a> '
                '<a href="https://www.tva.com/environment/lake-levels/ocoee-1" '
                'target="_blank" class="location-link">📅 Lower Ocoee Info</a>')

    # USGS sites
    if site_id == "02399200":  # Little River Canyon
        return (' <a href="https://www.google.com/maps/dir/Little+River+Canyon+Kayak+Put+In//@34.3914776,-85.6250722,19z" '
                'target="_blank" class="location-link">🚀 Suicide put in</a> '
                '<a href="https://maps.app.goo.gl/WuMrPD13zbDKwzwx6" '
                'target="_blank" class="location-link">📍 Eberhart Point</a> '
                '<a href="https://maps.app.goo.gl/Rt7pv8qZzzUsFFh37" '
                'target="_blank" class="location-link">🏁 Chair Lift Take Out</a>')

    if site_id == "02455000":  # Locust Fork
        return (' <a href="https://maps.app.goo.gl/VxoBRfDEiznaJEuR6" '
                'target="_blank" class="location-link">📍 Upper put in</a> '
                '<a href="https://maps.app.goo.gl/yW8uYJAUbpub1bQX8" '
                'target="_blank" class="location-link">📍 OLD Upper put in</a> '
                '<a href="https://maps.app.goo.gl/KsminZcRhyHsQi4s9" '
                'target="_blank" class="location-link">📍 Kings Bend put in</a> '
                '<a href="https://maps.app.goo.gl/8QTdmaYiyBWgdB7G6" '
                'target="_blank" class="location-link">🏁 Take out</a>')

    if site_id == "02341460":  # Rush South (Columbus GA)
        return (' <a href="https://rushsouth.com/" '
                'target="_blank" class="location-link">🌊 RushSouth Whitewater Park</a> '
                '<a href="https://lakes.southernco.com/" '
                'target="_blank" class="location-link">📊 GA Power Lake Levels</a> '
                '<a href="https://www.google.com/maps/place/RushSouth+Whitewater+Park/@32.4697,-84.9935,16z" '
                'target="_blank" class="location-link">📍 Map</a>')

    if site_id == "1":  # Short Creek (StreamBeam)
        return (' <a href="https://maps.app.goo.gl/S7sgCqGY2Hg43J5H9" '
                'target="_blank" class="location-link">📍 Put in</a> '
                '<a href="https://maps.app.goo.gl/D2QKT4HobnhpRnnVA" '
                'target="_blank" class="location-link">🏁 Take out</a>')

    return ""


def fetch_usgs_7day_data(site_id, parameter_code):
    """
    Fetch 7 days of historical data from USGS IV service.

    Args:
        site_id: USGS site number (e.g., "02455000")
        parameter_code: "00060" for discharge (CFS) or "00065" for gage height (feet)

    Returns:
        List of (timestamp_iso, value) tuples
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)

    params = {
        "sites": site_id,
        "parameterCd": parameter_code,
        "startDT": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDT": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "siteStatus": "all",
        "format": "json"
    }

    url = f"https://waterservices.usgs.gov/nwis/iv/?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read())

        time_series = data.get("value", {}).get("timeSeries", [])
        if not time_series:
            return []

        values = time_series[0].get("values", [{}])[0].get("value", [])

        # Extract (datetime, value) pairs
        result = []
        for item in values:
            dt_str = item.get("dateTime")
            val_str = item.get("value")

            if dt_str and val_str:
                try:
                    val = float(val_str)
                    result.append((dt_str, val))
                except (ValueError, TypeError):
                    continue

        return result

    except Exception as e:
        print(f"Error fetching USGS data for {site_id} parameter {parameter_code}: {e}")
        return []

def generate_site_detail_html(site_data, cfs_history, feet_history):
    """
    Generate Google Analytics-style HTML dashboard for a river site.

    Args:
        site_data: Dict with site info (name, current cfs, current ft, etc.)
        cfs_history: List of (timestamp, cfs) tuples for 7 days
        feet_history: List of (timestamp, feet) tuples for 7 days

    Returns:
        HTML string
    """
    h = html.escape

    site_name = site_data.get("name", "River Site")
    site_id = site_data.get("site", "")
    current_cfs = site_data.get("cfs")
    current_ft = site_data.get("stage_ft")

    # StreamBeam sites only have feet data, no CFS
    is_streambeam = site_data.get("is_streambeam", False) or site_id == "1"
    current_temp = site_data.get("temp_f")
    current_wind_mph = site_data.get("wind_mph")
    current_wind_dir = site_data.get("wind_dir", "")
    threshold_ft = site_data.get("threshold_ft")
    threshold_cfs = site_data.get("threshold_cfs")
    in_range = site_data.get("in_range", False)
    last_in_time = site_data.get("last_in_time")  # Human-readable time when it went green

    # Prepare data for Chart.js - format timestamps as readable strings
    cfs_labels = []
    cfs_values = []
    for ts, val in cfs_history:
        try:
            # Parse ISO timestamp and format as "MMM D h:mm a"
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            label = dt.strftime("%b %d %I:%M %p")
            cfs_labels.append(label)
            cfs_values.append(val)
        except Exception:
            continue

    feet_labels = []
    feet_values = []
    for ts, val in feet_history:
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            label = dt.strftime("%b %d %I:%M %p")
            feet_labels.append(label)
            feet_values.append(val)
        except Exception:
            continue

    # Calculate stats
    if cfs_values:
        avg_cfs = sum(cfs_values) / len(cfs_values)
        max_cfs = max(cfs_values)
        min_cfs = min(cfs_values)
    else:
        avg_cfs = max_cfs = min_cfs = 0

    if feet_values:
        avg_ft = sum(feet_values) / len(feet_values)
        max_ft = max(feet_values)
        min_ft = min(feet_values)
    else:
        avg_ft = max_ft = min_ft = 0

    status_color = "#4ade80" if in_range else "#ef4444"
    status_text = "RUNNABLE" if in_range else "TOO LOW"

    # Build threshold display
    threshold_parts = []
    if threshold_ft is not None:
        threshold_parts.append(f"{threshold_ft:.2f} ft")
    if threshold_cfs is not None:
        threshold_parts.append(f"{int(threshold_cfs):,} CFS")
    threshold_str = " & ".join(threshold_parts) if threshold_parts else "No threshold set"

    # Last runnable time
    last_runnable = last_in_time if last_in_time else "Never recorded"

    # Check for TVA source and generate forecast panel
    is_tva = site_data.get("is_tva", False)
    tva_site_code = site_data.get("tva_site_code")
    tva_forecast_html = ""
    if is_tva and tva_site_code and TVA_FORECAST_AVAILABLE:
        try:
            runnable_threshold = int(threshold_cfs) if threshold_cfs else 3000
            tva_forecast_html = generate_tva_forecast_html(tva_site_code, runnable_threshold)
        except Exception as e:
            print(f"[DETAIL] TVA forecast generation failed: {e}")
            tva_forecast_html = ""

    # Get wind chill from passed data, or calculate if not provided
    wind_chill_temp = site_data.get("wind_chill_f")
    wind_chill_emoji = site_data.get("wind_chill_emoji")
    wind_chill_desc = site_data.get("wind_chill_desc")

    # If wind chill wasn't pre-calculated, calculate it now
    if wind_chill_temp is None and current_temp is not None and current_wind_mph is not None:
        wind_chill_temp, wind_chill_emoji, wind_chill_desc = calculate_wind_chill(current_temp, current_wind_mph)

    # Extract rainfall data
    precip_today = site_data.get("precip_today_in")
    pws_station = site_data.get("pws_station")
    pws_label = site_data.get("pws_label")
    rainfall_48h = site_data.get("rainfall_48h", {})
    rainfall_7d = site_data.get("rainfall_7d", {})
    rainfall_30d = site_data.get("rainfall_30d", {})

    # Extract rainfall stats
    rain_48h_total = rainfall_48h.get("total_precip_in", 0)
    rain_7d_total = rainfall_7d.get("total_precip_in", 0)
    rain_7d_rainy_days = rainfall_7d.get("rainy_days", 0)
    rain_30d_total = rainfall_30d.get("total_precip_in", 0)
    rain_30d_rainy_days = rainfall_30d.get("rainy_days", 0)

    # Prepare rainfall chart data (daily totals for 7 days)
    rainfall_daily = site_data.get("rainfall_daily", [])
    rain_labels = []
    rain_values = []
    for day in rainfall_daily:
        try:
            # Parse date and format as "Mon Jan 2"
            dt = datetime.strptime(day.get("date", ""), "%Y-%m-%d")
            label = dt.strftime("%a %b %d")
            rain_labels.append(label)
            rain_values.append(day.get("precip_in", 0) or 0)
        except Exception:
            continue

    # Calculate rainfall chart stats
    if rain_values:
        avg_rain = sum(rain_values) / len(rain_values)
        max_rain = max(rain_values)
        total_rain = sum(rain_values)
    else:
        avg_rain = max_rain = total_rain = 0

    # Extract QPF (forecast) data for chart
    qpf_data = site_data.get("qpf", {}) or {}
    qpf_labels = []
    qpf_values = []
    if qpf_data:
        # QPF data comes as {date_str: inches, ...} sorted by date
        today = datetime.now().date()
        sorted_dates = sorted(qpf_data.keys())
        for date_str in sorted_dates:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                # Label: Today, Tomorrow, or day name
                days_diff = (dt - today).days
                if days_diff == 0:
                    label = "Today (QPF)"
                elif days_diff == 1:
                    label = "Tomorrow (QPF)"
                else:
                    label = dt.strftime("%a (QPF)")
                qpf_labels.append(label)
                qpf_values.append(qpf_data[date_str] or 0)
            except Exception:
                continue

    # Calculate total QPF forecast
    total_qpf = sum(qpf_values) if qpf_values else 0

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{h(site_name)} - River Dashboard</title>
{"" if is_tva else '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>'}
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  background: #f5f5f5;
  padding: 20px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{
  background: white;
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.header h1 {{
  font-size: 28px;
  color: #333;
  margin-bottom: 8px;
}}
.header .status {{
  display: inline-block;
  padding: 6px 12px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
  color: white;
  background: {status_color};
}}
.header .meta {{
  margin-top: 12px;
  font-size: 14px;
  color: #666;
}}
.header .meta span {{
  margin-right: 20px;
}}

.chart-row {{
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
  margin-bottom: 20px;
}}

.chart-box {{
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.chart-box h2 {{
  font-size: 18px;
  color: #555;
  margin-bottom: 4px;
  font-weight: 600;
}}
.chart-box .chart-value {{
  font-size: 32px;
  font-weight: bold;
  color: #1a73e8;
  margin-bottom: 8px;
}}
.chart-box .chart-meta {{
  font-size: 13px;
  color: #888;
  margin-bottom: 16px;
}}
.chart-canvas {{
  position: relative;
  height: 300px;
  background: #f8fbff;
  border-radius: 4px;
  padding: 10px;
}}

.stats-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}}
.stat-box {{
  background: white;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.stat-box .label {{
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}}
.stat-box .value {{
  font-size: 24px;
  font-weight: bold;
  color: #333;
}}
.stat-box .range {{
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}}

.back-link {{
  display: inline-block;
  margin-bottom: 16px;
  color: #1a73e8;
  text-decoration: none;
  font-size: 14px;
}}
.back-link:hover {{ text-decoration: underline; }}

.location-link {{
  font-size: 16px;
  font-weight: normal;
  color: #1a73e8;
  text-decoration: none;
  margin-left: 16px;
  padding: 4px 12px;
  background: #e8f0fe;
  border-radius: 16px;
  transition: all 0.2s ease;
}}
.location-link:hover {{
  background: #1a73e8;
  color: white;
  text-decoration: none;
}}

@media (max-width: 768px) {{
  .header h1 {{ font-size: 22px; }}
  .chart-value {{ font-size: 24px; }}
  .stat-box .value {{ font-size: 20px; }}
}}

/* Historical Chart Section */
.history-section {{
  background: linear-gradient(135deg, #1a2f4a 0%, #243b55 100%);
  border-radius: 12px;
  padding: 24px;
  margin: 24px 0;
  color: white;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}}
.history-header {{
  text-align: center;
  margin-bottom: 20px;
}}
.history-title {{
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 4px;
}}
.history-subtitle {{
  font-size: 13px;
  opacity: 0.7;
}}
.history-controls {{
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 20px;
}}
.range-btn {{
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
}}
.range-btn:hover {{
  background: rgba(255,255,255,0.2);
}}
.range-btn.active {{
  background: #3b82f6;
  border-color: #3b82f6;
  font-weight: bold;
}}
.history-stats {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}}
.stat-card {{
  background: rgba(0,0,0,0.3);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}}
.stat-card .stat-label {{
  font-size: 11px;
  text-transform: uppercase;
  opacity: 0.7;
  margin-bottom: 4px;
}}
.stat-card .stat-value {{
  font-size: 18px;
  font-weight: bold;
  color: #60a5fa;
}}
.history-chart-container {{
  background: rgba(255,255,255,0.95);
  border-radius: 8px;
  padding: 16px;
  height: 300px;
  margin-bottom: 16px;
}}
.history-legend {{
  display: flex;
  justify-content: center;
  gap: 24px;
  flex-wrap: wrap;
}}
.legend-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}}
.legend-color {{
  width: 16px;
  height: 4px;
  border-radius: 2px;
}}
@media (max-width: 600px) {{
  .history-stats {{
    grid-template-columns: repeat(2, 1fr);
  }}
  .history-controls {{
    flex-wrap: wrap;
  }}
  .history-legend {{
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }}
}}

/* Weather & Rainfall Section */
.weather-rainfall-section {{
  background: linear-gradient(135deg, #0f766e 0%, #115e59 100%);
  border-radius: 12px;
  padding: 24px;
  margin: 24px 0;
  color: white;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}}
.weather-rainfall-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}}
.weather-rainfall-title {{
  font-size: 20px;
  font-weight: bold;
}}
.weather-rainfall-source {{
  font-size: 12px;
  opacity: 0.8;
  background: rgba(255,255,255,0.1);
  padding: 4px 10px;
  border-radius: 12px;
}}
.weather-rainfall-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
}}
.weather-card {{
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  backdrop-filter: blur(5px);
}}
.weather-card .card-icon {{
  font-size: 28px;
  margin-bottom: 8px;
}}
.weather-card .card-label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.8;
  margin-bottom: 6px;
}}
.weather-card .card-value {{
  font-size: 22px;
  font-weight: bold;
}}
.weather-card .card-sub {{
  font-size: 11px;
  opacity: 0.7;
  margin-top: 4px;
}}
.weather-card.rain-highlight {{
  background: rgba(59, 130, 246, 0.3);
  border: 1px solid rgba(59, 130, 246, 0.5);
}}
@media (max-width: 600px) {{
  .weather-rainfall-grid {{
    grid-template-columns: repeat(2, 1fr);
  }}
}}
</style>
</head>
<body>
<div class="container">
  <a href="/" class="back-link">← Back to All Rivers</a>

  <div class="header">
    <h1>{h(site_name)}{get_location_links(site_id, tva_site_code)}</h1>
    {"" if is_tva else f'''<div class="status">{status_text}</div>
    <div class="meta">
      <span><strong>USGS Site:</strong> {h(site_id)}</span>
      <span><strong>Threshold:</strong> {h(threshold_str)}</span>
      <span><strong>Last Runnable:</strong> {h(last_runnable)}</span>
    </div>'''}
  </div>

  {tva_forecast_html}

  {"" if is_tva or is_streambeam else f'''<div class="chart-row">
    <div class="chart-box">
      <h2>Discharge (CFS)</h2>
      <div class="chart-value">{f"{int(current_cfs):,}" if current_cfs is not None else "N/A"} <span style="font-size:18px; font-weight:normal;">CFS</span></div>
      <div class="chart-meta">7-day average: {f"{int(avg_cfs):,}" if avg_cfs > 0 else "N/A"} CFS · Range: {f"{int(min_cfs):,} - {int(max_cfs):,}" if max_cfs > 0 else "N/A"}</div>
      <div class="chart-canvas">
        <canvas id="cfsChart"></canvas>
      </div>
    </div>
  </div>'''}

  {"" if is_tva else f'''<div class="chart-row">
    <div class="chart-box">
      <h2>{"Water Level" if is_streambeam else "Gage Height"} (Feet)</h2>
      <div class="chart-value">{current_ft:.2f} <span style="font-size:18px; font-weight:normal;">ft</span></div>
      <div class="chart-meta">7-day average: {avg_ft:.2f} ft · Range: {min_ft:.2f} - {max_ft:.2f}</div>
      <div class="chart-canvas">
        <canvas id="feetChart"></canvas>
      </div>
    </div>
  </div>'''}

  {"" if is_tva else f'''<div class="chart-row">
    <div class="chart-box" style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);">
      <h2 style="color: #0369a1;">🌧️ Rainfall & Forecast (Inches)</h2>
      <div class="chart-value" style="color: #0284c7;">{total_rain:.2f} <span style="font-size:18px; font-weight:normal;">in (7-day)</span>{f' + <span style="color:#f59e0b;">{total_qpf:.2f}</span> <span style="font-size:18px; font-weight:normal;">in forecast</span>' if total_qpf > 0 else ''}</div>
      <div class="chart-meta">7-day avg: {avg_rain:.2f} in/day · Max: {max_rain:.2f} in{f' · <span style="color:#f59e0b;">QPF: {total_qpf:.2f} in</span>' if total_qpf > 0 else ''}</div>
      <div class="chart-canvas">
        <canvas id="rainChart"></canvas>
      </div>
      <div style="display: flex; justify-content: center; gap: 24px; margin-top: 12px; font-size: 13px;">
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="display: inline-block; width: 16px; height: 12px; background: rgba(14, 165, 233, 0.7); border-radius: 2px;"></span>
          <span style="color: #0369a1;">Historical Rain</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="display: inline-block; width: 16px; height: 12px; background: rgba(245, 158, 11, 0.7); border-radius: 2px;"></span>
          <span style="color: #d97706;">QPF Forecast</span>
        </div>
      </div>
    </div>
  </div>'''}

  <div class="stats-grid">
    <div class="stat-box">
      <div class="label">Current Temperature</div>
      <div class="value">{f"{current_temp:.1f}°F" if current_temp is not None else "N/A"}</div>
    </div>
    <div class="stat-box">
      <div class="label">Wind Speed</div>
      <div class="value">{f"{current_wind_mph:.1f} mph {current_wind_dir}" if current_wind_mph is not None else "N/A"}</div>
    </div>
    <div class="stat-box">
      <div class="label">Current Status</div>
      <div class="value" style="color: {status_color};">{status_text}</div>
      <div class="range">{"Meets all thresholds" if in_range else "Below threshold"}</div>
    </div>
    <div class="stat-box">
      <div class="label">Wind Chill {wind_chill_emoji if wind_chill_emoji else ""}</div>
      <div class="value">{f"{wind_chill_temp:.1f}°F" if wind_chill_temp is not None else "N/A"}</div>
      <div class="range">{wind_chill_desc if wind_chill_desc else "No wind chill" if current_temp is not None and current_wind_mph is not None else "Data unavailable"}</div>
    </div>
  </div>

  <div class="weather-rainfall-section">
    <div class="weather-rainfall-header">
      <div class="weather-rainfall-title">🌧️ Weather & Rainfall</div>
      {f'<div class="weather-rainfall-source">PWS: {h(pws_label or pws_station or "N/A")}</div>' if pws_station else ''}
    </div>
    <div class="weather-rainfall-grid">
      <div class="weather-card">
        <div class="card-icon">🌡️</div>
        <div class="card-label">Temperature</div>
        <div class="card-value">{f"{current_temp:.0f}°F" if current_temp is not None else "N/A"}</div>
      </div>
      <div class="weather-card">
        <div class="card-icon">💨</div>
        <div class="card-label">Wind</div>
        <div class="card-value">{f"{current_wind_mph:.0f}" if current_wind_mph is not None else "N/A"}</div>
        <div class="card-sub">{f"mph {current_wind_dir}" if current_wind_mph is not None else ""}</div>
      </div>
      <div class="weather-card{' rain-highlight' if precip_today and precip_today > 0 else ''}">
        <div class="card-icon">☔</div>
        <div class="card-label">Today's Rain</div>
        <div class="card-value">{f'{precip_today:.2f}"' if precip_today is not None else "N/A"}</div>
      </div>
      <div class="weather-card{' rain-highlight' if rain_48h_total > 0.5 else ''}">
        <div class="card-icon">⏱️</div>
        <div class="card-label">48-Hour Rain</div>
        <div class="card-value">{f'{rain_48h_total:.2f}"' if rain_48h_total else "N/A"}</div>
      </div>
      <div class="weather-card{' rain-highlight' if rain_7d_total > 0.5 else ''}">
        <div class="card-icon">📊</div>
        <div class="card-label">7-Day Rain</div>
        <div class="card-value">{f'{rain_7d_total:.2f}"' if rain_7d_total else "N/A"}</div>
        <div class="card-sub">{f"{rain_7d_rainy_days} rainy days" if rain_7d_rainy_days else ""}</div>
      </div>
      <div class="weather-card">
        <div class="card-icon">📈</div>
        <div class="card-label">30-Day Rain</div>
        <div class="card-value">{f'{rain_30d_total:.2f}"' if rain_30d_total else "N/A"}</div>
        <div class="card-sub">{f"{rain_30d_rainy_days} rainy days" if rain_30d_rainy_days else ""}</div>
      </div>
      <div class="weather-card">
        <div class="card-icon">{wind_chill_emoji if wind_chill_emoji else "❄️"}</div>
        <div class="card-label">Feels Like</div>
        <div class="card-value">{f"{wind_chill_temp:.0f}°F" if wind_chill_temp is not None else f"{current_temp:.0f}°F" if current_temp is not None else "N/A"}</div>
        <div class="card-sub">{wind_chill_desc if wind_chill_desc else ""}</div>
      </div>
    </div>
  </div>

  {"" if is_streambeam else '''<div class="history-section">
    <div class="history-header">
      <div class="history-title">Historical Data</div>
      <div class="history-subtitle">Select time range to view historical trends</div>
    </div>
    <div class="history-controls">
      <button class="range-btn active" data-days="7">7 Days</button>
      <button class="range-btn" data-days="30">30 Days</button>
      <button class="range-btn" data-days="90">90 Days</button>
      <button class="range-btn" data-days="365">1 Year</button>
    </div>
    <div class="history-stats" id="historyStats">
      <div class="stat-card">
        <div class="stat-label">Data Points</div>
        <div class="stat-value" id="statCount">--</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Max CFS</div>
        <div class="stat-value" id="statMaxCfs">--</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg CFS</div>
        <div class="stat-value" id="statAvgCfs">--</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Max Height</div>
        <div class="stat-value" id="statMaxFeet">--</div>
      </div>
    </div>
    <div class="history-chart-container">
      <canvas id="historyChart"></canvas>
    </div>
    <div class="history-legend">
      <div class="legend-row">
        <span class="legend-color" style="background: #ef4444;"></span>
        <span>Discharge (CFS) - Left Axis</span>
      </div>
      <div class="legend-row">
        <span class="legend-color" style="background: #3b82f6;"></span>
        <span>Gage Height (ft) - Right Axis</span>
      </div>
    </div>
  </div>
'''}

</div>

{"" if is_tva else f'''<script>
// Debug: Log data to console
console.log('CFS Labels:', {json.dumps(cfs_labels)});
console.log('CFS Values:', {json.dumps(cfs_values)});
console.log('Feet Labels:', {json.dumps(feet_labels)});
console.log('Feet Values:', {json.dumps(feet_values)});

// CFS Chart (skip if element doesn't exist - e.g., StreamBeam sites)
const cfsChartEl = document.getElementById('cfsChart');
if (cfsChartEl) {{
const cfsCtx = cfsChartEl.getContext('2d');
const cfsLabels = {json.dumps(cfs_labels)};
const cfsValues = {json.dumps(cfs_values)};

if (cfsLabels.length === 0 || cfsValues.length === 0) {{
  cfsCtx.canvas.parentElement.innerHTML = '<div style="padding:20px;text-align:center;color:#999;">No CFS data available for this site</div>';
}} else {{
  new Chart(cfsCtx, {{
    type: 'line',
    data: {{
      labels: cfsLabels,
      datasets: [{{
        label: 'CFS',
        data: cfsValues,
      borderColor: '#1a73e8',
      backgroundColor: 'rgba(26, 115, 232, 0.1)',
      borderWidth: 2,
      tension: 0.4,
      fill: true,
      pointRadius: 0,
      pointHoverRadius: 4
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        mode: 'index',
        intersect: false,
      }}
    }},
    scales: {{
      x: {{
        ticks: {{
          maxRotation: 45,
          minRotation: 45,
          autoSkip: true,
          maxTicksLimit: 10
        }},
        grid: {{ display: false }}
      }},
      y: {{
        beginAtZero: false,
        grid: {{ color: 'rgba(0,0,0,0.05)' }}
      }}
    }}
  }}
  }});
}}
}} // End cfsChartEl check

// Feet Chart
const feetCtx = document.getElementById('feetChart').getContext('2d');
const feetLabels = {json.dumps(feet_labels)};
const feetValues = {json.dumps(feet_values)};

if (feetLabels.length === 0 || feetValues.length === 0) {{
  feetCtx.canvas.parentElement.innerHTML = '<div style="padding:20px;text-align:center;color:#999;">No gage height data available for this site</div>';
}} else {{
  new Chart(feetCtx, {{
    type: 'line',
    data: {{
      labels: feetLabels,
      datasets: [{{
        label: 'Feet',
        data: feetValues,
      borderColor: '#1a73e8',
      backgroundColor: 'rgba(26, 115, 232, 0.1)',
      borderWidth: 2,
      tension: 0.4,
      fill: true,
      pointRadius: 0,
      pointHoverRadius: 4
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        mode: 'index',
        intersect: false,
      }}
    }},
    scales: {{
      x: {{
        ticks: {{
          maxRotation: 45,
          minRotation: 45,
          autoSkip: true,
          maxTicksLimit: 10
        }},
        grid: {{ display: false }}
      }},
      y: {{
        beginAtZero: false,
        grid: {{ color: 'rgba(0,0,0,0.05)' }}
      }}
    }}
  }}
  }});
}}

// Rainfall Chart (bar chart for daily totals + QPF forecast)
const rainChartEl = document.getElementById('rainChart');
if (rainChartEl) {{
  const rainCtx = rainChartEl.getContext('2d');
  const rainLabels = {json.dumps(rain_labels)};
  const rainValues = {json.dumps(rain_values)};
  const qpfLabels = {json.dumps(qpf_labels)};
  const qpfValues = {json.dumps(qpf_values)};

  // Combine historical + QPF labels and create datasets
  const allLabels = [...rainLabels, ...qpfLabels];
  const historicalData = [...rainValues, ...Array(qpfLabels.length).fill(null)];
  const forecastData = [...Array(rainLabels.length).fill(null), ...qpfValues];

  if (allLabels.length === 0) {{
    rainCtx.canvas.parentElement.innerHTML = '<div style="padding:20px;text-align:center;color:#999;">No rainfall data available for this site</div>';
  }} else {{
    new Chart(rainCtx, {{
      type: 'bar',
      data: {{
        labels: allLabels,
        datasets: [
          {{
            label: 'Historical Rain',
            data: historicalData,
            backgroundColor: 'rgba(14, 165, 233, 0.7)',
            borderColor: 'rgba(3, 105, 161, 1)',
            borderWidth: 1,
            borderRadius: 4,
          }},
          {{
            label: 'QPF Forecast',
            data: forecastData,
            backgroundColor: 'rgba(245, 158, 11, 0.7)',
            borderColor: 'rgba(217, 119, 6, 1)',
            borderWidth: 1,
            borderRadius: 4,
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              label: function(context) {{
                if (context.parsed.y === null) return null;
                const type = context.dataset.label;
                return type + ': ' + context.parsed.y.toFixed(2) + ' inches';
              }}
            }}
          }}
        }},
        scales: {{
          x: {{
            grid: {{ display: false }}
          }},
          y: {{
            beginAtZero: true,
            title: {{
              display: true,
              text: 'Inches',
              color: '#0369a1'
            }},
            grid: {{ color: 'rgba(0,0,0,0.05)' }}
          }}
        }}
      }}
    }});
  }}
}}

// History Chart with Time Range Selection (skip if element doesn't exist - e.g., StreamBeam sites)
(function() {{
  const historyChartEl = document.getElementById('historyChart');
  if (!historyChartEl) {{
    console.log('History chart element not found - skipping history chart initialization');
    return;
  }}
  const siteId = '{site_id}';
  let historyChart = null;

  async function loadHistoryData(days) {{
    try {{
      const response = await fetch(`/api/usgs-history/${{siteId}}?days=${{days}}`);
      const data = await response.json();
      return data;
    }} catch (err) {{
      console.error('Failed to load history:', err);
      return null;
    }}
  }}

  function updateStats(data) {{
    document.getElementById('statCount').textContent = (data.cfs_count || 0).toLocaleString();

    if (data.stats && data.stats.cfs) {{
      document.getElementById('statMaxCfs').textContent =
        data.stats.cfs.max ? Math.round(data.stats.cfs.max).toLocaleString() + ' CFS' : '--';
      document.getElementById('statAvgCfs').textContent =
        data.stats.cfs.avg ? Math.round(data.stats.cfs.avg).toLocaleString() + ' CFS' : '--';
    }}

    if (data.stats && data.stats.feet) {{
      document.getElementById('statMaxFeet').textContent =
        data.stats.feet.max ? data.stats.feet.max.toFixed(2) + ' ft' : '--';
    }}
  }}

  function renderChart(data) {{
    const ctx = document.getElementById('historyChart').getContext('2d');

    if (historyChart) {{
      historyChart.destroy();
    }}

    if (!data.cfs || data.cfs.length === 0) {{
      ctx.canvas.parentElement.innerHTML =
        '<div style="padding:40px;text-align:center;color:#666;">' +
        '<p style="font-size:18px;">No historical data available</p></div>';
      return;
    }}

    const labels = data.cfs.map(o => {{
      const d = new Date(o.timestamp);
      return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric', hour: 'numeric' }});
    }});

    const cfsData = data.cfs.map(o => o.value);
    const feetData = data.feet ? data.feet.map(o => o.value) : [];

    const datasets = [
      {{
        label: 'Discharge (CFS)',
        data: cfsData,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        yAxisID: 'y',
        pointRadius: 1,
        pointHoverRadius: 4
      }}
    ];

    if (feetData.length > 0) {{
      datasets.push({{
        label: 'Gage Height (ft)',
        data: feetData,
        borderColor: '#3b82f6',
        borderWidth: 2,
        fill: false,
        tension: 0.3,
        yAxisID: 'y1',
        pointRadius: 0,
        pointHoverRadius: 3
      }});
    }}

    historyChart = new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: datasets
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{
          mode: 'index',
          intersect: false
        }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(0,0,0,0.8)',
            titleFont: {{ size: 14 }},
            bodyFont: {{ size: 13 }},
            padding: 12,
            callbacks: {{
              label: function(context) {{
                let label = context.dataset.label || '';
                if (context.parsed.y !== null) {{
                  if (label.includes('CFS')) {{
                    label += ': ' + context.parsed.y.toLocaleString() + ' CFS';
                  }} else {{
                    label += ': ' + context.parsed.y.toFixed(2) + ' ft';
                  }}
                }}
                return label;
              }}
            }}
          }}
        }},
        scales: {{
          x: {{
            ticks: {{
              maxRotation: 45,
              minRotation: 45,
              autoSkip: true,
              maxTicksLimit: 12
            }},
            grid: {{ display: false }}
          }},
          y: {{
            type: 'linear',
            display: true,
            position: 'left',
            title: {{
              display: true,
              text: 'Discharge (CFS)',
              color: '#ef4444'
            }},
            ticks: {{ color: '#ef4444' }},
            grid: {{ color: 'rgba(239, 68, 68, 0.1)' }}
          }},
          y1: {{
            type: 'linear',
            display: feetData.length > 0,
            position: 'right',
            title: {{
              display: true,
              text: 'Gage Height (ft)',
              color: '#3b82f6'
            }},
            ticks: {{ color: '#3b82f6' }},
            grid: {{ drawOnChartArea: false }}
          }}
        }}
      }}
    }});
  }}

  async function updateChart(days) {{
    const data = await loadHistoryData(days);
    if (data) {{
      updateStats(data);
      renderChart(data);
    }}
  }}

  // Set up button click handlers
  document.querySelectorAll('.range-btn').forEach(btn => {{
    btn.addEventListener('click', function() {{
      document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      updateChart(parseInt(this.dataset.days));
    }});
  }});

  // Initial load
  updateChart(7);
}})();
</script>'''}

</body>
</html>"""

    return html_content


if __name__ == "__main__":
    # Test with a sample site
    print("Testing site detail generator...")

    test_data = {
        "name": "Locust Fork @ US 231",
        "site": "02455000",
        "cfs": 1250,
        "stage_ft": 2.35,
        "temp_f": 54.3,
        "wind_mph": 8.5,
        "wind_dir": "NW",
        "threshold_ft": 1.70,
        "threshold_cfs": None,
        "in_range": True,
        "last_in_time": "Oct 31, 2025 10:15 AM"
    }

    cfs_hist = fetch_usgs_7day_data("02455000", "00060")
    feet_hist = fetch_usgs_7day_data("02455000", "00065")

    html = generate_site_detail_html(test_data, cfs_hist, feet_hist)

    with open("test_site_detail.html", "w") as f:
        f.write(html)

    print("Generated test_site_detail.html")

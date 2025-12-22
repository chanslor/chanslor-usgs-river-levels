#!/usr/bin/env python3
"""
TVA Dam Data Fetcher

Fetches observed data from TVA REST API for dam monitoring.
Used for sites like Apalachia Dam (Hiwassee Dries) that don't have USGS gauges.

API Endpoint: https://www.tva.com/RestApi/observed-data/{SITE_CODE}.json
"""

import json
import urllib.request
from datetime import datetime
from typing import Optional, Dict, List, Any

# TVA API configuration
TVA_API_BASE = "https://www.tva.com/RestApi/observed-data"

# Browser-style User-Agent (TVA blocks obvious bots)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Known TVA site codes
TVA_SITES = {
    "HADT1": {
        "name": "Hiwassee Dries (Apalachia Dam)",
        "description": "Apalachia Dam spillway releases",
        "lat": 35.168,
        "lon": -84.298,
    },
    "OCBT1": {
        "name": "Ocoee #2 (Middle Dam)",
        "description": "Ocoee Dam #2 - main whitewater put-in for Middle Ocoee",
        "lat": 35.093,
        "lon": -84.510,
    },
    "OCCT1": {
        "name": "Ocoee #3 (Upper Dam)",
        "description": "Ocoee Dam #3 - Upper Ocoee section",
        "lat": 35.040,
        "lon": -84.467,
    },
    "OCAT1": {
        "name": "Ocoee #1 (Parksville Dam)",
        "description": "Ocoee Dam #1 / Parksville - Lower Ocoee section",
        "lat": 35.095,
        "lon": -84.647,
    },
    "DUGT1": {
        "name": "Douglas Dam",
        "description": "Douglas Dam on French Broad River",
        "lat": 36.0,
        "lon": -83.5,
    },
}

# Site-specific display text for the forecast panel
TVA_DISPLAY_CONFIG = {
    "HADT1": {
        "title": "APALACHIA OPERATIONS FORECAST",
        "subtitle": "Apalachia Dam → Hiwassee Dries",
        "history_title": "Apalachia Historical Dam Operations",
        "running_msg": "The Dries are running!",
        "quiet_msg": "Dam quiet, Dries dry",
        "filling_msg": "Dries filling up",
        "spillway_label": "Water starts flowing into Dries",
        "runnable_msg": "Dries will run",
    },
    "OCBT1": {
        "title": "OCOEE #2 OPERATIONS FORECAST",
        "subtitle": "Ocoee Dam #2 → Middle Ocoee",
        "history_title": "Ocoee #2 Historical Dam Operations",
        "running_msg": "Middle Ocoee is running!",
        "quiet_msg": "Dam quiet, no release",
        "filling_msg": "Release building up",
        "spillway_label": "Release starting",
        "runnable_msg": "Middle Ocoee will run",
    },
    "OCCT1": {
        "title": "OCOEE #3 OPERATIONS FORECAST",
        "subtitle": "Ocoee Dam #3 → Upper Ocoee",
        "history_title": "Ocoee #3 Historical Dam Operations",
        "running_msg": "Upper Ocoee is running!",
        "quiet_msg": "Dam quiet, no release",
        "filling_msg": "Release building up",
        "spillway_label": "Release starting",
        "runnable_msg": "Upper Ocoee will run",
    },
    "OCAT1": {
        "title": "OCOEE #1 OPERATIONS FORECAST",
        "subtitle": "Parksville Dam → Lower Ocoee",
        "history_title": "Ocoee #1 Historical Dam Operations",
        "running_msg": "Lower Ocoee is running!",
        "quiet_msg": "Dam quiet, no release",
        "filling_msg": "Release building up",
        "spillway_label": "Release starting",
        "runnable_msg": "Lower Ocoee will run",
    },
}


def fetch_tva_observed(site_code: str, timeout: int = 30) -> Optional[List[Dict]]:
    """
    Fetch observed data from TVA API.

    Args:
        site_code: TVA site code (e.g., 'HADT1' for Apalachia)
        timeout: Request timeout in seconds

    Returns:
        List of observation dicts, or None on error.
        Each dict has keys:
        - Day: "MM/DD/YYYY"
        - Time: "H AM/PM EST"
        - ReservoirElevation: "X,XXX.XX" (feet MSL, with commas)
        - TailwaterElevation: "XXX.XX" (feet MSL)
        - AverageHourlyDischarge: "X,XXX" (CFS, with commas)
    """
    url = f"{TVA_API_BASE}/{site_code}.json"
    headers = {"User-Agent": USER_AGENT}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())

            # API returns empty array [] if site code is invalid
            if not data:
                return None

            return data

    except Exception as e:
        print(f"[TVA] Error fetching {site_code}: {e}")
        return None


def parse_tva_value(value_str: str) -> float:
    """
    Parse a TVA numeric value (they use commas as thousands separators).

    Args:
        value_str: String like "1,277.81" or "2,848"

    Returns:
        Float value
    """
    if value_str is None:
        return 0.0
    return float(str(value_str).replace(",", ""))


def parse_tva_timestamp(day: str, time: str) -> Optional[datetime]:
    """
    Parse TVA timestamp strings.

    Args:
        day: "MM/DD/YYYY"
        time: "H AM EST" or "HH PM EDT"

    Returns:
        datetime object (timezone-naive, Eastern time)
    """
    try:
        # Remove timezone suffix for parsing
        time_clean = time.replace(" EST", "").replace(" EDT", "").strip()
        dt_str = f"{day} {time_clean}"
        return datetime.strptime(dt_str, "%m/%d/%Y %I %p")
    except Exception:
        return None


def get_latest_tva_observation(site_code: str) -> Optional[Dict[str, Any]]:
    """
    Get the most recent observation for a TVA site.

    Args:
        site_code: TVA site code (e.g., 'HADT1')

    Returns:
        Dict with:
        - discharge_cfs: int (current discharge in CFS)
        - pool_elevation_ft: float (reservoir level in feet MSL)
        - tailwater_ft: float (water level below dam in feet MSL)
        - timestamp: datetime
        - timestamp_str: str (formatted timestamp)
        - is_releasing: bool (True if discharge > 100 CFS)
        - raw: dict (original API response)

        Returns None if API fails or no data.
    """
    data = fetch_tva_observed(site_code)
    if not data:
        return None

    # Get the most recent observation (last in array)
    latest = data[-1]

    discharge = parse_tva_value(latest.get("AverageHourlyDischarge", "0"))
    pool = parse_tva_value(latest.get("ReservoirElevation", "0"))
    tailwater = parse_tva_value(latest.get("TailwaterElevation", "0"))
    timestamp = parse_tva_timestamp(latest.get("Day", ""), latest.get("Time", ""))

    return {
        "discharge_cfs": int(discharge),
        "pool_elevation_ft": pool,
        "tailwater_ft": tailwater,
        "timestamp": timestamp,
        "timestamp_str": timestamp.strftime("%Y-%m-%d %H:%M") if timestamp else "Unknown",
        "is_releasing": discharge >= 100,
        "raw": latest,
    }


def get_tva_discharge_for_site(site_code: str) -> Optional[int]:
    """
    Simple helper to get just the current discharge CFS.

    Args:
        site_code: TVA site code

    Returns:
        Current discharge in CFS, or None on error
    """
    obs = get_latest_tva_observation(site_code)
    if obs:
        return obs["discharge_cfs"]
    return None


def get_tva_trend(site_code: str, hours: int = 4) -> Optional[str]:
    """
    Calculate trend from recent observations.

    Args:
        site_code: TVA site code
        hours: Number of hours to consider for trend

    Returns:
        "rising", "falling", or "steady" (or None on error)
    """
    data = fetch_tva_observed(site_code)
    if not data or len(data) < 2:
        return None

    # Get last N hours of data
    recent = data[-min(hours, len(data)):]

    # Extract discharge values
    discharges = [parse_tva_value(obs.get("AverageHourlyDischarge", "0")) for obs in recent]

    if len(discharges) < 2:
        return "steady"

    first_avg = sum(discharges[:len(discharges)//2]) / (len(discharges)//2)
    last_avg = sum(discharges[len(discharges)//2:]) / (len(discharges) - len(discharges)//2)

    diff = last_avg - first_avg

    # Use 10% change as threshold
    if abs(diff) < first_avg * 0.1 if first_avg > 0 else 50:
        return "steady"
    elif diff > 0:
        return "rising"
    else:
        return "falling"


def get_tva_trend_data(site_code: str, hours: int = 12) -> Optional[Dict[str, Any]]:
    """
    Get trend data for sparkline visualization (compatible with USGS format).

    Args:
        site_code: TVA site code
        hours: Number of hours of history to fetch

    Returns:
        Dict with:
        - values: List of discharge values (floats) for sparkline
        - direction: "rising", "falling", or "steady"

        Returns None on error or insufficient data.
    """
    data = fetch_tva_observed(site_code)
    if not data or len(data) < 2:
        return None

    # Get last N hours of data
    recent = data[-min(hours, len(data)):]

    # Extract discharge values
    values = []
    for obs in recent:
        discharge = parse_tva_value(obs.get("AverageHourlyDischarge", "0"))
        values.append(discharge)

    if len(values) < 2:
        return None

    # Calculate direction
    delta = values[-1] - values[0]
    # Use 10% of first value as threshold, or 50 CFS minimum
    threshold = max(values[0] * 0.1, 50) if values[0] > 0 else 50

    if delta > threshold:
        direction = "rising"
    elif delta < -threshold:
        direction = "falling"
    else:
        direction = "steady"

    # Sample down to ~12 bars for display (take evenly spaced samples)
    target_bars = 12
    if len(values) > target_bars:
        step = len(values) // target_bars
        sampled = [values[i] for i in range(0, len(values), step)][:target_bars]
    else:
        sampled = values

    return {
        "values": sampled,
        "direction": direction
    }


def fetch_tva_predicted(site_code: str, timeout: int = 30) -> Optional[List[Dict]]:
    """
    Fetch predicted data from TVA API (3-day forecast).

    Args:
        site_code: TVA site code (e.g., 'HADT1' for Apalachia)
        timeout: Request timeout in seconds

    Returns:
        List of prediction dicts, or None on error.
        Each dict has keys:
        - Day: "MM/DD/YYYY"
        - AverageInflow: "X,XXX" (CFS, with commas)
        - MidnightElevation: float (feet MSL)
        - AverageOutflow: "X,XXX" (CFS, with commas)
    """
    url = f"https://www.tva.com/RestApi/predicted-data/{site_code}.json"
    headers = {"User-Agent": USER_AGENT}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())

            # API returns empty array [] if no predictions available
            if not data:
                return None

            return data

    except Exception as e:
        print(f"[TVA] Error fetching predicted data for {site_code}: {e}")
        return None


def get_tva_forecast(site_code: str, runnable_threshold: int = 3000) -> Optional[List[Dict[str, Any]]]:
    """
    Get 3-day dam operations forecast with runnable status.

    Args:
        site_code: TVA site code (e.g., 'HADT1')
        runnable_threshold: CFS threshold for runnable conditions (default 3000)

    Returns:
        List of forecast dicts with:
        - day: "MM/DD/YYYY"
        - day_label: "Today", "Tomorrow", "Day 3"
        - day_name: "Thu", "Fri", etc.
        - inflow_cfs: int
        - outflow_cfs: int
        - pool_elevation_ft: float
        - runnable_status: "yes", "maybe", "no"
        - runnable_label: "YES!", "MAYBE", "NO"
        - runnable_color: CSS color

        Returns None on error or no data.
    """
    data = fetch_tva_predicted(site_code)
    if not data:
        return None

    forecasts = []
    day_labels = ["Today", "Tomorrow", "Day 3"]

    for i, pred in enumerate(data[:3]):  # Max 3 days
        try:
            # Parse values
            inflow = int(parse_tva_value(pred.get("AverageInflow", "0")))
            outflow = int(parse_tva_value(pred.get("AverageOutflow", "0")))
            pool = pred.get("MidnightElevation", 0)
            if isinstance(pool, str):
                pool = parse_tva_value(pool)

            # Parse date for day name
            day_str = pred.get("Day", "")
            try:
                dt = datetime.strptime(day_str, "%m/%d/%Y")
                day_name = dt.strftime("%a")  # Mon, Tue, etc.
            except:
                day_name = ""

            # Determine runnable status
            if outflow >= runnable_threshold:
                status = "yes"
                label = "YES!"
                color = "#22c55e"  # Green
            elif outflow >= runnable_threshold * 0.5:  # 50% of threshold = maybe
                status = "maybe"
                label = "MAYBE"
                color = "#eab308"  # Yellow
            else:
                status = "no"
                label = "NO"
                color = "#9ca3af"  # Gray

            forecasts.append({
                "day": day_str,
                "day_label": day_labels[i] if i < len(day_labels) else f"Day {i+1}",
                "day_name": day_name,
                "inflow_cfs": inflow,
                "outflow_cfs": outflow,
                "pool_elevation_ft": pool,
                "runnable_status": status,
                "runnable_label": label,
                "runnable_color": color,
            })

        except Exception as e:
            print(f"[TVA] Error parsing prediction: {e}")
            continue

    return forecasts if forecasts else None


def generate_tva_forecast_html(site_code: str, runnable_threshold: int = 3000) -> str:
    """
    Generate HTML for the Dam Operations Forecast panel.

    Args:
        site_code: TVA site code (e.g., 'HADT1')
        runnable_threshold: CFS threshold for runnable conditions

    Returns:
        HTML string for the forecast panel, or empty string if no data
    """
    forecasts = get_tva_forecast(site_code, runnable_threshold)
    if not forecasts:
        return ""

    # Get site-specific display configuration (with defaults)
    default_config = {
        "title": f"{site_code} OPERATIONS FORECAST",
        "subtitle": f"Dam → River",
        "history_title": f"{site_code} Historical Dam Operations",
        "running_msg": "River is running!",
        "quiet_msg": "Dam quiet, no release",
        "filling_msg": "Release building up",
        "spillway_label": "Release starting",
        "runnable_msg": "River will run",
    }
    display = TVA_DISPLAY_CONFIG.get(site_code, default_config)

    # Get current observation for the header
    current = get_latest_tva_observation(site_code)
    current_outflow = current['discharge_cfs'] if current else 0
    current_pool = current['pool_elevation_ft'] if current else 0
    current_time = current.get('timestamp_str', '') if current else ''

    # Get all observations for the "story" table
    all_observations = fetch_tva_observed(site_code)

    # Get trend for current release
    current_trend = get_tva_trend(site_code, hours=4)
    trend_arrow = "↗" if current_trend == "rising" else "↘" if current_trend == "falling" else "→"
    trend_label = current_trend.title() if current_trend else "Steady"

    # Calculate current release gauge values
    max_gauge_cfs = 6000  # Max for visualization
    spillway_opens_cfs = 500  # CFS when release is noticeable
    current_pct = min(100, (current_outflow / max_gauge_cfs) * 100)
    threshold_pct_gauge = min(100, (runnable_threshold / max_gauge_cfs) * 100)
    spillway_pct_gauge = min(100, (spillway_opens_cfs / max_gauge_cfs) * 100)

    # Determine current status
    if current_outflow >= runnable_threshold:
        current_status = "RUNNABLE!"
        current_color = "#22c55e"  # Green
        status_desc = display["running_msg"]
    elif current_outflow >= runnable_threshold * 0.5:
        current_status = "GETTING CLOSE"
        current_color = "#eab308"  # Yellow
        status_desc = f"Need {runnable_threshold - current_outflow:,} more CFS"
    else:
        current_status = "TOO LOW"
        current_color = "#9ca3af"  # Gray
        status_desc = f"Need {runnable_threshold - current_outflow:,} more CFS"

    # Build the "Today's Story" table from observations
    story_rows = ""
    if all_observations:
        prev_discharge = None
        for obs in all_observations:
            try:
                time_str = obs.get("Time", "").replace(" EST", "").replace(" EDT", "")
                discharge = int(parse_tva_value(obs.get("AverageHourlyDischarge", "0")))
                pool = parse_tva_value(obs.get("ReservoirElevation", "0"))
                tailwater = parse_tva_value(obs.get("TailwaterElevation", "0"))

                # Determine what's happening (site-specific text)
                if discharge < 100:
                    event = display["quiet_msg"]
                    event_class = "event-quiet"
                elif discharge < 500:
                    event = "Minimal release"
                    event_class = "event-quiet"
                elif discharge < 1500:
                    event = "Release opening!"
                    event_class = "event-opening"
                elif discharge < runnable_threshold:
                    event = display["filling_msg"]
                    event_class = "event-filling"
                else:
                    event = "Full release - RUNNABLE!"
                    event_class = "event-runnable"

                # Check if this is a significant change
                is_change = prev_discharge is not None and abs(discharge - prev_discharge) > 500
                row_class = "story-highlight" if is_change else ""

                story_rows += f'''
                <tr class="{row_class}">
                    <td class="story-time">{time_str}</td>
                    <td class="story-pool">{pool:,.1f} ft</td>
                    <td class="story-tailwater">{tailwater:,.1f} ft</td>
                    <td class="story-discharge">{discharge:,} CFS</td>
                    <td class="story-event {event_class}">{event}</td>
                </tr>
                '''
                prev_discharge = discharge
            except Exception:
                continue

    # Build the 3-day forecast cards
    cards_html = ""
    for f in forecasts:
        # Calculate bar heights (max 100% at 5000 CFS for visualization)
        max_cfs = 5000
        inflow_pct = min(100, (f['inflow_cfs'] / max_cfs) * 100)
        outflow_pct = min(100, (f['outflow_cfs'] / max_cfs) * 100)
        threshold_pct = min(100, (runnable_threshold / max_cfs) * 100)

        cards_html += f'''
        <div class="forecast-card">
          <div class="forecast-day">{f['day_label']}</div>
          <div class="forecast-date">{f['day_name']} {f['day'].split('/')[0]}/{f['day'].split('/')[1]}</div>

          <div class="forecast-bars">
            <div class="bar-group">
              <div class="bar-label">In</div>
              <div class="bar-container">
                <div class="bar bar-inflow" style="height: {inflow_pct}%;"></div>
                <div class="threshold-line" style="bottom: {threshold_pct}%;"></div>
              </div>
              <div class="bar-value">{f['inflow_cfs']:,}</div>
            </div>
            <div class="bar-group">
              <div class="bar-label">Out</div>
              <div class="bar-container">
                <div class="bar bar-outflow" style="height: {outflow_pct}%; background: {f['runnable_color']};"></div>
                <div class="threshold-line" style="bottom: {threshold_pct}%;"></div>
              </div>
              <div class="bar-value">{f['outflow_cfs']:,}</div>
            </div>
          </div>

          <div class="forecast-status" style="background: {f['runnable_color']};">
            {f['runnable_label']}
          </div>

          <div class="forecast-pool">🌊 {f['pool_elevation_ft']:.1f} ft</div>
        </div>
        '''

    html = f'''
    <div class="forecast-panel">
      <div class="forecast-header">
        <div class="forecast-title">🌊 3-DAY {display["title"]}</div>
        <div class="forecast-subtitle">{display["subtitle"]}</div>
      </div>

      <div class="flow-diagram">
        <div class="flow-section">
          <div class="flow-label">INFLOW</div>
          <div class="flow-arrow">▶▶▶</div>
        </div>
        <div class="flow-section reservoir">
          <div class="reservoir-box">
            <div class="reservoir-label">RESERVOIR</div>
            <div class="reservoir-level">{current_pool:.1f} ft</div>
          </div>
        </div>
        <div class="flow-section">
          <div class="flow-arrow">▶▶▶</div>
          <div class="flow-label">OUTFLOW</div>
        </div>
      </div>

      <div class="current-release-panel">
        <div class="current-release-header">
          <div class="current-release-title">⚡ CURRENT RELEASE</div>
          <div class="current-release-time">Updated: {current_time}</div>
        </div>

        <div class="current-release-content">
          <div class="current-gauge-section">
            <div class="current-gauge">
              <div class="gauge-track">
                <div class="gauge-fill" style="width: {current_pct}%; background: {current_color};"></div>
                <div class="gauge-threshold spillway" style="left: {spillway_pct_gauge}%;"></div>
                <div class="gauge-threshold-label spillway" style="left: {spillway_pct_gauge}%;">💧 {spillway_opens_cfs:,}</div>
                <div class="gauge-threshold runnable" style="left: {threshold_pct_gauge}%;"></div>
                <div class="gauge-threshold-label runnable" style="left: {threshold_pct_gauge}%;">🚣 {runnable_threshold:,}</div>
              </div>
              <div class="gauge-labels">
                <span>0</span>
                <span>{max_gauge_cfs:,} CFS</span>
              </div>
            </div>
          </div>

          <div class="current-stats">
            <div class="current-cfs">
              <div class="current-cfs-value" style="color: {current_color};">{current_outflow:,}</div>
              <div class="current-cfs-unit">CFS</div>
            </div>
            <div class="current-trend">
              <span class="trend-arrow">{trend_arrow}</span>
              <span class="trend-text">{trend_label}</span>
            </div>
            <div class="current-status-box" style="background: {current_color};">
              {current_status}
            </div>
            <div class="current-status-desc">{status_desc}</div>
          </div>
        </div>
      </div>

      <div class="forecast-cards">
        {cards_html}
      </div>

      <div class="forecast-legend">
        <div class="legend-item">
          <div class="legend-line spillway"></div>
          <span>💧 Release: {spillway_opens_cfs:,} CFS - {display["spillway_label"]}</span>
        </div>
        <div class="legend-item">
          <div class="legend-line runnable"></div>
          <span>🚣 Runnable: {runnable_threshold:,} CFS - Good paddling conditions!</span>
        </div>
        <div class="legend-item">
          <div class="legend-box" style="background: #22c55e;"></div>
          <span>YES! - {display["runnable_msg"]}</span>
        </div>
        <div class="legend-item">
          <div class="legend-box" style="background: #eab308;"></div>
          <span>MAYBE - Close to threshold</span>
        </div>
        <div class="legend-item">
          <div class="legend-box" style="background: #9ca3af;"></div>
          <span>NO - Below threshold</span>
        </div>
      </div>

      <div class="story-section">
        <div class="story-header">
          <div class="story-title">📖 Today's Story - What's Happening at the Dam</div>
          <div class="story-subtitle">Hourly observations showing how the dam operates</div>
        </div>
        <div class="story-table-wrapper">
          <table class="story-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Lake Level</th>
                <th>Tailwater</th>
                <th>Release</th>
                <th>What's Happening</th>
              </tr>
            </thead>
            <tbody>
              {story_rows}
            </tbody>
          </table>
        </div>
        <div class="story-explainer">
          <div class="explainer-item">
            <strong>Lake Level</strong> = Water elevation in the reservoir (behind the dam)
          </div>
          <div class="explainer-item">
            <strong>Tailwater</strong> = Water level below the dam (start of whitewater section)
          </div>
          <div class="explainer-item">
            <strong>Release</strong> = How much water is flowing through the spillway
          </div>
        </div>
      </div>
    </div>

    <div class="history-section">
      <div class="history-header">
        <div class="history-title">📊 {display["history_title"]}</div>
        <div class="history-subtitle">Long-term trends - data accumulates over time</div>
      </div>
      <div class="history-controls">
        <button class="range-btn active" data-days="7">7 Days</button>
        <button class="range-btn" data-days="30">30 Days</button>
        <button class="range-btn" data-days="90">90 Days</button>
        <button class="range-btn" data-days="365">1 Year</button>
      </div>
      <div class="history-stats" id="historyStats">
        <div class="stat-card">
          <div class="stat-label">Observations</div>
          <div class="stat-value" id="statCount">--</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Max Release</div>
          <div class="stat-value" id="statMaxCfs">--</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Avg Release</div>
          <div class="stat-value" id="statAvgCfs">--</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Data Range</div>
          <div class="stat-value" id="statRange">--</div>
        </div>
      </div>
      <div class="history-chart-container">
        <canvas id="historyChart"></canvas>
      </div>
      <div class="history-legend">
        <div class="legend-row">
          <span class="legend-color" style="background: #ef4444;"></span>
          <span>Release (CFS) - Left Axis</span>
        </div>
        <div class="legend-row">
          <span class="legend-color" style="background: #3b82f6;"></span>
          <span>Lake Level (ft) - Right Axis</span>
        </div>
        <div class="legend-row">
          <span class="legend-color" style="background: #10b981;"></span>
          <span>Tailwater (ft) - Right Axis</span>
        </div>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
    (function() {{
      const siteCode = '{site_code}';
      let historyChart = null;

      async function loadHistoryData(days) {{
        try {{
          const response = await fetch(`/api/tva-history/${{siteCode}}?days=${{days}}`);
          const data = await response.json();
          return data;
        }} catch (err) {{
          console.error('Failed to load history:', err);
          return null;
        }}
      }}

      function updateStats(data) {{
        document.getElementById('statCount').textContent = data.observation_count || '--';

        if (data.stats && data.stats.discharge_cfs) {{
          document.getElementById('statMaxCfs').textContent =
            data.stats.discharge_cfs.max ? data.stats.discharge_cfs.max.toLocaleString() + ' CFS' : '--';
          document.getElementById('statAvgCfs').textContent =
            data.stats.discharge_cfs.avg ? Math.round(data.stats.discharge_cfs.avg).toLocaleString() + ' CFS' : '--';
        }}

        if (data.date_range && data.date_range.earliest) {{
          const earliest = new Date(data.date_range.earliest);
          const latest = new Date(data.date_range.latest);
          const diffDays = Math.round((latest - earliest) / (1000 * 60 * 60 * 24));
          document.getElementById('statRange').textContent = diffDays + ' days';
        }} else {{
          document.getElementById('statRange').textContent = '--';
        }}
      }}

      function renderChart(data) {{
        const ctx = document.getElementById('historyChart').getContext('2d');

        if (historyChart) {{
          historyChart.destroy();
        }}

        if (!data.observations || data.observations.length === 0) {{
          ctx.canvas.parentElement.innerHTML =
            '<div style="padding:40px;text-align:center;color:#666;">' +
            '<p style="font-size:18px;">📊 No historical data yet</p>' +
            '<p>Data will accumulate as the system runs. Check back soon!</p></div>';
          return;
        }}

        const labels = data.observations.map(o => {{
          const d = new Date(o.timestamp);
          return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric', hour: 'numeric' }});
        }});

        const cfsData = data.observations.map(o => o.discharge_cfs);
        const poolData = data.observations.map(o => o.pool_elevation_ft);
        const tailwaterData = data.observations.map(o => o.tailwater_ft);

        historyChart = new Chart(ctx, {{
          type: 'line',
          data: {{
            labels: labels,
            datasets: [
              {{
                label: 'Release (CFS)',
                data: cfsData,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                yAxisID: 'y',
                pointRadius: 1,
                pointHoverRadius: 4
              }},
              {{
                label: 'Lake Level (ft)',
                data: poolData,
                borderColor: '#3b82f6',
                borderWidth: 2,
                fill: false,
                tension: 0.3,
                yAxisID: 'y1',
                pointRadius: 0,
                pointHoverRadius: 3
              }},
              {{
                label: 'Tailwater (ft)',
                data: tailwaterData,
                borderColor: '#10b981',
                borderWidth: 2,
                fill: false,
                tension: 0.3,
                yAxisID: 'y1',
                pointRadius: 0,
                pointHoverRadius: 3
              }}
            ]
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
                  text: 'Release (CFS)',
                  color: '#ef4444'
                }},
                ticks: {{ color: '#ef4444' }},
                grid: {{ color: 'rgba(239, 68, 68, 0.1)' }}
              }},
              y1: {{
                type: 'linear',
                display: true,
                position: 'right',
                title: {{
                  display: true,
                  text: 'Elevation (ft)',
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
    </script>

    <style>
    .forecast-panel {{
      background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
      border-radius: 12px;
      padding: 24px;
      margin: 20px 0;
      color: white;
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }}
    .forecast-header {{
      text-align: center;
      margin-bottom: 20px;
    }}
    .forecast-title {{
      font-size: 20px;
      font-weight: bold;
      margin-bottom: 4px;
    }}
    .forecast-subtitle {{
      font-size: 14px;
      opacity: 0.8;
    }}
    .flow-diagram {{
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 8px;
      margin: 20px 0;
      padding: 16px;
      background: rgba(255,255,255,0.1);
      border-radius: 8px;
    }}
    .flow-section {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .flow-label {{
      font-size: 12px;
      font-weight: bold;
      text-transform: uppercase;
      opacity: 0.9;
    }}
    .flow-arrow {{
      color: #60a5fa;
      font-size: 16px;
      animation: flow 1.5s ease-in-out infinite;
    }}
    @keyframes flow {{
      0%, 100% {{ opacity: 0.5; }}
      50% {{ opacity: 1; }}
    }}
    .reservoir-box {{
      background: linear-gradient(180deg, #3b82f6 0%, #1d4ed8 100%);
      padding: 12px 24px;
      border-radius: 8px;
      text-align: center;
      border: 2px solid rgba(255,255,255,0.3);
    }}
    .reservoir-label {{
      font-size: 11px;
      text-transform: uppercase;
      opacity: 0.8;
      margin-bottom: 4px;
    }}
    .reservoir-level {{
      font-size: 18px;
      font-weight: bold;
    }}
    .current-release-panel {{
      background: rgba(0,0,0,0.3);
      border-radius: 12px;
      padding: 20px;
      margin: 20px 0;
    }}
    .current-release-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }}
    .current-release-title {{
      font-size: 16px;
      font-weight: bold;
    }}
    .current-release-time {{
      font-size: 12px;
      opacity: 0.7;
    }}
    .current-release-content {{
      display: grid;
      grid-template-columns: 1fr 200px;
      gap: 24px;
      align-items: center;
    }}
    .current-gauge {{
      width: 100%;
    }}
    .gauge-track {{
      height: 32px;
      background: rgba(0,0,0,0.4);
      border-radius: 16px;
      position: relative;
      overflow: visible;
    }}
    .gauge-fill {{
      height: 100%;
      border-radius: 16px;
      transition: width 0.5s ease;
      box-shadow: 0 0 10px rgba(255,255,255,0.3);
    }}
    .gauge-threshold {{
      position: absolute;
      top: -8px;
      bottom: -8px;
      width: 4px;
      border-radius: 2px;
      transform: translateX(-50%);
    }}
    .gauge-threshold.spillway {{
      background: #38bdf8;
      box-shadow: 0 0 8px #38bdf8;
    }}
    .gauge-threshold.runnable {{
      background: #ef4444;
      box-shadow: 0 0 8px #ef4444;
    }}
    .gauge-threshold-label {{
      position: absolute;
      transform: translateX(-50%);
      font-size: 11px;
      font-weight: bold;
      white-space: nowrap;
    }}
    .gauge-threshold-label.spillway {{
      bottom: -20px;
      color: #38bdf8;
    }}
    .gauge-threshold-label.runnable {{
      top: -24px;
      color: #ef4444;
    }}
    .gauge-labels {{
      display: flex;
      justify-content: space-between;
      margin-top: 24px;
      font-size: 11px;
      opacity: 0.6;
    }}
    .current-stats {{
      text-align: center;
    }}
    .current-cfs {{
      margin-bottom: 8px;
    }}
    .current-cfs-value {{
      font-size: 48px;
      font-weight: bold;
      line-height: 1;
    }}
    .current-cfs-unit {{
      font-size: 14px;
      opacity: 0.7;
    }}
    .current-trend {{
      margin-bottom: 12px;
      font-size: 16px;
    }}
    .trend-arrow {{
      font-size: 20px;
      margin-right: 4px;
    }}
    .current-status-box {{
      display: inline-block;
      padding: 8px 20px;
      border-radius: 20px;
      font-weight: bold;
      font-size: 14px;
      margin-bottom: 8px;
    }}
    .current-status-desc {{
      font-size: 12px;
      opacity: 0.8;
    }}
    @media (max-width: 600px) {{
      .current-release-content {{
        grid-template-columns: 1fr;
      }}
      .current-stats {{
        order: -1;
      }}
    }}
    .forecast-cards {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin: 20px 0;
    }}
    .forecast-card {{
      background: rgba(255,255,255,0.1);
      border-radius: 12px;
      padding: 16px;
      text-align: center;
    }}
    .forecast-day {{
      font-size: 16px;
      font-weight: bold;
      margin-bottom: 2px;
    }}
    .forecast-date {{
      font-size: 12px;
      opacity: 0.7;
      margin-bottom: 12px;
    }}
    .forecast-bars {{
      display: flex;
      justify-content: center;
      gap: 16px;
      margin-bottom: 12px;
    }}
    .bar-group {{
      text-align: center;
    }}
    .bar-label {{
      font-size: 10px;
      text-transform: uppercase;
      opacity: 0.7;
      margin-bottom: 4px;
    }}
    .bar-container {{
      width: 32px;
      height: 80px;
      background: rgba(0,0,0,0.3);
      border-radius: 4px;
      position: relative;
      overflow: hidden;
    }}
    .bar {{
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      border-radius: 4px 4px 0 0;
      transition: height 0.5s ease;
    }}
    .bar-inflow {{
      background: #60a5fa;
    }}
    .bar-outflow {{
      background: #22c55e;
    }}
    .threshold-line {{
      position: absolute;
      left: -4px;
      right: -4px;
      height: 2px;
      background: #ef4444;
      box-shadow: 0 0 4px #ef4444;
    }}
    .bar-value {{
      font-size: 11px;
      margin-top: 4px;
      font-weight: 500;
    }}
    .forecast-status {{
      display: inline-block;
      padding: 6px 16px;
      border-radius: 20px;
      font-weight: bold;
      font-size: 14px;
      margin-bottom: 8px;
    }}
    .forecast-pool {{
      font-size: 12px;
      opacity: 0.8;
    }}
    .forecast-legend {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 16px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid rgba(255,255,255,0.2);
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      opacity: 0.9;
    }}
    .legend-line {{
      width: 20px;
      height: 3px;
      border-radius: 2px;
    }}
    .legend-line.spillway {{
      background: #38bdf8;
      box-shadow: 0 0 4px #38bdf8;
    }}
    .legend-line.runnable {{
      background: #ef4444;
      box-shadow: 0 0 4px #ef4444;
    }}
    .legend-box {{
      width: 14px;
      height: 14px;
      border-radius: 4px;
    }}
    @media (max-width: 600px) {{
      .forecast-cards {{
        grid-template-columns: 1fr;
      }}
      .flow-diagram {{
        flex-direction: column;
      }}
    }}
    .story-section {{
      margin-top: 24px;
      padding-top: 24px;
      border-top: 1px solid rgba(255,255,255,0.2);
    }}
    .story-header {{
      text-align: center;
      margin-bottom: 16px;
    }}
    .story-title {{
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 4px;
    }}
    .story-subtitle {{
      font-size: 13px;
      opacity: 0.7;
    }}
    .story-table-wrapper {{
      overflow-x: auto;
      margin: 16px 0;
    }}
    .story-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .story-table th {{
      background: rgba(0,0,0,0.3);
      padding: 10px 12px;
      text-align: left;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }}
    .story-table th:nth-child(2),
    .story-table th:nth-child(3),
    .story-table th:nth-child(4) {{
      text-align: center;
      width: 120px;
    }}
    .story-table td {{
      padding: 10px 12px;
      border-bottom: 1px solid rgba(255,255,255,0.1);
    }}
    .story-table tr:hover {{
      background: rgba(255,255,255,0.05);
    }}
    .story-table tr.story-highlight {{
      background: rgba(234,179,8,0.2);
    }}
    .story-table tr.story-highlight:hover {{
      background: rgba(234,179,8,0.3);
    }}
    .story-time {{
      font-weight: 600;
      white-space: nowrap;
      width: 80px;
    }}
    .story-pool, .story-tailwater {{
      font-family: monospace;
      text-align: center;
      width: 120px;
    }}
    .story-discharge {{
      font-family: monospace;
      font-weight: bold;
      text-align: center;
      width: 120px;
    }}
    .story-event {{
      font-style: italic;
    }}
    .event-quiet {{
      color: #9ca3af;
    }}
    .event-opening {{
      color: #fbbf24;
    }}
    .event-filling {{
      color: #60a5fa;
    }}
    .event-runnable {{
      color: #4ade80;
      font-weight: bold;
    }}
    .story-explainer {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      justify-content: center;
      padding: 16px;
      background: rgba(0,0,0,0.2);
      border-radius: 8px;
      font-size: 12px;
    }}
    .explainer-item {{
      opacity: 0.9;
    }}
    .explainer-item strong {{
      color: #60a5fa;
    }}
    @media (max-width: 600px) {{
      .story-table {{
        font-size: 11px;
      }}
      .story-table th, .story-table td {{
        padding: 8px 6px;
      }}
      .story-explainer {{
        flex-direction: column;
        gap: 8px;
      }}
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
    .stat-label {{
      font-size: 11px;
      text-transform: uppercase;
      opacity: 0.7;
      margin-bottom: 4px;
    }}
    .stat-value {{
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
    </style>
    '''

    return html


def main():
    """Test TVA fetch for all known sites."""
    print("TVA Dam Observations")
    print("=" * 60)

    for site_code, info in TVA_SITES.items():
        print(f"\n{info['name']} ({site_code})")
        print("-" * 40)

        obs = get_latest_tva_observation(site_code)

        if obs:
            trend = get_tva_trend(site_code)
            print(f"  Discharge:    {obs['discharge_cfs']:,} CFS")
            print(f"  Pool Level:   {obs['pool_elevation_ft']:.2f} ft MSL")
            print(f"  Tailwater:    {obs['tailwater_ft']:.2f} ft MSL")
            print(f"  Trend:        {trend or 'unknown'}")
            print(f"  Updated:      {obs['timestamp_str']}")
            print(f"  Releasing:    {'YES' if obs['is_releasing'] else 'No'}")
        else:
            print("  ERROR: Could not fetch data")


if __name__ == "__main__":
    main()

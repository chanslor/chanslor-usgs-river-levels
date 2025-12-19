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
    "DUGT1": {
        "name": "Douglas Dam",
        "description": "Douglas Dam on French Broad River",
        "lat": 36.0,
        "lon": -83.5,
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

#!/usr/bin/env python3
"""
Get current temp (°F) and wind speed (mph) for creek / river spots
using nearby NOAA/NWS stations.

Spots & Stations:
- Town Creek (Geraldine, AL)      -> KBFZ  (Albertville Regional Airport)
- South Sauty (Rainsville, AL)    -> K4A9  (Fort Payne / Isbell Field Airport)
- Little River (Fort Payne, AL)   -> K4A9  (same as above)
- Locust Fork (Cleveland, AL)     -> KCMD  (Cullman Regional Airport / Folsom Field)
"""

import json
import urllib.request
import math
from datetime import datetime, timezone

# Map paddling spots to their NOAA/NWS station IDs
SPOTS = {
    "Town Creek (Geraldine, AL)": "KBFZ",
    "South Sauty (Rainsville, AL)": "K4A9",
    "Little River (Fort Payne, AL)": "K4A9",
    "Locust Fork (Cleveland, AL)": "KCMD",
}

API_BASE = "https://api.weather.gov/stations/{station}/observations/latest"

# User-Agent you requested
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

def c_to_f(celsius_val):
    """Convert Celsius to Fahrenheit. Return None if input is None."""
    if celsius_val is None:
        return None
    return (celsius_val * 9.0 / 5.0) + 32.0

def ms_to_mph(ms_val):
    """Convert meters/sec to miles/hour. Return None if input is None."""
    if ms_val is None:
        return None
    return ms_val * 2.23694

def fetch_latest_observation(station_id):
    """
    Call api.weather.gov for a given station and return parsed fields.

    Returns dict with:
      {
        "obs_time_utc": str,
        "temp_f": float|None,
        "wind_mph": float|None,
        "wind_dir_deg": float|None,
        "wind_gust_mph": float|None
      }

    Raises Exception if HTTP fails.
    """
    url = API_BASE.format(station=station_id)

    headers = {
        # Browser-style UA you provided
        "User-Agent": USER_AGENT,
        # Ask for NOAA's GeoJSON/JSON
        "Accept": "application/geo+json, application/json;q=0.9",
        "Accept-Language": "en-US,en;q=0.8",
        # IMPORTANT: leave out Accept-Encoding so we get plain text back
        "Connection": "close",
    }

    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()  # should now be plain UTF-8 JSON

    data = json.loads(raw)
    props = data.get("properties", {})

    # Extract raw values from API
    temp_c = props.get("temperature", {}).get("value")
    wind_ms = props.get("windSpeed", {}).get("value")
    gust_ms = props.get("windGust", {}).get("value")
    wind_dir = props.get("windDirection", {}).get("value")
    obs_time = props.get("timestamp")

    # Convert to friendlier units
    temp_f = c_to_f(temp_c)
    wind_mph = ms_to_mph(wind_ms)
    gust_mph = ms_to_mph(gust_ms)

    # Round for nicer output (but keep None as None)
    def _r(v):
        if v is None:
            return None
        return round(v, 1)

    return {
        "obs_time_utc": obs_time,
        "temp_f": _r(temp_f),
        "wind_mph": _r(wind_mph),
        "wind_gust_mph": _r(gust_mph),
        "wind_dir_deg": wind_dir,
    }

def fmt_dir(deg):
    """
    Convert wind direction (degrees) into a compass string like WNW.
    Returns 'calm/variable' if deg is None or NaN.
    """
    if deg is None:
        return "calm/variable"
    try:
        if math.isnan(deg):
            return "calm/variable"
    except TypeError:
        # deg wasn't a float, ignore math.isnan on it
        pass

    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW"
    ]
    # each sector is 22.5 degrees
    idx = int((deg + 11.25) // 22.5) % 16
    return dirs[idx]

def main():
    print("NOAA / NWS Latest Observations")
    print("Generated at:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"))
    print("-" * 60)

    for spot, station in SPOTS.items():
        try:
            obs = fetch_latest_observation(station)
        except Exception as e:
            print(f"{spot} [{station}]")
            print(f"  ERROR: could not fetch data for station {station}")
            print(f"  Details: {e}")
            print(f"  Try curl with same headers to confirm access:")
            print(f"    curl -H 'User-Agent: {USER_AGENT}' "
                  f"-H 'Accept: application/geo+json' "
                  f"-H 'Accept-Language: en-US,en;q=0.8' "
                  f'https://api.weather.gov/stations/{station}/observations/latest')
            print("-" * 60)
            continue

        temp_f = obs["temp_f"]
        wind_mph = obs["wind_mph"]
        gust_mph = obs["wind_gust_mph"]
        wdir_deg = obs["wind_dir_deg"]
        obs_time = obs["obs_time_utc"]

        # Build readable strings
        temp_str = f"{temp_f} °F" if temp_f is not None else "N/A"

        if wind_mph is None:
            wind_str = "N/A"
        else:
            wind_str = f"{wind_mph} mph {fmt_dir(wdir_deg)}"
            if gust_mph is not None:
                wind_str += f" (gust {gust_mph} mph)"

        print(f"{spot} [{station}]")
        print(f"  Obs Time (UTC): {obs_time}")
        print(f"  Air Temp:       {temp_str}")
        print(f"  Wind:           {wind_str}")
        print("-" * 60)

if __name__ == "__main__":
    main()


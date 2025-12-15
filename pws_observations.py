#!/usr/bin/env python3
"""
Get current temp (F) and wind speed (mph) from Weather Underground
Personal Weather Stations (PWS) for river/creek spots.

Uses the embedded public API key from Weather Underground's website.
Tries multiple stations in order until one works (fallback chain).

Station lists from GPS.txt - curated for each river location.
"""

import json
import urllib.request
import math
from datetime import datetime, timezone

# Weather Underground embedded public API key (from their website)
WU_API_KEY = "e1f10a1e78da46f5b10a1e78da96f525"
WU_API_BASE = "https://api.weather.com/v2/pws/observations/current"

# PWS station fallback chains for each river
# Try stations in order - first working station wins
PWS_STATIONS = {
    "Locust Fork": ["KALBLOUN24", "KALBLOUN23", "KALHANCE17", "KALONEON42"],
    "Short Creek": ["KALGUNTE26", "KALALBER97", "KALALBER66", "KALALBER69"],
    "Town Creek": ["KALFYFFE7", "KALFYFFE11", "KALALBER111", "KALGROVE15"],
    "South Sauty": ["KALLANGS7", "KALGROVE15", "KALFYFFE11", "KALRAINS14"],
    "Little River Canyon": ["KALCEDAR14", "KALGAYLE19", "KALGAYLE16", "KALGAYLE7"],
    "Little River": ["KALCEDAR14", "KALGAYLE19", "KALGAYLE16", "KALGAYLE7"],  # alias
    "Mulberry Fork": ["KALHAYDE19", "KALHAYDE21", "KALHAYDE13", "KALWARRI54"],
}

# Friendly labels for display
PWS_LABELS = {
    "KALBLOUN24": "BLNTVL",   # Blountsville
    "KALBLOUN23": "BLNTVL",   # Blountsville
    "KALHANCE17": "STPVL",    # Steppville
    "KALONEON42": "ONEONT",   # Oneonta
    "KALGUNTE26": "GNTVL",    # Guntersville Shores
    "KALALBER97": "ALBVL",    # Albertville
    "KALALBER66": "ALBVL",    # Albertville
    "KALALBER69": "ALBVL",    # Albertville
    "KALFYFFE7": "FYFFE",     # Lakeview/Fyffe
    "KALFYFFE11": "FYFFE",    # Moores Crossroads
    "KALALBER111": "ALBVL",   # Albertville
    "KALGROVE15": "GRVOAK",   # Groveoak
    "KALLANGS7": "LNGSTN",    # Langston
    "KALRAINS14": "RNSVL",    # Rainsville
    "KALCEDAR14": "CDBLF",    # Cedar Bluff
    "KALGAYLE19": "BRMTWN",   # Broomtown
    "KALGAYLE16": "GYLSVL",   # Gaylesville
    "KALGAYLE7": "GYLSVL",    # Gaylesville
    "KALHAYDE19": "BANGOR",   # Bangor
    "KALHAYDE21": "HAYDEN",   # Hayden
    "KALHAYDE13": "HAYDEN",   # Hayden
    "KALWARRI54": "SMOKRS",   # Smoke Rise
}

# Browser-style User-Agent
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_pws_observation(station_id):
    """
    Fetch current observations from a Weather Underground PWS station.

    Returns dict with:
        {
            "station_id": str,
            "neighborhood": str,
            "obs_time_utc": str,
            "obs_time_local": str,
            "temp_f": float|None,
            "wind_mph": float|None,
            "wind_gust_mph": float|None,
            "wind_dir_deg": float|None,
            "humidity": float|None,
            "pressure_in": float|None,
            "precip_today_in": float|None,
        }

    Returns None if station doesn't respond or has no data.
    """
    url = (
        f"{WU_API_BASE}?apiKey={WU_API_KEY}"
        f"&stationId={station_id}"
        f"&numericPrecision=decimal&format=json&units=e"
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            # 204 = no content (station offline or no data)
            if resp.status == 204:
                return None

            data = json.loads(resp.read())
            observations = data.get("observations", [])

            if not observations:
                return None

            obs = observations[0]
            imp = obs.get("imperial", {})

            return {
                "station_id": obs.get("stationID", station_id),
                "neighborhood": obs.get("neighborhood", "Unknown"),
                "obs_time_utc": obs.get("obsTimeUtc"),
                "obs_time_local": obs.get("obsTimeLocal"),
                "temp_f": imp.get("temp"),
                "wind_mph": imp.get("windSpeed"),
                "wind_gust_mph": imp.get("windGust"),
                "wind_dir_deg": obs.get("winddir"),
                "humidity": obs.get("humidity"),
                "pressure_in": imp.get("pressure"),
                "precip_today_in": imp.get("precipTotal"),
            }

    except Exception as e:
        # Station unreachable or error - return None to try next
        return None


def fetch_observation_for_river(river_name):
    """
    Fetch weather observation for a river, trying PWS stations in order.

    Args:
        river_name: Name of the river (must match key in PWS_STATIONS)

    Returns:
        Tuple of (observation_dict, station_id) or (None, None) if all fail
    """
    stations = PWS_STATIONS.get(river_name, [])

    for station_id in stations:
        obs = fetch_pws_observation(station_id)
        if obs and obs.get("temp_f") is not None:
            return obs, station_id

    return None, None


def get_station_label(station_id):
    """Get friendly label for a PWS station ID."""
    return PWS_LABELS.get(station_id, station_id[:6])


def fmt_wind_dir(deg):
    """
    Convert wind direction (degrees) into a compass string like WNW.
    Returns 'calm' if deg is None.
    """
    if deg is None:
        return "calm"

    try:
        if math.isnan(deg):
            return "calm"
    except (TypeError, ValueError):
        pass

    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW"
    ]
    idx = int((deg + 11.25) // 22.5) % 16
    return dirs[idx]


def main():
    """Test all river PWS stations."""
    print("Weather Underground PWS Observations")
    print("Generated at:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"))
    print("-" * 60)

    for river_name in PWS_STATIONS.keys():
        if river_name == "Little River":  # skip alias
            continue

        obs, station_id = fetch_observation_for_river(river_name)

        if obs:
            label = get_station_label(station_id)
            temp_str = f"{obs['temp_f']}°F" if obs['temp_f'] is not None else "N/A"
            wind_str = f"{obs['wind_mph']} mph" if obs['wind_mph'] is not None else "N/A"
            wind_dir = fmt_wind_dir(obs['wind_dir_deg'])

            print(f"{river_name} [{station_id} / {label}]")
            print(f"  Location:  {obs['neighborhood']}")
            print(f"  Temp:      {temp_str}")
            print(f"  Wind:      {wind_str} {wind_dir}")
            print(f"  Humidity:  {obs['humidity']}%")
            print(f"  Updated:   {obs['obs_time_local']}")
        else:
            print(f"{river_name}")
            print(f"  ERROR: All PWS stations failed")

        print("-" * 60)


if __name__ == "__main__":
    main()

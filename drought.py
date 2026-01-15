#!/usr/bin/env python3
"""
US Drought Monitor integration for river gauge dashboard.

Fetches drought status by county FIPS code from the USDM REST API.
https://droughtmonitor.unl.edu/DmData/DataDownload/WebServiceInfo.aspx

Drought Categories:
  - None: No drought
  - D0: Abnormally Dry
  - D1: Moderate Drought
  - D2: Severe Drought
  - D3: Extreme Drought
  - D4: Exceptional Drought
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# USDM API endpoint
USDM_API = "https://usdmdataservices.unl.edu/api/CountyStatistics/GetDroughtSeverityStatisticsByArea"

# Drought level descriptions and display info
DROUGHT_LEVELS = {
    "none": {"level": -1, "name": "None", "description": "No Drought", "color": "#4ade80", "emoji": ""},
    "d0": {"level": 0, "name": "D0", "description": "Abnormally Dry", "color": "#e89b3c", "emoji": "Drought Monitor:"},
    "d1": {"level": 1, "name": "D1", "description": "Moderate Drought", "color": "#fcd37f", "emoji": "Drought Monitor:"},
    "d2": {"level": 2, "name": "D2", "description": "Severe Drought", "color": "#ffaa00", "emoji": "Drought Monitor:"},
    "d3": {"level": 3, "name": "D3", "description": "Extreme Drought", "color": "#e60000", "emoji": "Drought Monitor:"},
    "d4": {"level": 4, "name": "D4", "description": "Exceptional Drought", "color": "#730000", "emoji": "Drought Monitor:"},
}

# Cache settings
DEFAULT_CACHE_TTL_HOURS = 12  # Drought data updates weekly, so 12 hours is plenty


class DroughtClient:
    """Client for fetching drought data from USDM API with SQLite caching."""

    def __init__(self, cache_db: Optional[str] = None, cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS) -> None:
        """
        Initialize drought client.

        Args:
            cache_db: Path to SQLite cache database (optional)
            cache_ttl_hours: Hours to cache drought data (default 12)
        """
        self.cache_db = cache_db
        self.cache_ttl_seconds = cache_ttl_hours * 3600
        if cache_db:
            self._init_cache_table()

    def _init_cache_table(self) -> None:
        """Create cache table if it doesn't exist."""
        with sqlite3.connect(self.cache_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS drought_cache (
                    fips TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    fetched_at REAL NOT NULL
                )
            """)
            conn.commit()

    def _get_cached(self, fips: str) -> Optional[Dict[str, Any]]:
        """Get cached drought data if still valid."""
        if not self.cache_db:
            return None
        try:
            with sqlite3.connect(self.cache_db) as conn:
                row = conn.execute(
                    "SELECT data, fetched_at FROM drought_cache WHERE fips = ?",
                    (fips,)
                ).fetchone()
                if row:
                    data, fetched_at = row
                    if time.time() - fetched_at < self.cache_ttl_seconds:
                        return json.loads(data)
        except Exception:
            pass
        return None

    def _set_cached(self, fips: str, data: Dict[str, Any]) -> None:
        """Store drought data in cache."""
        if not self.cache_db:
            return
        try:
            with sqlite3.connect(self.cache_db) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO drought_cache (fips, data, fetched_at) VALUES (?, ?, ?)",
                    (fips, json.dumps(data), time.time())
                )
                conn.commit()
        except Exception:
            pass

    def fetch_drought_status(self, fips: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current drought status for a county by FIPS code.

        Args:
            fips: 5-digit county FIPS code (e.g., "01009" for Blount County, AL)

        Returns:
            Dict with drought info or None if fetch fails:
            {
                "fips": "01009",
                "county": "Blount County",
                "state": "AL",
                "level": "d0",  # Worst drought level
                "level_num": 0,  # Numeric level (-1 to 4)
                "name": "D0",
                "description": "Abnormally Dry",
                "color": "#ffff00",
                "emoji": "Drought Monitor:",
                "map_date": "2025-12-09",
                "area_sq_mi": {
                    "none": 0.0,
                    "d0": 653.15,
                    "d1": 0.0,
                    "d2": 0.0,
                    "d3": 0.0,
                    "d4": 0.0
                }
            }
        """
        # Check cache first
        cached = self._get_cached(fips)
        if cached:
            return cached

        # Fetch from API
        try:
            # Get last 7 days of data (API requires date range)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            url = (
                f"{USDM_API}?"
                f"aoi={fips}&"
                f"startdate={start_date.strftime('%-m/%-d/%Y')}&"
                f"enddate={end_date.strftime('%-m/%-d/%Y')}&"
                f"statisticsType=1"
            )

            req = Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "RiverGaugeDashboard/1.0"
            })

            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if not data:
                return None

            # Get most recent entry
            latest = data[0]

            # Extract area values
            area_sq_mi = {
                "none": float(latest.get("none", 0)),
                "d0": float(latest.get("d0", 0)),
                "d1": float(latest.get("d1", 0)),
                "d2": float(latest.get("d2", 0)),
                "d3": float(latest.get("d3", 0)),
                "d4": float(latest.get("d4", 0)),
            }

            # Determine worst drought level (highest D-level with any area)
            worst_level = "none"
            for level in ["d4", "d3", "d2", "d1", "d0"]:
                if area_sq_mi[level] > 0:
                    worst_level = level
                    break

            # If no drought levels have area, check if "none" has area
            if worst_level == "none" and area_sq_mi["none"] == 0:
                # All zeros - might be data issue, but treat as no drought
                pass

            level_info = DROUGHT_LEVELS[worst_level]

            result = {
                "fips": fips,
                "county": latest.get("county", ""),
                "state": latest.get("state", ""),
                "level": worst_level,
                "level_num": level_info["level"],
                "name": level_info["name"],
                "description": level_info["description"],
                "color": level_info["color"],
                "emoji": level_info["emoji"],
                "map_date": latest.get("mapDate", "")[:10],  # Just the date part
                "area_sq_mi": area_sq_mi
            }

            # Cache the result
            self._set_cached(fips, result)

            return result

        except (URLError, HTTPError, json.JSONDecodeError, KeyError, IndexError) as e:
            # Return None on any error - caller should handle gracefully
            return None


def get_drought_display_html(drought_data: Optional[Dict[str, Any]], css_class: str = "drought-info") -> str:
    """
    Generate HTML snippet for displaying drought status.

    Args:
        drought_data: Dict from fetch_drought_status()
        css_class: CSS class for the container div

    Returns:
        HTML string like: <div class="drought-info">Drought Monitor: <span style="color:#ffff00">D0 Abnormally Dry</span></div>
    """
    if not drought_data:
        return ""

    level = drought_data.get("level", "none")

    # Don't show anything if no drought
    if level == "none":
        return ""

    emoji = drought_data.get("emoji", "Drought Monitor:")
    name = drought_data.get("name", "")
    description = drought_data.get("description", "")
    color = drought_data.get("color", "#888")

    return f'<div class="{css_class}">{emoji} <span class="drought-level" style="color:{color}">{name} {description}</span></div>'


# CLI for testing
if __name__ == "__main__":
    import sys

    # Test FIPS codes for Alabama rivers
    test_fips = {
        "01009": "Blount County (Locust Fork, Mulberry Fork)",
        "01049": "DeKalb County (Town Creek, Little River Canyon)",
        "01095": "Marshall County (South Sauty, Short Creek)",
    }

    fips_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if fips_arg:
        test_fips = {fips_arg: "User-specified"}

    client = DroughtClient()

    for fips, desc in test_fips.items():
        print(f"\n=== {desc} (FIPS: {fips}) ===")
        result = client.fetch_drought_status(fips)
        if result:
            print(f"County: {result['county']}, {result['state']}")
            print(f"Drought Level: {result['name']} - {result['description']}")
            print(f"Map Date: {result['map_date']}")
            print(f"Area (sq mi): {result['area_sq_mi']}")
            print(f"HTML: {get_drought_display_html(result)}")
        else:
            print("Failed to fetch drought data")

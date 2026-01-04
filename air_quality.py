#!/usr/bin/env python3
"""
air_quality.py — Fetch air quality data from Open-Meteo Air Quality API.

- Uses Open-Meteo (no auth required for non-commercial use):
  https://air-quality-api.open-meteo.com/v1/air-quality

- Returns US AQI, PM2.5, PM10, Ozone, and category/color coding.
- Simple SQLite cache to reduce API calls (configurable TTL).
"""

from __future__ import annotations
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

import requests

# AQI category definitions (US EPA standard)
AQI_CATEGORIES = [
    (50, "Good", "#00e400"),           # Green
    (100, "Moderate", "#ffff00"),       # Yellow
    (150, "Unhealthy for Sensitive", "#ff7e00"),  # Orange
    (200, "Unhealthy", "#ff0000"),      # Red
    (300, "Very Unhealthy", "#8f3f97"), # Purple
    (500, "Hazardous", "#7e0023"),      # Maroon
]


@dataclass
class AirQualityData:
    """Container for air quality readings."""
    aqi: int
    pm2_5: float
    pm10: float
    ozone: float
    carbon_monoxide: float
    category: str
    color: str
    timestamp: str
    latitude: float
    longitude: float

    def to_dict(self) -> dict:
        return {
            "aqi": self.aqi,
            "pm2_5": self.pm2_5,
            "pm10": self.pm10,
            "ozone": self.ozone,
            "carbon_monoxide": self.carbon_monoxide,
            "category": self.category,
            "color": self.color,
            "timestamp": self.timestamp,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


def get_aqi_category(aqi: int) -> tuple[str, str]:
    """Return (category_name, hex_color) for a given AQI value."""
    for threshold, name, color in AQI_CATEGORIES:
        if aqi <= threshold:
            return name, color
    return "Hazardous", "#7e0023"


class AirQualityClient:
    """Client for Open-Meteo Air Quality API with SQLite caching."""

    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(
        self,
        cache_path: str = os.environ.get("AQI_CACHE", "aqi_cache.sqlite"),
        ttl_hours: int = int(os.environ.get("AQI_TTL_HOURS", "1")),
        timeout: int = 15,
    ):
        self.ttl = ttl_hours * 3600
        self.timeout = timeout
        self.cache_path = cache_path
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "usgs-river-alert/1.0",
            "Accept": "application/json",
        })
        self._init_cache()

    def _init_cache(self):
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aqi_cache (
                    key TEXT PRIMARY KEY,
                    fetched_at INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _cache_get(self, key: str) -> Optional[dict]:
        now = int(time.time())
        conn = sqlite3.connect(self.cache_path)
        try:
            cur = conn.execute(
                "SELECT fetched_at, payload FROM aqi_cache WHERE key = ?", (key,)
            )
            row = cur.fetchone()
            if not row:
                return None
            fetched_at, payload = row
            if now - fetched_at > self.ttl:
                return None
            return json.loads(payload)
        finally:
            conn.close()

    def _cache_put(self, key: str, payload: dict):
        now = int(time.time())
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                "REPLACE INTO aqi_cache (key, fetched_at, payload) VALUES (?, ?, ?)",
                (key, now, json.dumps(payload)),
            )
            conn.commit()
        finally:
            conn.close()

    def get_current_aqi(
        self, lat: float, lon: float, timezone: str = "America/Chicago"
    ) -> Optional[AirQualityData]:
        """
        Fetch current air quality for given coordinates.
        Returns AirQualityData or None on error.
        """
        key = f"aqi:{lat:.4f},{lon:.4f}"
        cached = self._cache_get(key)
        if cached:
            return AirQualityData(**cached)

        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "us_aqi,pm2_5,pm10,ozone,carbon_monoxide",
                "timezone": timezone,
            }
            resp = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            current = data.get("current", {})
            aqi = int(current.get("us_aqi", 0))
            category, color = get_aqi_category(aqi)

            result = AirQualityData(
                aqi=aqi,
                pm2_5=float(current.get("pm2_5", 0)),
                pm10=float(current.get("pm10", 0)),
                ozone=float(current.get("ozone", 0)),
                carbon_monoxide=float(current.get("carbon_monoxide", 0)),
                category=category,
                color=color,
                timestamp=current.get("time", ""),
                latitude=data.get("latitude", lat),
                longitude=data.get("longitude", lon),
            )

            self._cache_put(key, result.to_dict())
            return result

        except Exception as e:
            print(f"[AQI] Error fetching air quality for ({lat}, {lon}): {e}")
            return None


# --------------- CLI for testing --------------- #

def main():
    import argparse

    ap = argparse.ArgumentParser(description="Fetch current air quality from Open-Meteo")
    ap.add_argument("--lat", type=float, required=True, help="Latitude")
    ap.add_argument("--lon", type=float, required=True, help="Longitude")
    ap.add_argument("--tz", type=str, default="America/Chicago", help="Timezone")
    args = ap.parse_args()

    client = AirQualityClient()
    result = client.get_current_aqi(args.lat, args.lon, timezone=args.tz)

    if result:
        print(f"Air Quality for ({result.latitude}, {result.longitude})")
        print(f"  AQI: {result.aqi} ({result.category})")
        print(f"  PM2.5: {result.pm2_5} μg/m³")
        print(f"  PM10: {result.pm10} μg/m³")
        print(f"  Ozone: {result.ozone} μg/m³")
        print(f"  CO: {result.carbon_monoxide} μg/m³")
        print(f"  Color: {result.color}")
        print(f"  Time: {result.timestamp}")
    else:
        print("Failed to fetch air quality data")


if __name__ == "__main__":
    main()

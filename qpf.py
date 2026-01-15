#!/usr/bin/env python3
"""
qpf.py — Fetch NWS gridpoint Quantitative Precipitation Forecast (QPF) and
summarize by local calendar day for the next 3 days.

- Uses api.weather.gov:
  1) /points/{lat},{lon}  -> gridId, gridX, gridY, timezone
  2) /gridpoints/{gridId}/{gridX},{gridY} -> properties.quantitativePrecipitation

- Handles ISO 8601 "validTime" intervals like: "2025-10-28T12:00:00+00:00/PT6H"
- Sums mm (kg/m^2) into daily totals; converts to inches.
- Simple SQLite cache to stay polite with the API (configurable TTL).
"""

from __future__ import annotations
import argparse
import json
import math
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple, Optional

import requests
from dateutil import parser as dtparse
from dateutil.tz import gettz

DEFAULT_TZ = "America/Chicago"
INCH_PER_MM = 1.0 / 25.4

class QPFClient:
    def __init__(
        self,
        user_agent: str,
        contact_email: str,
        cache_path: str = os.environ.get("QPF_CACHE", "qpf_cache.sqlite"),
        ttl_hours: int = int(os.environ.get("QPF_TTL_HOURS", "3")),
        timeout: int = 20,
    ):
        """
        NWS requires a valid, descriptive User-Agent with contact info.
        Example UA: "mdchansl-usgs-alert/1.0 (https://github.com/..., email@example.com)"
        """
        assert user_agent and contact_email, "NWS User-Agent and contact email are required"
        self.ttl = ttl_hours * 3600
        self.timeout = timeout
        self.cache_path = cache_path
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"{user_agent} ({contact_email})",
            "Accept": "application/geo+json, application/json"
        })
        self._init_cache()

    def _init_cache(self) -> None:
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS qpf_cache (
                    key TEXT PRIMARY KEY,
                    fetched_at INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        now = int(time.time())
        conn = sqlite3.connect(self.cache_path)
        try:
            cur = conn.execute("SELECT fetched_at, payload FROM qpf_cache WHERE key = ?", (key,))
            row = cur.fetchone()
            if not row:
                return None
            fetched_at, payload = row
            if now - fetched_at > self.ttl:
                return None
            return json.loads(payload)
        finally:
            conn.close()

    def _cache_put(self, key: str, payload: Dict[str, Any]) -> None:
        now = int(time.time())
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                "REPLACE INTO qpf_cache (key, fetched_at, payload) VALUES (?, ?, ?)",
                (key, now, json.dumps(payload))
            )
            conn.commit()
        finally:
            conn.close()

    # ---------------- Core public API ---------------- #

    def get_qpf_by_day(
        self, lat: float, lon: float, days: int = 3, local_tz: str = DEFAULT_TZ
    ) -> Dict[str, float]:
        """
        Returns a dict: { 'YYYY-MM-DD': inches, ... } up to `days` days.
        """
        key = f"qpf:{lat:.4f},{lon:.4f}:{days}:{local_tz}"
        cached = self._cache_get(key)
        if cached:
            return cached

        meta = self._get_points_meta(lat, lon)
        grid_id, grid_x, grid_y = meta["properties"]["gridId"], meta["properties"]["gridX"], meta["properties"]["gridY"]
        tzname = meta["properties"].get("timeZone") or local_tz

        gp = self._get_gridpoint(grid_id, grid_x, grid_y)
        qpf = gp["properties"].get("quantitativePrecipitation", {})
        values: List[dict] = qpf.get("values") or []

        # Sum per local day
        totals_mm: Dict[str, float] = {}
        tzinfo = gettz(tzname) or gettz(local_tz)

        # Build day buckets starting at local midnight
        now_local = datetime.now(tzinfo)
        start_of_today = datetime(now_local.year, now_local.month, now_local.day, tzinfo=tzinfo)
        day_edges = [start_of_today + timedelta(days=i) for i in range(days + 1)]

        # Iterate QPF time bins and apportion into day buckets
        for item in values:
            vt = item.get("validTime")  # e.g., "2025-10-28T12:00:00+00:00/PT6H"
            mm = item.get("value")
            if mm is None or vt is None:
                continue
            # Some values can be null; treat None as 0
            try:
                mm = float(mm)
            except (TypeError, ValueError):
                continue

            start_utc, dur = _parse_valid_time(vt)  # start as aware UTC dt, duration as timedelta
            end_utc = start_utc + dur

            # Convert to local
            start_local = start_utc.astimezone(tzinfo)
            end_local = end_utc.astimezone(tzinfo)

            # Skip bins that end before today or start after our window
            if end_local <= day_edges[0] or start_local >= day_edges[-1]:
                continue

            # Apportion mm by overlap into each day bucket it crosses
            bin_seconds = (end_local - start_local).total_seconds()
            if bin_seconds <= 0:
                continue

            for i in range(days):
                seg_start = max(start_local, day_edges[i])
                seg_end = min(end_local, day_edges[i+1])
                overlap = (seg_end - seg_start).total_seconds()
                if overlap > 0:
                    frac = overlap / bin_seconds
                    date_key = day_edges[i].date().isoformat()
                    totals_mm[date_key] = totals_mm.get(date_key, 0.0) + mm * frac

        # Convert to inches and round to 2 decimals for reporting
        totals_in = {d: round(mm * INCH_PER_MM, 2) for d, mm in totals_mm.items()}

        self._cache_put(key, totals_in)
        return totals_in

    # --------------- NWS helpers --------------- #

    def _get_points_meta(self, lat: float, lon: float) -> Dict[str, Any]:
        url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
        r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _get_gridpoint(self, grid_id: str, grid_x: int, grid_y: int) -> Dict[str, Any]:
        url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}"
        r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

# -------- utilities -------- #

def _parse_valid_time(valid_time: str) -> Tuple[datetime, timedelta]:
    """
    Parse NWS validTime like "2025-10-28T12:00:00+00:00/PT6H".
    Returns (start_dt_utc, duration_timedelta).
    """
    if "/" in valid_time:
        start_str, dur_str = valid_time.split("/", 1)
    else:
        start_str, dur_str = valid_time, "PT1H"
    start_dt = dtparse.isoparse(start_str)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    # duration
    dur = _parse_iso_duration(dur_str)
    return start_dt.astimezone(timezone.utc), dur

def _parse_iso_duration(iso_dur: str) -> timedelta:
    # minimal ISO-8601 duration parser for formats like "PT6H", "PT1H30M", "PT3H", "PT30M"
    hours = minutes = seconds = 0
    if not iso_dur.startswith("P"):
        return timedelta(hours=1)
    # Strip "P"
    rest = iso_dur[1:]
    # We only expect time components following 'T'
    if "T" not in rest:
        return timedelta(0)
    _, tpart = rest.split("T", 1)
    num = ""
    for ch in tpart:
        if ch.isdigit() or ch == ".":
            num += ch
        else:
            if ch == "H":
                hours = float(num)
            elif ch == "M":
                minutes = float(num)
            elif ch == "S":
                seconds = float(num)
            num = ""
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

# -------- CLI for quick checks -------- #

def _format_totals(totals: Dict[str, float]) -> str:
    parts = []
    for d in sorted(totals.keys()):
        parts.append(f"{d}: {totals[d]:.2f}\"")
    return ", ".join(parts)

def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch QPF by day from NWS")
    ap.add_argument("--lat", type=float, required=True, help="Latitude")
    ap.add_argument("--lon", type=float, required=True, help="Longitude")
    ap.add_argument("--days", type=int, default=3, help="Number of days (default 3)")
    ap.add_argument("--ua", type=str, default=os.environ.get("NWS_UA", "usgs-alert/1.0"),
                    help="User-Agent (NWS requirement)")
    ap.add_argument("--email", type=str, default=os.environ.get("NWS_CONTACT", "you@example.com"),
                    help="Contact email (NWS requirement)")
    ap.add_argument("--tz", type=str, default=os.environ.get("QPF_TZ", DEFAULT_TZ),
                    help="Local timezone for day rollup (IANA)")
    args = ap.parse_args()

    client = QPFClient(user_agent=args.ua, contact_email=args.email)
    totals = client.get_qpf_by_day(args.lat, args.lon, days=args.days, local_tz=args.tz)
    print(_format_totals(totals))

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Rainfall History Storage

Stores daily precipitation data indefinitely for each river location.
Uses two data sources:
  1. PWS (Weather Underground) - Real-time updates throughout the day
  2. Open-Meteo Historical API - For backfilling and validation

This data is used to:
  - Correlate rainfall amounts with river level rises
  - Predict when rivers will reach min/max thresholds
  - Analyze response times (rain -> runnable level)

Database: /data/rainfall_history.sqlite
"""

import sqlite3
import os
import json
import urllib.request
from datetime import datetime, timedelta, date, timezone
from typing import Optional, List, Dict, Any

# Try to use zoneinfo for local timezone, fall back to UTC offset
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/Chicago")
except Exception:
    # Fallback: CST is UTC-6
    LOCAL_TZ = timezone(timedelta(hours=-6))

# Default database path (can be overridden via environment)
DEFAULT_DB_PATH = "/data/rainfall_history.sqlite"

# Open-Meteo Historical Weather API
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# PWS station mapping (primary station for each river)
PWS_STATIONS = {
    "Little River": "KALCEDAR14",
    "Little River Canyon": "KALCEDAR14",
    "Locust Fork": "KALBLOUN24",
    "Short Creek": "KALGUNTE26",
    "Town Creek": "KALFYFFE7",
    "South Sauty": "KALLANGS7",
    "Mulberry Fork": "KALHAYDE19",
    "Tellico River": None,  # No PWS available - use Open-Meteo only
    "Hiwassee Dries": "KTNBENTO3",
    "Ocoee #3 (Upper)": "KTNBENTO3",
    "Ocoee #2 (Middle)": "KTNBENTO3",
    "Ocoee #1 (Lower)": "KTNBENTO3",
    "Rush South": "KGACOLUM39",
}


def get_db_path() -> str:
    """Get the database path from environment or use default."""
    return os.environ.get("RAINFALL_HISTORY_DB", DEFAULT_DB_PATH)


def init_database(db_path: Optional[str] = None) -> None:
    """
    Initialize the rainfall history database with required tables and indexes.
    """
    if db_path is None:
        db_path = get_db_path()

    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create daily rainfall table
    # This stores the final daily total for each river/date combination
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_rainfall (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            river_name TEXT NOT NULL,
            date TEXT NOT NULL,
            precip_in REAL NOT NULL,
            source TEXT NOT NULL,
            station_id TEXT,
            lat REAL,
            lon REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(river_name, date, source)
        )
    """)

    # Create real-time observations table
    # This stores each PWS observation throughout the day for tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rainfall_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            river_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            precip_today_in REAL NOT NULL,
            precip_rate_in_hr REAL,
            station_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(river_name, timestamp)
        )
    """)

    # Create river level correlation table
    # Links rainfall events to river level peaks for analysis
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rainfall_river_correlation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            river_name TEXT NOT NULL,
            rain_date TEXT NOT NULL,
            rain_total_in REAL NOT NULL,
            peak_date TEXT,
            peak_cfs REAL,
            peak_ft REAL,
            response_hours REAL,
            reached_min INTEGER DEFAULT 0,
            reached_good INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(river_name, rain_date)
        )
    """)

    # Create indexes for efficient queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_river_date
        ON daily_rainfall(river_name, date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_obs_river_time
        ON rainfall_observations(river_name, timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_corr_river_date
        ON rainfall_river_correlation(river_name, rain_date)
    """)

    conn.commit()
    conn.close()

    print(f"[Rainfall History] Database initialized: {db_path}")


def save_daily_rainfall(
    river_name: str,
    date_str: str,
    precip_in: float,
    source: str = "pws",
    station_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Save or update daily rainfall total for a river.

    Uses INSERT OR REPLACE to update if the date/source combination exists.

    Args:
        river_name: Name of the river (must match config)
        date_str: Date in YYYY-MM-DD format
        precip_in: Precipitation total in inches
        source: Data source ('pws' or 'open-meteo')
        station_id: PWS station ID if from PWS
        lat: Latitude of measurement location
        lon: Longitude of measurement location
        db_path: Optional path to database file

    Returns:
        True if saved successfully
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO daily_rainfall
            (river_name, date, precip_in, source, station_id, lat, lon, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(river_name, date, source) DO UPDATE SET
                precip_in = excluded.precip_in,
                updated_at = CURRENT_TIMESTAMP
        """, (river_name, date_str, precip_in, source, station_id, lat, lon))

        conn.commit()
        return True

    except Exception as e:
        print(f"[Rainfall History] Error saving daily rainfall: {e}")
        return False

    finally:
        conn.close()


def save_rainfall_observation(
    river_name: str,
    timestamp: str,
    precip_today_in: float,
    precip_rate_in_hr: Optional[float] = None,
    station_id: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Save a real-time rainfall observation from PWS.

    Args:
        river_name: Name of the river
        timestamp: ISO format timestamp
        precip_today_in: Total precipitation today so far
        precip_rate_in_hr: Current precipitation rate (in/hr)
        station_id: PWS station ID
        db_path: Optional path to database file

    Returns:
        True if saved (new observation), False if duplicate or error
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO rainfall_observations
            (river_name, timestamp, precip_today_in, precip_rate_in_hr, station_id)
            VALUES (?, ?, ?, ?, ?)
        """, (river_name, timestamp, precip_today_in, precip_rate_in_hr, station_id))

        conn.commit()
        return cursor.rowcount > 0

    except Exception as e:
        print(f"[Rainfall History] Error saving observation: {e}")
        return False

    finally:
        conn.close()


def get_daily_rainfall(
    river_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = None,
    source: Optional[str] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve daily rainfall history for a river.

    Args:
        river_name: Name of the river
        start_date: Start date (YYYY-MM-DD). Overridden by 'days'.
        end_date: End date (YYYY-MM-DD). Defaults to today.
        days: Number of days to retrieve (from today backwards)
        source: Filter by source ('pws' or 'open-meteo'). None for all.
        db_path: Optional path to database file

    Returns:
        List of daily rainfall records, ordered by date ascending
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        query = """
            SELECT date, precip_in, source, station_id, lat, lon, updated_at
            FROM daily_rainfall
            WHERE river_name = ?
        """
        params = [river_name]

        # Handle date range
        if days is not None:
            start_dt = datetime.now(LOCAL_TZ) - timedelta(days=days)
            start_date = start_dt.strftime("%Y-%m-%d")

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " ORDER BY date ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    except Exception as e:
        print(f"[Rainfall History] Error retrieving daily rainfall: {e}")
        return []

    finally:
        conn.close()


def get_rainfall_stats(
    river_name: str,
    days: int = 30,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get rainfall statistics for a river over a time period.

    Args:
        river_name: Name of the river
        days: Number of days to analyze
        db_path: Optional path to database file

    Returns:
        Dict with statistics including total, average, max, rainy days count
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        start_dt = datetime.now(LOCAL_TZ) - timedelta(days=days)
        start_date = start_dt.strftime("%Y-%m-%d")

        cursor.execute("""
            SELECT
                COUNT(*) as days_with_data,
                SUM(precip_in) as total_precip,
                AVG(precip_in) as avg_daily,
                MAX(precip_in) as max_daily,
                SUM(CASE WHEN precip_in > 0.01 THEN 1 ELSE 0 END) as rainy_days,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM daily_rainfall
            WHERE river_name = ? AND date >= ?
        """, (river_name, start_date))

        row = cursor.fetchone()

        return {
            'river_name': river_name,
            'days_requested': days,
            'days_with_data': row[0] or 0,
            'total_precip_in': round(row[1], 2) if row[1] else 0,
            'avg_daily_in': round(row[2], 3) if row[2] else 0,
            'max_daily_in': round(row[3], 2) if row[3] else 0,
            'rainy_days': row[4] or 0,
            'date_range': {
                'start': row[5],
                'end': row[6]
            }
        }

    except Exception as e:
        print(f"[Rainfall History] Error getting stats: {e}")
        return {}

    finally:
        conn.close()


def fetch_open_meteo_history(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str
) -> List[Dict[str, Any]]:
    """
    Fetch historical daily precipitation from Open-Meteo API.

    Args:
        lat: Latitude
        lon: Longitude
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        List of dicts with 'date' and 'precip_in' keys
    """
    url = (
        f"{OPEN_METEO_ARCHIVE_URL}"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=precipitation_sum"
        f"&timezone=America/Chicago"
        f"&precipitation_unit=inch"
    )

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "usgs-river-alert/1.0"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        precips = daily.get("precipitation_sum", [])

        results = []
        for d, p in zip(dates, precips):
            results.append({
                'date': d,
                'precip_in': round(p, 3) if p is not None else 0
            })

        return results

    except Exception as e:
        print(f"[Rainfall History] Open-Meteo fetch error: {e}")
        return []


def backfill_historical_data(
    river_name: str,
    lat: float,
    lon: float,
    days: int = 365,
    db_path: Optional[str] = None
) -> int:
    """
    Backfill historical rainfall data from Open-Meteo for a river.

    Args:
        river_name: Name of the river
        lat: Latitude of the river/gauge location
        lon: Longitude of the river/gauge location
        days: Number of days of history to fetch (default 365)
        db_path: Optional path to database file

    Returns:
        Number of days successfully saved
    """
    if db_path is None:
        db_path = get_db_path()

    end_dt = datetime.now(LOCAL_TZ) - timedelta(days=1)  # Yesterday
    start_dt = end_dt - timedelta(days=days)

    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    print(f"[Rainfall History] Backfilling {river_name} from {start_date} to {end_date}...")

    history = fetch_open_meteo_history(lat, lon, start_date, end_date)

    if not history:
        print(f"[Rainfall History] No data returned from Open-Meteo")
        return 0

    saved_count = 0
    for record in history:
        if save_daily_rainfall(
            river_name=river_name,
            date_str=record['date'],
            precip_in=record['precip_in'],
            source="open-meteo",
            lat=lat,
            lon=lon,
            db_path=db_path
        ):
            saved_count += 1

    print(f"[Rainfall History] Saved {saved_count} days for {river_name}")
    return saved_count


def record_pws_rainfall(
    river_name: str,
    pws_observation: Dict[str, Any],
    db_path: Optional[str] = None
) -> bool:
    """
    Record rainfall from a PWS observation.

    Call this during each monitoring loop iteration.
    Updates both the real-time observations table and the daily total.

    Args:
        river_name: Name of the river
        pws_observation: Dict from pws_observations.fetch_pws_observation()
        db_path: Optional path to database file

    Returns:
        True if recorded successfully
    """
    if db_path is None:
        db_path = get_db_path()

    if not pws_observation:
        return False

    precip_today = pws_observation.get('precip_today_in')
    if precip_today is None:
        return False

    # Get current local date
    now = datetime.now(LOCAL_TZ)
    date_str = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

    station_id = pws_observation.get('station_id')
    precip_rate = pws_observation.get('precip_rate_in_hr')

    # Save observation
    save_rainfall_observation(
        river_name=river_name,
        timestamp=timestamp,
        precip_today_in=precip_today,
        precip_rate_in_hr=precip_rate,
        station_id=station_id,
        db_path=db_path
    )

    # Update daily total (PWS resets at midnight, so this is cumulative for the day)
    save_daily_rainfall(
        river_name=river_name,
        date_str=date_str,
        precip_in=precip_today,
        source="pws",
        station_id=station_id,
        db_path=db_path
    )

    return True


def get_all_rivers_today(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get today's rainfall totals for all rivers.

    Returns:
        List of dicts with river_name, precip_in, source, updated_at
    """
    if db_path is None:
        db_path = get_db_path()

    today = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT river_name, precip_in, source, station_id, updated_at
            FROM daily_rainfall
            WHERE date = ?
            ORDER BY river_name
        """, (today,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    except Exception as e:
        print(f"[Rainfall History] Error getting today's rainfall: {e}")
        return []

    finally:
        conn.close()


def get_weekly_summary(
    river_name: str,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get weekly rainfall summary for a river (last 7 days).

    Returns:
        Dict with daily breakdown and totals
    """
    if db_path is None:
        db_path = get_db_path()

    days_data = get_daily_rainfall(river_name, days=7, db_path=db_path)

    # Fill in missing days with 0
    today = datetime.now(LOCAL_TZ).date()
    week_data = []

    for i in range(6, -1, -1):  # 6 days ago to today
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")

        # Find this date in the data
        precip = 0
        for rec in days_data:
            if rec['date'] == date_str:
                precip = rec['precip_in']
                break

        week_data.append({
            'date': date_str,
            'day': d.strftime("%a"),
            'precip_in': precip
        })

    total = sum(d['precip_in'] for d in week_data)

    return {
        'river_name': river_name,
        'days': week_data,
        'total_in': round(total, 2),
        'avg_daily_in': round(total / 7, 3)
    }


# CLI for testing and backfill
if __name__ == "__main__":
    import sys

    # Use local test database for development
    test_db = "./test_rainfall_history.sqlite"

    print("Rainfall History Database Test")
    print("=" * 60)

    # Initialize
    init_database(test_db)

    # Test backfill for Little River Canyon
    lat = 34.1736
    lon = -85.6164
    saved = backfill_historical_data(
        river_name="Little River Canyon",
        lat=lat,
        lon=lon,
        days=30,
        db_path=test_db
    )
    print(f"\nBackfilled {saved} days")

    # Get stats
    stats = get_rainfall_stats("Little River Canyon", days=30, db_path=test_db)
    print(f"\n30-day Stats:")
    print(f"  Total: {stats['total_precip_in']}\"")
    print(f"  Avg Daily: {stats['avg_daily_in']}\"")
    print(f"  Max Daily: {stats['max_daily_in']}\"")
    print(f"  Rainy Days: {stats['rainy_days']}")

    # Get weekly summary
    weekly = get_weekly_summary("Little River Canyon", db_path=test_db)
    print(f"\nWeekly Summary:")
    for day in weekly['days']:
        bar = '#' * int(day['precip_in'] * 20)  # Simple bar chart
        print(f"  {day['day']} {day['date']}: {day['precip_in']:>5.2f}\" {bar}")
    print(f"  Total: {weekly['total_in']}\"")

    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"\nTest database removed: {test_db}")

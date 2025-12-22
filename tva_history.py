#!/usr/bin/env python3
"""
TVA Historical Data Storage

Stores TVA dam observations indefinitely for historical charting.
Uses SQLite for persistent storage with automatic deduplication.

Database: /data/tva_history.sqlite
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Default database path (can be overridden via environment)
DEFAULT_DB_PATH = "/data/tva_history.sqlite"


def get_db_path() -> str:
    """Get the database path from environment or use default."""
    return os.environ.get("TVA_HISTORY_DB", DEFAULT_DB_PATH)


def init_database(db_path: Optional[str] = None) -> None:
    """
    Initialize the TVA history database with required tables and indexes.

    Args:
        db_path: Optional path to database file. Uses default if not provided.
    """
    if db_path is None:
        db_path = get_db_path()

    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create observations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_code TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            discharge_cfs INTEGER,
            pool_elevation_ft REAL,
            tailwater_ft REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(site_code, timestamp)
        )
    """)

    # Create index for efficient queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_time
        ON observations(site_code, timestamp)
    """)

    # Create index for time-range queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON observations(timestamp)
    """)

    conn.commit()
    conn.close()

    print(f"[TVA History] Database initialized: {db_path}")


def save_observation(
    site_code: str,
    timestamp: str,
    discharge_cfs: int,
    pool_elevation_ft: float,
    tailwater_ft: float,
    db_path: Optional[str] = None
) -> bool:
    """
    Save a single TVA observation to the database.

    Uses INSERT OR IGNORE to prevent duplicates (based on site_code + timestamp).

    Args:
        site_code: TVA site code (e.g., 'HADT1')
        timestamp: ISO format timestamp (e.g., '2025-12-18T14:00:00')
        discharge_cfs: Discharge in CFS
        pool_elevation_ft: Pool elevation in feet MSL
        tailwater_ft: Tailwater elevation in feet MSL
        db_path: Optional path to database file

    Returns:
        True if observation was saved (new), False if it already existed
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO observations
            (site_code, timestamp, discharge_cfs, pool_elevation_ft, tailwater_ft)
            VALUES (?, ?, ?, ?, ?)
        """, (site_code, timestamp, discharge_cfs, pool_elevation_ft, tailwater_ft))

        conn.commit()
        inserted = cursor.rowcount > 0
        return inserted

    except Exception as e:
        print(f"[TVA History] Error saving observation: {e}")
        return False

    finally:
        conn.close()


def save_observations_batch(
    site_code: str,
    observations: List[Dict[str, Any]],
    db_path: Optional[str] = None
) -> int:
    """
    Save multiple observations in a single transaction.

    Args:
        site_code: TVA site code (e.g., 'HADT1')
        observations: List of dicts with keys:
            - timestamp: ISO format
            - discharge_cfs: int
            - pool_elevation_ft: float
            - tailwater_ft: float
        db_path: Optional path to database file

    Returns:
        Number of new observations saved
    """
    if db_path is None:
        db_path = get_db_path()

    if not observations:
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    saved_count = 0

    try:
        for obs in observations:
            cursor.execute("""
                INSERT OR IGNORE INTO observations
                (site_code, timestamp, discharge_cfs, pool_elevation_ft, tailwater_ft)
                VALUES (?, ?, ?, ?, ?)
            """, (
                site_code,
                obs.get('timestamp'),
                obs.get('discharge_cfs'),
                obs.get('pool_elevation_ft'),
                obs.get('tailwater_ft')
            ))

            if cursor.rowcount > 0:
                saved_count += 1

        conn.commit()

        if saved_count > 0:
            print(f"[TVA History] Saved {saved_count} new observations for {site_code}")

        return saved_count

    except Exception as e:
        print(f"[TVA History] Error saving batch: {e}")
        conn.rollback()
        return 0

    finally:
        conn.close()


def get_observations(
    site_code: str,
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve historical observations for a site.

    Args:
        site_code: TVA site code (e.g., 'HADT1')
        days: Number of days of history (from now). Overrides start_date.
        start_date: ISO format start date (inclusive)
        end_date: ISO format end date (inclusive). Defaults to now.
        limit: Maximum number of records to return
        db_path: Optional path to database file

    Returns:
        List of observation dicts, ordered by timestamp ascending
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Build query
        query = """
            SELECT timestamp, discharge_cfs, pool_elevation_ft, tailwater_ft
            FROM observations
            WHERE site_code = ?
        """
        params = [site_code]

        # Handle date range
        if days is not None:
            start_dt = datetime.now() - timedelta(days=days)
            start_date = start_dt.strftime("%Y-%m-%dT%H:%M:%S")

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp ASC"

        if limit:
            query += f" LIMIT {int(limit)}"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    except Exception as e:
        print(f"[TVA History] Error retrieving observations: {e}")
        return []

    finally:
        conn.close()


def get_observation_count(site_code: str, db_path: Optional[str] = None) -> int:
    """
    Get the total number of observations stored for a site.

    Args:
        site_code: TVA site code
        db_path: Optional path to database file

    Returns:
        Total observation count
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT COUNT(*) FROM observations WHERE site_code = ?",
            (site_code,)
        )
        return cursor.fetchone()[0]

    except Exception:
        return 0

    finally:
        conn.close()


def get_date_range(site_code: str, db_path: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Get the date range of stored observations.

    Args:
        site_code: TVA site code
        db_path: Optional path to database file

    Returns:
        Dict with 'earliest' and 'latest' timestamps (or None if no data)
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM observations
            WHERE site_code = ?
        """, (site_code,))

        row = cursor.fetchone()
        return {
            'earliest': row[0],
            'latest': row[1]
        }

    except Exception:
        return {'earliest': None, 'latest': None}

    finally:
        conn.close()


def get_stats(site_code: str, days: int = 30, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get statistics for a site over a time period.

    Args:
        site_code: TVA site code
        days: Number of days to analyze
        db_path: Optional path to database file

    Returns:
        Dict with min, max, avg for each metric
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        start_dt = datetime.now() - timedelta(days=days)
        start_date = start_dt.strftime("%Y-%m-%dT%H:%M:%S")

        cursor.execute("""
            SELECT
                MIN(discharge_cfs) as min_cfs,
                MAX(discharge_cfs) as max_cfs,
                AVG(discharge_cfs) as avg_cfs,
                MIN(pool_elevation_ft) as min_pool,
                MAX(pool_elevation_ft) as max_pool,
                AVG(pool_elevation_ft) as avg_pool,
                MIN(tailwater_ft) as min_tailwater,
                MAX(tailwater_ft) as max_tailwater,
                AVG(tailwater_ft) as avg_tailwater,
                COUNT(*) as observation_count
            FROM observations
            WHERE site_code = ? AND timestamp >= ?
        """, (site_code, start_date))

        row = cursor.fetchone()

        return {
            'discharge_cfs': {
                'min': row[0],
                'max': row[1],
                'avg': round(row[2], 1) if row[2] else None
            },
            'pool_elevation_ft': {
                'min': row[3],
                'max': row[4],
                'avg': round(row[5], 2) if row[5] else None
            },
            'tailwater_ft': {
                'min': row[6],
                'max': row[7],
                'avg': round(row[8], 2) if row[8] else None
            },
            'observation_count': row[9],
            'days': days
        }

    except Exception as e:
        print(f"[TVA History] Error getting stats: {e}")
        return {}

    finally:
        conn.close()


# CLI for testing
if __name__ == "__main__":
    import sys

    # Use local test database
    test_db = "./test_tva_history.sqlite"

    print("TVA History Database Test")
    print("=" * 50)

    # Initialize
    init_database(test_db)

    # Test saving observations
    test_observations = [
        {
            'timestamp': '2025-12-18T14:00:00',
            'discharge_cfs': 2850,
            'pool_elevation_ft': 1277.5,
            'tailwater_ft': 840.5
        },
        {
            'timestamp': '2025-12-18T15:00:00',
            'discharge_cfs': 2900,
            'pool_elevation_ft': 1277.4,
            'tailwater_ft': 840.6
        },
        {
            'timestamp': '2025-12-18T16:00:00',
            'discharge_cfs': 1500,
            'pool_elevation_ft': 1277.6,
            'tailwater_ft': 839.5
        }
    ]

    saved = save_observations_batch('HADT1', test_observations, test_db)
    print(f"Saved {saved} observations")

    # Test retrieval
    obs = get_observations('HADT1', days=7, db_path=test_db)
    print(f"\nRetrieved {len(obs)} observations:")
    for o in obs:
        print(f"  {o['timestamp']}: {o['discharge_cfs']} CFS, Pool: {o['pool_elevation_ft']} ft")

    # Test stats
    stats = get_stats('HADT1', days=30, db_path=test_db)
    print(f"\n30-day Stats:")
    print(f"  CFS: min={stats['discharge_cfs']['min']}, max={stats['discharge_cfs']['max']}, avg={stats['discharge_cfs']['avg']}")

    # Test date range
    date_range = get_date_range('HADT1', test_db)
    print(f"\nDate Range: {date_range['earliest']} to {date_range['latest']}")

    # Cleanup
    os.remove(test_db)
    print(f"\nTest database removed: {test_db}")

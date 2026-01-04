#!/usr/bin/env python3
"""
Paddle Event Log - Track successful paddle runs with rainfall correlation data.

This module stores paddle events to help understand the relationship between
rainfall amounts and runnable river conditions for each river.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

DEFAULT_DB_PATH = "/data/paddle_log.sqlite"


def init_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the paddle events database table."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paddle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            river_name TEXT NOT NULL,
            paddle_date DATE NOT NULL,
            paddle_time TEXT,
            rain_24h REAL,
            rain_48h REAL,
            rain_72h REAL,
            rain_7d REAL,
            cfs_at_paddle REAL,
            feet_at_paddle REAL,
            peak_cfs REAL,
            peak_feet REAL,
            response_hours REAL,
            water_trend TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(river_name, paddle_date)
        )
    """)

    # Create index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_paddle_river_date
        ON paddle_events(river_name, paddle_date)
    """)

    conn.commit()
    conn.close()


def log_paddle_event(
    river_name: str,
    paddle_date: date,
    rain_24h: float = None,
    rain_48h: float = None,
    rain_72h: float = None,
    rain_7d: float = None,
    cfs_at_paddle: float = None,
    feet_at_paddle: float = None,
    peak_cfs: float = None,
    peak_feet: float = None,
    response_hours: float = None,
    water_trend: str = None,
    notes: str = None,
    paddle_time: str = None,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """
    Log a paddle event to the database.

    Args:
        river_name: Name of the river
        paddle_date: Date of the paddle (date object or 'YYYY-MM-DD' string)
        rain_24h: Rainfall in the 24 hours before paddle
        rain_48h: Rainfall in the 48 hours before paddle
        rain_72h: Rainfall in the 72 hours before paddle
        rain_7d: Rainfall in the 7 days before paddle
        cfs_at_paddle: CFS reading at time of paddle
        feet_at_paddle: Feet reading at time of paddle
        peak_cfs: Peak CFS observed during the event
        peak_feet: Peak feet observed during the event
        response_hours: Hours from rain to runnable conditions
        water_trend: 'rising', 'falling', or 'steady'
        notes: Free-form notes about the paddle
        paddle_time: Time of paddle (HH:MM format)
        db_path: Path to SQLite database

    Returns:
        ID of the inserted row
    """
    init_database(db_path)

    # Convert date string to date object if needed
    if isinstance(paddle_date, str):
        paddle_date = datetime.strptime(paddle_date, "%Y-%m-%d").date()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO paddle_events (
                river_name, paddle_date, paddle_time,
                rain_24h, rain_48h, rain_72h, rain_7d,
                cfs_at_paddle, feet_at_paddle,
                peak_cfs, peak_feet,
                response_hours, water_trend, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            river_name, paddle_date.isoformat(), paddle_time,
            rain_24h, rain_48h, rain_72h, rain_7d,
            cfs_at_paddle, feet_at_paddle,
            peak_cfs, peak_feet,
            response_hours, water_trend, notes
        ))

        row_id = cursor.lastrowid
        conn.commit()
        return row_id

    except sqlite3.IntegrityError:
        # Entry already exists for this river/date, update it instead
        cursor.execute("""
            UPDATE paddle_events SET
                paddle_time = COALESCE(?, paddle_time),
                rain_24h = COALESCE(?, rain_24h),
                rain_48h = COALESCE(?, rain_48h),
                rain_72h = COALESCE(?, rain_72h),
                rain_7d = COALESCE(?, rain_7d),
                cfs_at_paddle = COALESCE(?, cfs_at_paddle),
                feet_at_paddle = COALESCE(?, feet_at_paddle),
                peak_cfs = COALESCE(?, peak_cfs),
                peak_feet = COALESCE(?, peak_feet),
                response_hours = COALESCE(?, response_hours),
                water_trend = COALESCE(?, water_trend),
                notes = COALESCE(?, notes)
            WHERE river_name = ? AND paddle_date = ?
        """, (
            paddle_time,
            rain_24h, rain_48h, rain_72h, rain_7d,
            cfs_at_paddle, feet_at_paddle,
            peak_cfs, peak_feet,
            response_hours, water_trend, notes,
            river_name, paddle_date.isoformat()
        ))

        cursor.execute(
            "SELECT id FROM paddle_events WHERE river_name = ? AND paddle_date = ?",
            (river_name, paddle_date.isoformat())
        )
        row_id = cursor.fetchone()[0]
        conn.commit()
        return row_id

    finally:
        conn.close()


def get_paddle_events(
    river_name: str = None,
    limit: int = 50,
    db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """
    Get paddle events, optionally filtered by river.

    Args:
        river_name: Filter by river name (None for all rivers)
        limit: Maximum number of events to return
        db_path: Path to SQLite database

    Returns:
        List of paddle event dictionaries
    """
    init_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if river_name:
        cursor.execute("""
            SELECT * FROM paddle_events
            WHERE river_name = ?
            ORDER BY paddle_date DESC
            LIMIT ?
        """, (river_name, limit))
    else:
        cursor.execute("""
            SELECT * FROM paddle_events
            ORDER BY paddle_date DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_river_stats(river_name: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Get statistics for a river based on logged paddle events.

    Returns insights like average rain needed, typical response time, etc.
    """
    init_database(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total_paddles,
            AVG(rain_48h) as avg_rain_48h,
            MIN(rain_48h) as min_rain_48h,
            MAX(rain_48h) as max_rain_48h,
            AVG(cfs_at_paddle) as avg_cfs,
            MIN(cfs_at_paddle) as min_cfs,
            MAX(cfs_at_paddle) as max_cfs,
            AVG(feet_at_paddle) as avg_feet,
            AVG(response_hours) as avg_response_hours,
            MIN(paddle_date) as first_paddle,
            MAX(paddle_date) as last_paddle
        FROM paddle_events
        WHERE river_name = ?
    """, (river_name,))

    row = cursor.fetchone()
    conn.close()

    if not row or row[0] == 0:
        return {"river_name": river_name, "total_paddles": 0}

    return {
        "river_name": river_name,
        "total_paddles": row[0],
        "avg_rain_48h": round(row[1], 2) if row[1] else None,
        "min_rain_48h": round(row[2], 2) if row[2] else None,
        "max_rain_48h": round(row[3], 2) if row[3] else None,
        "avg_cfs": round(row[4], 0) if row[4] else None,
        "min_cfs": round(row[5], 0) if row[5] else None,
        "max_cfs": round(row[6], 0) if row[6] else None,
        "avg_feet": round(row[7], 2) if row[7] else None,
        "avg_response_hours": round(row[8], 1) if row[8] else None,
        "first_paddle": row[9],
        "last_paddle": row[10]
    }


def get_all_river_stats(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Get statistics for all rivers with logged paddle events."""
    init_database(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT river_name FROM paddle_events ORDER BY river_name")
    rivers = [row[0] for row in cursor.fetchall()]
    conn.close()

    return [get_river_stats(river, db_path) for river in rivers]


if __name__ == "__main__":
    # Test the module
    import argparse

    parser = argparse.ArgumentParser(description="Paddle Event Log")
    parser.add_argument("--db", default="usgs-data/paddle_log.sqlite", help="Database path")
    parser.add_argument("--list", action="store_true", help="List all events")
    parser.add_argument("--river", help="Filter by river name")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--log", action="store_true", help="Log a new event")
    parser.add_argument("--date", help="Paddle date (YYYY-MM-DD)")
    parser.add_argument("--cfs", type=float, help="CFS at paddle")
    parser.add_argument("--feet", type=float, help="Feet at paddle")
    parser.add_argument("--rain48", type=float, help="Rain in last 48h")
    parser.add_argument("--notes", help="Notes about the paddle")

    args = parser.parse_args()

    if args.log and args.river and args.date:
        row_id = log_paddle_event(
            river_name=args.river,
            paddle_date=args.date,
            cfs_at_paddle=args.cfs,
            feet_at_paddle=args.feet,
            rain_48h=args.rain48,
            notes=args.notes,
            db_path=args.db
        )
        print(f"Logged paddle event #{row_id}")

    elif args.stats:
        if args.river:
            stats = get_river_stats(args.river, args.db)
            print(f"\n=== {args.river} Statistics ===")
            for k, v in stats.items():
                print(f"  {k}: {v}")
        else:
            all_stats = get_all_river_stats(args.db)
            for stats in all_stats:
                print(f"\n=== {stats['river_name']} ===")
                for k, v in stats.items():
                    if k != 'river_name':
                        print(f"  {k}: {v}")

    elif args.list:
        events = get_paddle_events(args.river, db_path=args.db)
        print(f"\n=== Paddle Events ({len(events)} total) ===")
        for e in events:
            print(f"\n{e['paddle_date']} - {e['river_name']}")
            print(f"  CFS: {e['cfs_at_paddle']}, Feet: {e['feet_at_paddle']}")
            print(f"  Rain 48h: {e['rain_48h']}\"")
            if e['notes']:
                print(f"  Notes: {e['notes']}")

    else:
        parser.print_help()

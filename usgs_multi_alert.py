#!/usr/bin/env python3
"""
USGS multi-site gauge alert with per-site min_ft & min_cfs (both must pass for IN),
SQLite state, IN/OUT emails, and gauges.json/.html publishing.

Usage examples:
  python usgs_multi_alert.py --config gauges.conf.json --cfs
  python usgs_multi_alert.py --config gauges.conf.json --cfs \
    --dump-json public/gauges.json --dump-html public/index.html --trend-hours 8
"""
import sys
import os
# Ensure /app is in the path for module imports
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

import argparse, json, time, smtplib, ssl, sqlite3, re
from datetime import datetime
from email.mime.text import MIMEText
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import urllib.parse as up
from html import escape as h

# Import QPF client for rainfall forecasts
try:
    from qpf import QPFClient
    QPF_AVAILABLE = True
except ImportError:
    QPF_AVAILABLE = False

# Import weather observations
try:
    from observations import fetch_latest_observation, fmt_dir
    OBS_AVAILABLE = True
except ImportError:
    OBS_AVAILABLE = False

# Import site detail page generator
try:
    from site_detail import fetch_usgs_7day_data, generate_site_detail_html, calculate_wind_chill
    SITE_DETAIL_AVAILABLE = True
except ImportError:
    SITE_DETAIL_AVAILABLE = False
    def calculate_wind_chill(temp_f, wind_mph):
        """Fallback if site_detail not available"""
        return None, None, None

# Import StreamBeam scraper for non-USGS gauges
try:
    from streambeam_multi_scrape import scrape_one as streambeam_scrape_one
    STREAMBEAM_AVAILABLE = True
except ImportError:
    STREAMBEAM_AVAILABLE = False

# Weather station mapping for each river site
# For sites that need multiple stations for operational decisions, use primary station here
WEATHER_STATIONS = {
    "Locust Fork": "KCMD",           # Cullman Regional Airport
    "Town Creek": "KBFZ",            # Albertville Regional Airport (ultra-local, near shore)
    "South Sauty": "K4A9",           # Fort Payne / Isbell Field Airport
    "Tellico River": "KMNV",         # Monroe County Airport, Madisonville TN
    "Little River": "K4A9",          # Fort Payne / Isbell Field Airport
    "Little River Canyon": "K4A9",   # Fort Payne / Isbell Field Airport (cloud config name)
    "Short Creek": "KBFZ",           # Albertville Regional Airport (ultra-local for lake paddling)
}

# Secondary weather stations for sites that need valley trend data
WEATHER_STATIONS_SECONDARY = {
    "Short Creek": "KHSV",           # Huntsville (valley trend for operational paddling calls)
    "Town Creek": "KHSV",            # Huntsville (valley trend backup)
}

# Friendly city abbreviations for weather station codes (for display)
STATION_CITY_LABELS = {
    "KCMD": "CULMAN",      # Cullman Regional Airport
    "KBFZ": "ALBVL",       # Albertville Regional Airport
    "K4A9": "FTPAYN",      # Fort Payne / Isbell Field Airport
    "KMNV": "MADSNVL",     # Monroe County Airport, Madisonville TN
    "KHSV": "HNTSV",       # Huntsville International Airport
}

USGS_IV = "https://waterservices.usgs.gov/nwis/iv/"

# ---------------- Utilities ----------------
def ensure_parent_dir(path: str):
    d = os.path.dirname(path or "")
    if d:
        os.makedirs(d, exist_ok=True)

def _get(url):
    req = Request(url, headers={"User-Agent": "USGS-MultiAlert/3.1"})
    with urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

SITE_ID_RE = re.compile(r"(\d{8,})")
def normalize_site_id(site: str) -> str:
    """
    Accepts a site string and returns a digits-only USGS site id.
    If text is included (e.g., 'Foo (USGS 03572690)'), extract the last 8+ digits.
    """
    s = (site or "").strip()
    if s.isdigit():
        return s
    m = SITE_ID_RE.findall(s)
    if m:
        return m[-1]
    raise ValueError(f"Invalid USGS site value (no numeric id found): {site!r}")

# ---------------- SQLite state ----------------
def open_state_db(db_path: str):
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_state (
            site TEXT PRIMARY KEY,
            last_alert_epoch REAL,
            last_out_epoch REAL,
            last_stage_ft REAL,
            last_ts_iso TEXT,
            last_cfs REAL,
            last_in INTEGER,
            last_pct_change_epoch REAL,
            last_in_epoch REAL,
            last_temp_f REAL,
            last_wind_mph REAL,
            last_wind_dir TEXT,
            last_wind_gust_mph REAL
        );
    """)
    # Defensive migration if table existed without newer columns
    cols = {row[1] for row in conn.execute("PRAGMA table_info(site_state)")}
    migrations = [
        ("last_in", "INTEGER"),
        ("last_pct_change_epoch", "REAL"),
        ("last_in_epoch", "REAL"),
        ("last_temp_f", "REAL"),
        ("last_wind_mph", "REAL"),
        ("last_wind_dir", "TEXT"),
        ("last_wind_gust_mph", "REAL")
    ]
    for col_name, col_type in migrations:
        if col_name not in cols:
            try:
                conn.execute(f"ALTER TABLE site_state ADD COLUMN {col_name} {col_type};")
                conn.commit()
            except Exception:
                pass
    conn.commit()
    return conn

def read_site_state(conn, site: str):
    cur = conn.execute("""
        SELECT last_alert_epoch, last_out_epoch, last_stage_ft, last_ts_iso, last_cfs,
               COALESCE(last_in,0), COALESCE(last_pct_change_epoch,0), COALESCE(last_in_epoch,0),
               last_temp_f, last_wind_mph, last_wind_dir, last_wind_gust_mph
        FROM site_state WHERE site=?
    """, (site,))
    row = cur.fetchone()
    if not row:
        return {}
    return {
        "last_alert_epoch": row[0] if row[0] is not None else 0.0,
        "last_out_epoch":   row[1] if row[1] is not None else 0.0,
        "last_stage_ft":    row[2],
        "last_ts_iso":      row[3],
        "last_cfs":         row[4],
        "last_in":          bool(row[5]),
        "last_pct_change_epoch": row[6] if row[6] is not None else 0.0,
        "last_in_epoch":    row[7] if row[7] is not None else 0.0,
        "last_temp_f":      row[8],
        "last_wind_mph":    row[9],
        "last_wind_dir":    row[10],
        "last_wind_gust_mph": row[11]
    }

def write_site_state(conn, site: str, state: dict):
    conn.execute("""
        INSERT INTO site_state (site, last_alert_epoch, last_out_epoch, last_stage_ft, last_ts_iso, last_cfs, last_in, last_pct_change_epoch,
                                last_in_epoch, last_temp_f, last_wind_mph, last_wind_dir, last_wind_gust_mph)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site) DO UPDATE SET
            last_alert_epoch=excluded.last_alert_epoch,
            last_out_epoch=excluded.last_out_epoch,
            last_stage_ft=excluded.last_stage_ft,
            last_ts_iso=excluded.last_ts_iso,
            last_cfs=excluded.last_cfs,
            last_in=excluded.last_in,
            last_pct_change_epoch=excluded.last_pct_change_epoch,
            last_in_epoch=excluded.last_in_epoch,
            last_temp_f=excluded.last_temp_f,
            last_wind_mph=excluded.last_wind_mph,
            last_wind_dir=excluded.last_wind_dir,
            last_wind_gust_mph=excluded.last_wind_gust_mph
    """, (
        site,
        float(state.get("last_alert_epoch", 0.0)) if state.get("last_alert_epoch") is not None else None,
        float(state.get("last_out_epoch", 0.0)) if state.get("last_out_epoch") is not None else None,
        float(state.get("last_stage_ft")) if state.get("last_stage_ft") is not None else None,
        state.get("last_ts_iso"),
        float(state.get("last_cfs")) if state.get("last_cfs") is not None else None,
        1 if state.get("last_in") else 0,
        float(state.get("last_pct_change_epoch", 0.0)) if state.get("last_pct_change_epoch") is not None else None,
        float(state.get("last_in_epoch", 0.0)) if state.get("last_in_epoch") is not None else None,
        float(state.get("last_temp_f")) if state.get("last_temp_f") is not None else None,
        float(state.get("last_wind_mph")) if state.get("last_wind_mph") is not None else None,
        state.get("last_wind_dir"),
        float(state.get("last_wind_gust_mph")) if state.get("last_wind_gust_mph") is not None else None
    ))

def migrate_json_to_db(json_path: str, conn):
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for site, st in data.items():
                write_site_state(conn, site, st or {})
            conn.commit()
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return False

# ---------------- USGS helpers ----------------
def fetch_latest(site: str, include_discharge: bool):
    site_id = normalize_site_id(site)
    params = {
        "sites": site_id,
        "parameterCd": "00065,00060" if include_discharge else "00065",
        "format": "json"
    }
    url = f"{USGS_IV}?{up.urlencode(params)}"
    data = _get(url)
    latest = {"site": site_id, "url": url, "ts_iso": None, "stage_ft": None, "discharge_cfs": None}
    try:
        for ts in data["value"]["timeSeries"]:
            variable = ts["variable"]["variableCode"][0]["value"]
            points = ts["values"][0]["value"]
            if not points:
                continue
            last = points[-1]
            dt = last["dateTime"]
            if latest["ts_iso"] is None or dt > latest["ts_iso"]:
                latest["ts_iso"] = dt
            if variable == "00065":
                latest["stage_ft"] = float(last["value"]) if last["value"] not in (None, "") else None
            elif variable == "00060":
                latest["discharge_cfs"] = float(last["value"]) if last["value"] not in (None, "") else None
    except Exception as e:
        raise RuntimeError(f"Failed to parse USGS response for site {site_id}: {e}")
    return latest

def fetch_trend_label(site: str, hours: int):
    if hours <= 0:
        return None
    site_id = normalize_site_id(site)
    period = f"PT{int(hours)}H"
    url = f"{USGS_IV}?{up.urlencode({'sites': site_id, 'parameterCd': '00065', 'format': 'json', 'period': period})}"
    try:
        data = _get(url)
        series = None
        for ts in data["value"]["timeSeries"]:
            if ts["variable"]["variableCode"][0]["value"] == "00065":
                series = ts["values"][0]["value"]
                break
        if not series or len(series) < 2:
            return None
        first = float(series[0]["value"]) if series[0]["value"] not in ("", None) else None
        last  = float(series[-1]["value"]) if series[-1]["value"] not in ("", None) else None
        if first is None or last is None:
            return None
        delta = last - first
        eps = 0.02
        if delta > eps:  return "rising"
        if delta < -eps: return "falling"
        return "steady"
    except Exception:
        return None

def fetch_trend_data(site: str, hours: int):
    """Fetch historical data points for sparkline visualization"""
    if hours <= 0:
        return None
    site_id = normalize_site_id(site)
    period = f"PT{int(hours)}H"
    url = f"{USGS_IV}?{up.urlencode({'sites': site_id, 'parameterCd': '00065', 'format': 'json', 'period': period})}"
    try:
        data = _get(url)
        series = None
        for ts in data["value"]["timeSeries"]:
            if ts["variable"]["variableCode"][0]["value"] == "00065":
                series = ts["values"][0]["value"]
                break
        if not series or len(series) < 2:
            return None

        # Extract values, filtering out None/empty
        values = []
        for point in series:
            if point["value"] not in ("", None):
                values.append(float(point["value"]))

        if len(values) < 2:
            return None

        # Determine if rising or falling
        delta = values[-1] - values[0]
        eps = 0.02
        if delta > eps:
            direction = "rising"
        elif delta < -eps:
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
    except Exception:
        return None

# ---------------- StreamBeam helpers ----------------
# Cache for last known good StreamBeam readings (to detect wild swings)
_streambeam_last_good = {}
_streambeam_db_path = None  # Set by main() from config

def _init_streambeam_table(db_path: str):
    """Create the streambeam_last_good table if it doesn't exist."""
    global _streambeam_db_path
    _streambeam_db_path = db_path
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS streambeam_last_good (
                site_name TEXT PRIMARY KEY,
                last_good_ft REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()

def _load_streambeam_last_good(db_path: str):
    """Load last known good values from SQLite into memory cache."""
    global _streambeam_last_good
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT site_name, last_good_ft FROM streambeam_last_good").fetchall()
            for site_name, last_good_ft in rows:
                _streambeam_last_good[site_name] = last_good_ft
    except Exception:
        pass  # Table might not exist yet

def _save_streambeam_last_good(site_name: str, value_ft: float):
    """Save last known good value to SQLite."""
    global _streambeam_db_path
    if _streambeam_db_path is None:
        return
    try:
        with sqlite3.connect(_streambeam_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO streambeam_last_good (site_name, last_good_ft, updated_at)
                VALUES (?, ?, ?)
            """, (site_name, value_ft, datetime.now().isoformat()))
            conn.commit()
    except Exception:
        pass  # Don't fail the whole fetch if DB write fails

def convert_streambeam_timestamp_to_iso(timestamp_str: str) -> str:
    """
    Convert StreamBeam timestamp format to ISO 8601.
    Input: "2025-11-03 07:44 AM CST"
    Output: "2025-11-03T07:44:00-06:00"
    """
    if not timestamp_str:
        return ""

    try:
        # Parse StreamBeam format: "2025-11-03 07:44 AM CST"
        # Remove timezone abbreviation (CST, CDT, etc) for now
        ts_without_tz = timestamp_str.rsplit(' ', 1)[0]  # "2025-11-03 07:44 AM"

        # Parse the datetime
        dt = datetime.strptime(ts_without_tz, "%Y-%m-%d %I:%M %p")

        # Assume Central Time (CST/CDT) - most StreamBeam gauges are in central time
        # CST = UTC-6, CDT = UTC-5
        # For simplicity, use -06:00 (CST) year-round
        # If you need DST handling, you'd need pytz library
        if "CDT" in timestamp_str:
            tz_offset = "-05:00"
        else:  # CST or unknown
            tz_offset = "-06:00"

        # Format as ISO 8601
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + tz_offset
    except Exception:
        # If parsing fails, return original
        return timestamp_str

def fetch_streambeam_latest(entry):
    """
    Fetch latest StreamBeam gauge reading for a site.
    Returns data in same format as fetch_latest() for compatibility.

    Includes sanity checking to reject wild readings:
    - streambeam_min_valid_ft: minimum valid reading (default: -10.0)
    - streambeam_max_valid_ft: maximum valid reading (default: 50.0)
    - streambeam_max_change_ft: max change from last good reading (default: 5.0)
    """
    global _streambeam_last_good

    if not STREAMBEAM_AVAILABLE:
        raise RuntimeError("StreamBeam scraper not available")

    site_name = entry.get("name", "unknown")

    # Sanity check thresholds from config
    min_valid_ft = float(entry.get("streambeam_min_valid_ft", -10.0))
    max_valid_ft = float(entry.get("streambeam_max_valid_ft", 50.0))
    max_change_ft = float(entry.get("streambeam_max_change_ft", 5.0))

    # Build StreamBeam entry format
    sb_entry = {
        "name": site_name,
        "site_id": entry.get("streambeam_site_id"),
        "url": entry.get("streambeam_url"),
        "zero_offset_ft": float(entry.get("streambeam_zero_offset", 0.0)),
        "floor_at_zero": bool(entry.get("streambeam_floor_at_zero", True))
    }

    # Scrape the data
    result = streambeam_scrape_one(sb_entry, timeout=25, def_zero=0.0, def_floor=True)

    if not result.get("ok"):
        raise RuntimeError(f"StreamBeam fetch failed: {result.get('error', 'Unknown error')}")

    adjusted_ft = result.get("adjusted_ft")

    # SANITY CHECK 1: Absolute bounds
    if adjusted_ft < min_valid_ft or adjusted_ft > max_valid_ft:
        raise ValueError(
            f"StreamBeam reading {adjusted_ft:.2f} ft is outside valid range "
            f"[{min_valid_ft}, {max_valid_ft}] - rejecting as bad data"
        )

    # SANITY CHECK 2: Rate of change from last known good value
    last_good = _streambeam_last_good.get(site_name)
    if last_good is not None:
        change = abs(adjusted_ft - last_good)
        if change > max_change_ft:
            raise ValueError(
                f"StreamBeam reading {adjusted_ft:.2f} ft changed {change:.2f} ft from last good "
                f"reading ({last_good:.2f} ft) - exceeds max change of {max_change_ft} ft - "
                f"rejecting as bad data"
            )

    # Reading passed sanity checks - update last known good value (memory + SQLite)
    _streambeam_last_good[site_name] = adjusted_ft
    _save_streambeam_last_good(site_name, adjusted_ft)

    # Convert StreamBeam timestamp to ISO format
    streambeam_timestamp = result.get("observed_at_local", "")
    iso_timestamp = convert_streambeam_timestamp_to_iso(streambeam_timestamp)

    # Convert StreamBeam format to USGS-compatible format
    # StreamBeam returns: adjusted_ft, observed_at_local
    # USGS format expects: stage_ft, ts_iso, discharge_cfs, site
    return {
        "site": entry.get("streambeam_site_id", entry.get("name")),
        "url": result.get("url"),
        "ts_iso": iso_timestamp,
        "stage_ft": adjusted_ft,
        "discharge_cfs": None  # StreamBeam doesn't provide CFS
    }

def generate_sparkline_html(trend_data, site_id):
    """Generate CSS bar chart sparkline HTML with individual bar colors, wrapped in detail page link"""
    # Build link to our custom detail page
    detail_url = f"details/{site_id}.html"

    if not trend_data or not trend_data.get("values"):
        return f'<a href="{detail_url}" class="sparkline-link"><div class="sparkline-empty">—</div></a>'

    values = trend_data["values"]

    # Normalize values to 0-100 scale for bar heights
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val if max_val > min_val else 1

    # Generate bar divs with individual colors based on change from previous bar
    bars = []
    for i, v in enumerate(values):
        height = int(((v - min_val) / range_val) * 100)

        # Color each bar based on whether it's higher or lower than previous
        if i == 0:
            # First bar is gray (no previous to compare)
            color_class = "sparkline-steady"
        elif v > values[i-1]:
            # Rising from previous bar = green
            color_class = "sparkline-rising"
        elif v < values[i-1]:
            # Falling from previous bar = red
            color_class = "sparkline-falling"
        else:
            # Same as previous = gray
            color_class = "sparkline-steady"

        bars.append(f'<div class="sparkline-bar {color_class}" style="height:{height}%"></div>')

    sparkline_div = f'<div class="sparkline">{"".join(bars)}</div>'
    return f'<a href="{detail_url}" class="sparkline-link">{sparkline_div}</a>'

# ---------------- Email ----------------
def send_email(smtp: dict, subject: str, body: str):
    msg = MIMEText(body)

    # Handle both single email and list of emails for recipients
    to_addrs = smtp["to"]
    if isinstance(to_addrs, str):
        to_addrs = [to_addrs]
    elif not isinstance(to_addrs, list):
        to_addrs = [str(to_addrs)]

    # From address fallback logic
    from_addr = smtp.get("from") or smtp.get("user")
    if not from_addr:
        from_addr = to_addrs[0] if to_addrs else "noreply@example.com"

    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)  # Comma-separated list for header

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp["server"], int(smtp.get("port", 465)), context=context) as server:
        if smtp.get("user") and smtp.get("pass"):
            server.login(smtp["user"], smtp["pass"])
        server.send_message(msg, from_addr=from_addr, to_addrs=to_addrs)

# ---------------- HTML render ----------------
def format_timestamp(iso_str: str) -> str:
    """Convert ISO timestamp to readable format like '10:29AM 10-29-2025'"""
    if not iso_str:
        return ""
    try:
        # Parse ISO 8601 format (e.g., "2025-10-29T10:29:00-05:00")
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        # Format as "10:29AM 10-29-2025"
        return dt.strftime("%-I:%M%p %m-%d-%Y")
    except Exception:
        # If parsing fails, return original
        return iso_str

def format_timestamp_stacked(iso_str: str) -> str:
    """Convert ISO timestamp to stacked HTML format (time on top, date below)"""
    if not iso_str:
        return ""
    try:
        # Parse ISO 8601 format (e.g., "2025-10-29T10:29:00-05:00")
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        time_str = dt.strftime("%-I:%M%p")
        date_str = dt.strftime("%m-%d-%Y")
        return f'<div class="time">{time_str}</div><div class="date">{date_str}</div>'
    except Exception:
        # If parsing fails, return original
        return iso_str

def render_static_html(generated_at_iso: str, rows: list, wind_threshold_mph: float = 10, wind_alert_color: str = "#ffc107", temp_threshold_f: float = 55, temp_alert_color: str = "#add8e6", temp_cold_threshold_f: float = 45, temp_cold_alert_color: str = "#1e90ff"):
    def row_html(r):
        trend = r.get("trend_8h")
        trend_icon = "↗" if trend == "rising" else ("↘" if trend == "falling" else ("→" if trend else ""))
        thbits = []
        if isinstance(r.get("threshold_ft"), (int,float)): thbits.append(f"≥ {r['threshold_ft']:.2f} ft")
        if isinstance(r.get("threshold_cfs"), (int,float)): thbits.append(f"≥ {int(r['threshold_cfs'])} cfs")
        sub_parts = []
        if thbits: sub_parts.extend(thbits)
        # Color the trend text: green for rising, light red for falling
        if trend:
            if trend == "rising":
                sub_parts.append(f'<span class="trend-rising">{trend_icon} {trend}</span>')
            elif trend == "falling":
                sub_parts.append(f'<span class="trend-falling">{trend_icon} {trend}</span>')
            else:
                sub_parts.append(f"{trend_icon} {trend}")
        sub = " • ".join(sub_parts)

        # Multi-level classification for specific sites
        site_id = r.get('site', '')
        name = r.get('name', '')

        if site_id == "02399200":  # Little River Canyon
            cfs = r.get('cfs')
            if cfs is None:
                cls = "out"
            elif cfs < 250:
                cls = "out"
            elif cfs < 400:
                cls = "good-low"
            elif cfs < 800:
                cls = "shitty-medium"
            elif cfs < 1500:
                cls = "good-medium"
            elif cfs < 2500:
                cls = "good-high"
            else:  # 2500+
                cls = "too-high"
        elif "Short Creek" in name:  # Short Creek (StreamBeam)
            stage_ft = r.get('stage_ft')
            if stage_ft is None:
                cls = "out"
            elif stage_ft < 0.5:
                cls = "out"  # Too low
            elif stage_ft <= 1.5:
                cls = "in"   # Good range (0.5-1.5 ft)
            else:
                cls = "too-high"  # Too high, dangerous
        else:
            # Standard binary classification for other sites
            cls = "in" if r.get("in_range") else "out"

        # Check if data is stale (> 1 hour old)
        stale_indicator = ""
        ts_iso = r.get('ts_iso')
        if ts_iso:
            try:
                dt = datetime.fromisoformat(ts_iso.replace('Z', '+00:00'))
                now = datetime.now(dt.tzinfo)
                age_minutes = (now - dt).total_seconds() / 60
                if age_minutes > 60:  # More than 1 hour
                    stale_indicator = " ⏳"
            except Exception:
                pass

        # Format QPF (rainfall forecast) if available
        qpf_line = ""
        qpf_data = r.get("qpf")
        if qpf_data and isinstance(qpf_data, dict):
            sorted_dates = sorted(qpf_data.keys())
            qpf_parts = []
            labels = ["Today", "Tomorrow", "Day 3"]
            for i, date_key in enumerate(sorted_dates[:3]):
                label = labels[i] if i < len(labels) else f"Day {i+1}"
                inches = qpf_data[date_key]
                # Highlight significant rainfall (> 0.5") with blue text and rain emoji
                if inches > 0.5:
                    qpf_parts.append(f'<span class="rain-alert">{label}: {inches:.2f}" 🌧️</span>')
                else:
                    qpf_parts.append(f"{label}: {inches:.2f}\"")
            if qpf_parts:
                qpf_line = f'<div class="sub qpf">QPF {" · ".join(qpf_parts)}</div>'

        # Format weather observations (temp, wind) if available
        obs_line = ""
        obs_data = r.get("obs")
        if obs_data and isinstance(obs_data, dict):
            obs_parts = []
            station = obs_data.get("station", "")
            # Temperature
            temp_f = obs_data.get("temp_f")
            if temp_f is not None:
                # Highlight temperatures below thresholds
                if temp_f < temp_cold_threshold_f:
                    obs_parts.append(f'❄️ <span class="temp-cold-alert">{temp_f}°F</span>')
                elif temp_f < temp_threshold_f:
                    obs_parts.append(f'<span class="temp-alert">{temp_f}°F</span>')
                else:
                    obs_parts.append(f"{temp_f}°F")
            # Wind
            wind_mph = obs_data.get("wind_mph")
            wind_dir = obs_data.get("wind_dir")
            wind_gust = obs_data.get("wind_gust_mph")
            if wind_mph is not None:
                # Highlight wind speeds over threshold in yellow
                if wind_mph > wind_threshold_mph:
                    wind_str = f'Wind: <span class="wind-alert">{wind_mph} mph</span> {wind_dir}'
                    if wind_gust is not None and wind_gust > wind_mph:
                        wind_str += f" (gust {wind_gust})"
                else:
                    wind_str = f"Wind: {wind_mph} mph {wind_dir}"
                    if wind_gust is not None and wind_gust > wind_mph:
                        wind_str += f" (gust {wind_gust})"
                obs_parts.append(wind_str)
            # Wind Chill
            wind_chill_f = obs_data.get("wind_chill_f")
            wind_chill_emoji = obs_data.get("wind_chill_emoji")
            wind_chill_desc = obs_data.get("wind_chill_desc")
            if wind_chill_f is not None:
                obs_parts.append(f'{wind_chill_emoji} <span class="wind-chill">Feels: {wind_chill_f:.0f}°F</span>')
            if obs_parts:
                # Use city abbreviation if available, otherwise use airport code
                city_label = STATION_CITY_LABELS.get(station, station)
                station_label = f" ({city_label})" if city_label else ""
                obs_line = f'<div class="sub obs">{" · ".join(obs_parts)}{station_label}</div>'

        # Format secondary weather observations (valley trend) if available
        obs_secondary_line = ""
        obs_secondary = r.get("obs_secondary")
        if obs_secondary and isinstance(obs_secondary, dict):
            obs_sec_parts = []
            station = obs_secondary.get("station", "")
            # Temperature
            temp_f = obs_secondary.get("temp_f")
            if temp_f is not None:
                if temp_f < temp_cold_threshold_f:
                    obs_sec_parts.append(f'❄️ <span class="temp-cold-alert">{temp_f}°F</span>')
                elif temp_f < temp_threshold_f:
                    obs_sec_parts.append(f'<span class="temp-alert">{temp_f}°F</span>')
                else:
                    obs_sec_parts.append(f"{temp_f}°F")
            # Wind
            wind_mph = obs_secondary.get("wind_mph")
            wind_dir = obs_secondary.get("wind_dir")
            wind_gust = obs_secondary.get("wind_gust_mph")
            if wind_mph is not None:
                if wind_mph > wind_threshold_mph:
                    wind_str = f'Wind: <span class="wind-alert">{wind_mph} mph</span> {wind_dir}'
                    if wind_gust is not None and wind_gust > wind_mph:
                        wind_str += f" (gust {wind_gust})"
                else:
                    wind_str = f"Wind: {wind_mph} mph {wind_dir}"
                    if wind_gust is not None and wind_gust > wind_mph:
                        wind_str += f" (gust {wind_gust})"
                obs_sec_parts.append(wind_str)
            # Wind Chill
            wind_chill_f = obs_secondary.get("wind_chill_f")
            wind_chill_emoji = obs_secondary.get("wind_chill_emoji")
            wind_chill_desc = obs_secondary.get("wind_chill_desc")
            if wind_chill_f is not None:
                obs_sec_parts.append(f'{wind_chill_emoji} <span class="wind-chill">Feels: {wind_chill_f:.0f}°F</span>')
            if obs_sec_parts:
                # Use city abbreviation if available, otherwise use airport code
                city_label = STATION_CITY_LABELS.get(station, station)
                station_label = f" ({city_label})" if city_label else ""
                obs_secondary_line = f'<div class="sub obs-secondary">{" · ".join(obs_sec_parts)}{station_label}</div>'

        # Build USGS site URL
        site_id = r.get('site', '')

        # Generate sparkline for trend (with clickable link to USGS graph)
        sparkline_html = generate_sparkline_html(r.get("trend_data"), site_id)
        usgs_url = f"https://waterdata.usgs.gov/nwis/uv?site_no={site_id}&legacy=1" if site_id else "#"

        return f"""
        <tr class="{cls}">
          <td>
            <div class="river"><a href="{usgs_url}" target="_blank" rel="noopener">{h(r.get('name') or r.get('site') or '')}</a></div>
            <div class="sub">{sub}</div>
            {qpf_line}
            {obs_line}
            {obs_secondary_line}
          </td>
          <td class="sparkline-cell">{sparkline_html}</td>
          <td class="center">{("" if r.get('cfs') is None else f"{int(round(r['cfs'])):,}")}</td>
          <td class="num">{("" if r.get('stage_ft') is None else f"{r['stage_ft']:.2f}")}</td>
          <td class="num timestamp-cell"><a href="{h(r.get('waterdata_url') or '#')}">{format_timestamp_stacked(r.get('ts_iso') or '')}{stale_indicator}</a></td>
        </tr>"""
    rows_sorted = sorted(rows, key=lambda r: (not r.get("in_range", False), (r.get("name") or r.get("site") or "")))
    trs = "\n".join(row_html(r) for r in rows_sorted)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>River Levels</title>
<style>
  :root {{ --green:#b7ff9c; }}
  body {{ font-family: system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; margin:0; color:#111; }}
  .wrap {{ max-width: 1000px; margin: 0 auto; padding: 16px; }}
  h1 {{ margin:0 0 4px; font-size:22px; }} .muted{{color:#555;font-size:13px}}
  table {{ width:100%; border-collapse:collapse; margin-top:8px; }}
  thead td {{ font-weight:600; font-size:16px; padding:8px; border-bottom:1px solid #ddd; }}
  tbody tr td {{ padding:10px 6px; vertical-align:middle; }}
  tbody tr.in {{ background: var(--green); }}
  tbody tr.out {{ background: #f6f7f9; }}
  tbody tr.good-low {{ background: #fff9c4; }}
  tbody tr.shitty-medium {{ background: #d4a574; }}
  tbody tr.good-medium {{ background: #c8e6c9; }}
  tbody tr.good-high {{ background: var(--green); }}
  tbody tr.too-high {{ background: #ffcdd2; }}
  .river {{ font-weight:600; }}
  .river a {{ color: #1a73e8; border-bottom: 1px solid #1a73e8; }}
  .river a:hover {{ color: #0d47a1; border-bottom-color: #0d47a1; }}
  .sub{{font-size:14px;color:#444}}
  .num {{ text-align:right; white-space:nowrap; }}
  .center {{ text-align:center; white-space:nowrap; }}

  /* Stacked timestamp styling */
  .timestamp-cell {{ line-height: 1.3; text-align: center; }}
  .time {{ font-weight: 600; font-size: 14px; }}
  .date {{ font-size: 12px; color: #666; }}

  /* Column separation */
  tbody tr td {{ border-left: 1px solid rgba(0,0,0,0.08); }}
  tbody tr td:first-child {{ border-left: none; }}

  /* Sparkline styling */
  .sparkline-cell {{ text-align: center; padding: 10px 8px !important; }}
  .sparkline {{
    display: inline-flex;
    align-items: flex-end;
    height: 32px;
    gap: 2px;
    padding: 2px;
  }}
  .sparkline-bar {{
    width: 4px;
    min-height: 2px;
    border-radius: 1px;
    transition: opacity 0.2s;
  }}
  .sparkline-bar.sparkline-rising {{ background: #4ade80; }}  /* Green for rising */
  .sparkline-bar.sparkline-falling {{ background: #ef4444; }}  /* Red for falling */
  .sparkline-bar.sparkline-steady {{ background: #94a3b8; }}  /* Gray for steady */
  .sparkline-empty {{ color: #94a3b8; font-size: 18px; }}

  /* Clickable sparkline link styling */
  .sparkline-link {{
    border-bottom: none !important;
    cursor: pointer;
    display: inline-block;
    transition: opacity 0.2s;
  }}
  .sparkline-link:hover {{
    opacity: 0.7;
  }}
  .sparkline-link:active {{
    opacity: 0.5;
  }}

  a {{ color: inherit; text-decoration: none; border-bottom: 1px dashed #aaa; }}
  a:hover {{ border-bottom-color: #333; }}
  .foot {{ margin-top:16px; font-size:12px; color:#666; }}
  .rain-alert {{ color:#1e90ff; font-weight:600; }}
  .wind-alert {{ color:{wind_alert_color}; font-weight:600; }}
  .temp-alert {{ color:{temp_alert_color}; font-weight:600; }}
  .temp-cold-alert {{ color:{temp_cold_alert_color}; font-weight:600; }}
  .wind-chill {{ color:#87ceeb; font-weight:600; }}
  .trend-rising {{ color:#4ade80; font-weight:600; }}
  .trend-falling {{ color:#f87171; font-weight:600; }}

  /* Mobile optimizations */
  @media (max-width: 768px) {{
    .wrap {{ padding: 12px; }}
    h1 {{ font-size: 20px; }}
    .muted {{ font-size: 12px; }}

    /* Stack header on mobile */
    .wrap > div:first-of-type {{ flex-direction: column !important; align-items: flex-start !important; gap: 8px; }}

    /* Make table more compact */
    thead td {{ font-size: 14px; padding: 6px 4px; }}
    tbody tr td {{ padding: 8px 4px; font-size: 14px; }}
    .river {{ font-size: 15px; }}
    .sub {{ font-size: 13px; }}
    .qpf {{ font-size: 12px; }}

    /* Adjust number columns to take less space */
    .num {{ font-size: 14px; }}

    /* Stacked timestamp on mobile */
    .time {{ font-size: 13px; }}
    .date {{ font-size: 11px; }}

    /* Smaller sparklines on mobile */
    .sparkline {{ height: 28px; gap: 1.5px; }}
    .sparkline-bar {{ width: 3px; }}
    .sparkline-cell {{ padding: 8px 4px !important; }}

    /* Make links more touch-friendly */
    a {{ padding: 4px 0; display: inline-block; }}

    /* Better wrapping for long names */
    .river, .sub {{ word-wrap: break-word; }}

    .foot {{ font-size: 11px; margin-top: 12px; }}
  }}

  /* Extra small phones */
  @media (max-width: 400px) {{
    h1 {{ font-size: 18px; }}
    thead td {{ font-size: 13px; padding: 6px 2px; }}
    tbody tr td {{ padding: 8px 2px; font-size: 13px; }}
    .river {{ font-size: 14px; }}
    .sub, .qpf {{ font-size: 12px; }}
    .num {{ font-size: 13px; }}

    /* Even smaller stacked timestamp */
    .time {{ font-size: 12px; }}
    .date {{ font-size: 10px; }}

    /* Even smaller sparklines on tiny phones */
    .sparkline {{ height: 24px; gap: 1px; }}
    .sparkline-bar {{ width: 2.5px; }}
  }}
</style>
</head><body>
<div class="wrap">
  <table>
    <thead><tr><td>River</td><td class="center">12hr</td><td class="center">CFS</td><td class="num">Feet</td><td class="center">Updated</td></tr></thead>
    <tbody>{trs}</tbody>
  </table>
  <div class="foot" style="margin-top:8px;"><a href="http://flowpage.alabamawhitewater.com/" target="_blank" rel="noopener">Alabama Flow Page</a></div>
  <div class="foot" style="margin-top:8px;"><a href="https://syotr.org/" target="_blank" rel="noopener">See You On The River</a></div>
  <div class="foot" style="margin-top:8px;"><a href="https://rainpursuit.org/map/?supporter=true" target="_blank" rel="noopener">Rain Pursuit</a></div>
  <div class="foot" style="margin-top:16px; padding-top:8px; border-top:1px solid #ddd;"><a href="test_visual_indicators.html" target="_blank">🧪 Visual Indicators Test Suite</a></div>
</div>
</body></html>"""

# --------------- Main ---------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to JSON config file")
    ap.add_argument("--quiet", action="store_true", help="Only print on alerts/errors")
    ap.add_argument("--cfs", action="store_true", help="Force include discharge (00060) for all sites")
    ap.add_argument("--dump-json", help="Write a JSON feed to this path")
    ap.add_argument("--dump-html", help="Write a static HTML page (no JS) to this path")
    ap.add_argument("--trend-hours", type=int, default=0, help="Compute trend over last N hours for stage (00065)")
    args = ap.parse_args()

    with open(args.config, "r") as f:
        cfg = json.load(f)

    # SMTP config with environment variable overrides for sensitive data
    smtp = cfg["smtp"].copy()
    smtp["user"] = os.environ.get("SMTP_USER", smtp.get("user"))
    smtp["pass"] = os.environ.get("SMTP_PASS", smtp.get("pass"))

    # Handle SMTP_TO as either single email or comma-separated list
    smtp_to_env = os.environ.get("SMTP_TO")
    if smtp_to_env:
        # Split by comma if multiple emails provided via env var
        smtp["to"] = [email.strip() for email in smtp_to_env.split(",")]
    elif "to" not in smtp or smtp["to"] is None:
        smtp["to"] = []

    smtp["from"] = os.environ.get("SMTP_FROM", smtp.get("from"))

    sites_cfg = cfg["sites"]
    defaults = cfg.get("defaults", {})
    def_default_ft  = defaults.get("min_ft")
    def_default_cfs = defaults.get("min_cfs")

    cooldown_hours = int(cfg.get("cooldown_hours", 6))
    cooldown_sec = cooldown_hours * 3600

    notify_cfg = cfg.get("notify", {})
    notify_mode = str(notify_cfg.get("mode", "any")).lower().strip()   # "any" OR "rising"
    send_out = bool(notify_cfg.get("send_out", False))
    out_cooldown_hours = int(notify_cfg.get("out_cooldown_hours", cooldown_hours))
    out_cooldown_sec = out_cooldown_hours * 3600

    pct_change_cfg = cfg.get("percent_change_alert", {})
    pct_change_enabled = bool(pct_change_cfg.get("enabled", False))
    pct_change_threshold = float(pct_change_cfg.get("threshold_percent", 20))
    pct_change_cooldown_hours = int(pct_change_cfg.get("cooldown_hours", 2))
    pct_change_cooldown_sec = pct_change_cooldown_hours * 3600

    # Visual indicators config (wind, temperature alerts)
    visual_indicators = cfg.get("visual_indicators", {})
    wind_threshold_mph = float(visual_indicators.get("wind_threshold_mph", 10))
    wind_alert_color = visual_indicators.get("wind_alert_color", "#ffc107")
    temp_threshold_f = float(visual_indicators.get("temp_threshold_f", 55))
    temp_alert_color = visual_indicators.get("temp_alert_color", "#add8e6")
    temp_cold_threshold_f = float(visual_indicators.get("temp_cold_threshold_f", 45))
    temp_cold_alert_color = visual_indicators.get("temp_cold_alert_color", "#1e90ff")

    # Initialize QPF client for rainfall forecasts
    qpf_client = None
    if QPF_AVAILABLE:
        nws_ua = os.environ.get("NWS_UA", "usgs-alert/1.0")
        nws_contact = os.environ.get("NWS_CONTACT", smtp.get("user", "you@example.com"))
        qpf_cache = os.environ.get("QPF_CACHE", "/data/qpf_cache.sqlite")
        qpf_ttl_hours = int(os.environ.get("QPF_TTL_HOURS", "3"))
        try:
            qpf_client = QPFClient(user_agent=nws_ua, contact_email=nws_contact, cache_path=qpf_cache, ttl_hours=qpf_ttl_hours)
        except Exception as e:
            if not args.quiet:
                print(f"[WARN] QPF client initialization failed: {e}")

    state_db = cfg.get("state_db"); state_file_legacy = cfg.get("state_file")

    now = time.time()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    conn = None
    if state_db:
        ensure_parent_dir(state_db)
        conn = open_state_db(state_db)
        if state_file_legacy:
            migrate_json_to_db(state_file_legacy, conn)
        # Initialize StreamBeam last-good tracking in same database
        _init_streambeam_table(state_db)
        _load_streambeam_last_good(state_db)

    def get_site_state(site):
        if conn:
            return read_site_state(conn, site)
        try:
            with open(state_file_legacy, "r") as f:
                data = json.load(f)
            return data.get(site, {})
        except Exception:
            return {}

    def set_site_state(site, site_state):
        if conn:
            write_site_state(conn, site, site_state)
        else:
            data = {}
            if state_file_legacy:
                try:
                    with open(state_file_legacy, "r") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
                ensure_parent_dir(state_file_legacy)
                data[site] = site_state
                with open(state_file_legacy, "w") as f:
                    json.dump(data, f, indent=2, sort_keys=True)

    def is_in(stage, cfs, th_ft, th_cfs):
        cond_ft = True if th_ft is None else (stage is not None and stage >= th_ft)
        cond_cfs = True if th_cfs is None else (cfs is not None and cfs >= th_cfs)
        return cond_ft and cond_cfs

    feed_rows = []

    for entry in sites_cfg:
        # Determine data source (default to "usgs")
        source = entry.get("source", "usgs").lower()

        if source == "streambeam":
            # StreamBeam source - use streambeam_site_id or name as identifier
            site_raw = entry.get("streambeam_site_id") or entry.get("name", "unknown")
            site = site_raw  # No normalization needed for StreamBeam
            name = entry.get("name", site_raw)
            th_ft = entry.get("min_ft", def_default_ft)
            th_cfs = entry.get("min_cfs", def_default_cfs)

            streambeam_error = None
            try:
                data = fetch_streambeam_latest(entry)
                stage = data["stage_ft"]; ts_iso = data["ts_iso"]; discharge = data["discharge_cfs"]
            except (RuntimeError, ValueError) as e:
                streambeam_error = str(e)
                if not args.quiet:
                    print(f"[ERROR] StreamBeam fetch {site_raw} failed: {e}")
                # Try to use last known good value from cache
                last_good = _streambeam_last_good.get(name)
                if last_good is not None:
                    if not args.quiet:
                        print(f"[INFO] Using last known good value for {name}: {last_good:.2f} ft")
                    stage = last_good
                    ts_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "-06:00"  # Mark as now but stale
                    discharge = None
                else:
                    # No last known good value - skip this site entirely
                    if not args.quiet:
                        print(f"[WARN] No last known good value for {name}, skipping")
                    continue

            # StreamBeam doesn't provide historical data, so no trend data
            trend_label = "⚠ stale" if streambeam_error else None
            trend_data = None

        else:
            # USGS source (default)
            site_raw = entry["site"]
            site = normalize_site_id(site_raw)         # hardened
            name = entry.get("name", site)
            include_q = bool(entry.get("include_discharge", False) or args.cfs)
            th_ft = entry.get("min_ft", def_default_ft)
            th_cfs = entry.get("min_cfs", def_default_cfs)

            try:
                data = fetch_latest(site, include_discharge=include_q)
            except (URLError, HTTPError, RuntimeError, ValueError) as e:
                if not args.quiet:
                    print(f"[ERROR] fetch {site_raw} failed: {e}")
                continue

            stage = data["stage_ft"]; ts_iso = data["ts_iso"]; discharge = data["discharge_cfs"]

            # Fetch trend data for USGS sites
            trend_label = fetch_trend_label(site, args.trend_hours) if (args.trend_hours and (args.dump_json or args.dump_html)) else None
            trend_data = fetch_trend_data(site, 12) if (args.dump_json or args.dump_html) else None

        # Common processing for both sources
        in_range = is_in(stage, discharge, th_ft, th_cfs)

        if not args.quiet:
            th_bits = []
            if th_ft is not None: th_bits.append(f"{th_ft:.2f} ft")
            if th_cfs is not None: th_bits.append(f"{int(th_cfs)} cfs")
            thresh_str = " & ".join(th_bits) if th_bits else "no min"
            cfs_part = f" - {discharge:.0f} cfs" if discharge is not None else ""
            source_tag = f"[{source.upper()}]"
            print(f"[INFO] {source_tag} {name}: {stage if stage is not None else 'NA'} ft{cfs_part} @ {ts_iso} (mins: {thresh_str}) -> {'IN' if in_range else 'OUT'}")

        # Fetch QPF (rainfall forecast) if available
        qpf_data = None
        if qpf_client and entry.get("lat") and entry.get("lon"):
            try:
                qpf_data = qpf_client.get_qpf_by_day(entry["lat"], entry["lon"], days=3)
            except Exception as e:
                if not args.quiet:
                    print(f"[WARN] QPF fetch failed for {site}: {e}")

        # Fetch weather observations (temp, wind) if available
        obs_data = None
        if OBS_AVAILABLE and name in WEATHER_STATIONS:
            station = WEATHER_STATIONS[name]
            try:
                obs = fetch_latest_observation(station)
                # Calculate wind chill
                wind_chill_temp, wind_chill_emoji, wind_chill_desc = calculate_wind_chill(obs["temp_f"], obs["wind_mph"])
                obs_data = {
                    "station": station,
                    "temp_f": obs["temp_f"],
                    "wind_mph": obs["wind_mph"],
                    "wind_dir": fmt_dir(obs["wind_dir_deg"]),
                    "wind_gust_mph": obs["wind_gust_mph"],
                    "wind_chill_f": wind_chill_temp,
                    "wind_chill_emoji": wind_chill_emoji,
                    "wind_chill_desc": wind_chill_desc
                }
            except Exception as e:
                if not args.quiet:
                    print(f"[WARN] Weather observation fetch failed for {name} [{station}]: {e}")

        # Fetch secondary weather observations for sites that need valley trend data
        obs_secondary = None
        if OBS_AVAILABLE and name in WEATHER_STATIONS_SECONDARY:
            station_secondary = WEATHER_STATIONS_SECONDARY[name]
            try:
                obs = fetch_latest_observation(station_secondary)
                # Calculate wind chill for secondary station
                wind_chill_temp_sec, wind_chill_emoji_sec, wind_chill_desc_sec = calculate_wind_chill(obs["temp_f"], obs["wind_mph"])
                obs_secondary = {
                    "station": station_secondary,
                    "temp_f": obs["temp_f"],
                    "wind_mph": obs["wind_mph"],
                    "wind_dir": fmt_dir(obs["wind_dir_deg"]),
                    "wind_gust_mph": obs["wind_gust_mph"],
                    "wind_chill_f": wind_chill_temp_sec,
                    "wind_chill_emoji": wind_chill_emoji_sec,
                    "wind_chill_desc": wind_chill_desc_sec
                }
            except Exception as e:
                if not args.quiet:
                    print(f"[WARN] Secondary weather observation fetch failed for {name} [{station_secondary}]: {e}")

        feed_rows.append({
            "site": site,
            "name": name,
            "stage_ft": stage,
            "cfs": discharge,
            "ts_iso": ts_iso,
            "threshold_ft": th_ft,
            "threshold_cfs": th_cfs,
            "in_range": in_range,
            "trend_8h": trend_label if args.trend_hours else None,
            "trend_data": trend_data,
            "qpf": qpf_data,
            "obs": obs_data,
            "obs_secondary": obs_secondary,
            "waterdata_url": f"https://waterdata.usgs.gov/monitoring-location/{site}/#parameterCode=00065&period=P7D"
        })

        # Alerts
        site_state = get_site_state(site)
        last_alert_t = float(site_state.get("last_alert_epoch", 0))
        last_out_t   = float(site_state.get("last_out_epoch", 0))
        was_in       = bool(site_state.get("last_in", False))

        def format_thresh(th_ft, th_cfs):
            parts = []
            if th_ft is not None: parts.append(f">= {th_ft:.2f} ft")
            if th_cfs is not None: parts.append(f">= {int(th_cfs)} cfs")
            return " and ".join(parts) if parts else "no minimums"

        def do_in_alert():
            waterdata_url = f"https://waterdata.usgs.gov/monitoring-location/{site}/#parameterCode=00065&period=P7D"
            subj_cfs = f" - {discharge:.0f} cfs" if discharge is not None else ""
            subject = f"{name} is IN ({stage:.2f} ft{subj_cfs})"
            lines = [
                f"{name} is {stage:.2f} ft{subj_cfs} @ {ts_iso} (meets {format_thresh(th_ft, th_cfs)}).",
                f"USGS chart: {waterdata_url}",
                f"API: {data['url']}"
            ]
            body = "\n".join(lines)
            send_email(smtp, subject, body)
            site_state["last_alert_epoch"] = now

        def do_out_alert():
            waterdata_url = f"https://waterdata.usgs.gov/monitoring-location/{site}/#parameterCode=00065&period=P7D"
            subj_cfs = f" - {discharge:.0f} cfs" if discharge is not None else ""
            subject = f"{name} is OUT ({stage:.2f} ft{subj_cfs})"
            lines = [
                f"{name} dropped below {format_thresh(th_ft, th_cfs)}: now {stage:.2f} ft{subj_cfs} @ {ts_iso}.",
                f"USGS chart: {waterdata_url}",
                f"API: {data['url']}"
            ]
            body = "\n".join(lines)
            send_email(smtp, subject, body)
            site_state["last_out_epoch"] = now

        def do_pct_change_alert(pct_change, direction):
            waterdata_url = f"https://waterdata.usgs.gov/monitoring-location/{site}/#parameterCode=00065&period=P7D"
            subj_cfs = f" - {discharge:.0f} cfs" if discharge is not None else ""
            last_ft = site_state.get("last_stage_ft")
            subject = f"{name} {direction.upper()} {abs(pct_change):.1f}% ({stage:.2f} ft{subj_cfs})"
            lines = [
                f"{name} has {direction} by {abs(pct_change):.1f}%",
                f"Previous: {last_ft:.2f} ft",
                f"Current:  {stage:.2f} ft{subj_cfs}",
                f"Time: {ts_iso}",
                f"USGS chart: {waterdata_url}",
                f"API: {data['url']}"
            ]
            body = "\n".join(lines)
            send_email(smtp, subject, body)
            site_state["last_pct_change_epoch"] = now

        try:
            if notify_mode == "rising":
                if (not was_in) and in_range and (now - last_alert_t >= cooldown_sec):
                    do_in_alert()
                    if not args.quiet: print(f"[ALERT] IN (rising) {site}")
            else:
                if in_range and (now - last_alert_t >= cooldown_sec):
                    do_in_alert()
                    if not args.quiet: print(f"[ALERT] IN (any) {site}")

            if send_out and was_in and (not in_range) and (now - last_out_t >= out_cooldown_sec):
                do_out_alert()
                if not args.quiet: print(f"[ALERT] OUT {site}")

            # Percentage change alerts
            if pct_change_enabled and stage is not None:
                last_stage = site_state.get("last_stage_ft")
                last_pct_t = float(site_state.get("last_pct_change_epoch", 0))

                if last_stage is not None and last_stage > 0 and (now - last_pct_t >= pct_change_cooldown_sec):
                    pct_change = ((stage - last_stage) / last_stage) * 100.0

                    if abs(pct_change) >= pct_change_threshold:
                        direction = "increased" if pct_change > 0 else "decreased"
                        do_pct_change_alert(pct_change, direction)
                        if not args.quiet:
                            print(f"[ALERT] PCT_CHANGE {site}: {pct_change:+.1f}% ({last_stage:.2f} -> {stage:.2f} ft)")
        except Exception as e:
            print(f"[ALERT] email failed for {site}: {e}")

        # persist last seen
        site_state["last_stage_ft"] = stage
        site_state["last_ts_iso"]   = ts_iso
        site_state["last_cfs"]      = discharge
        site_state["last_in"]       = in_range

        # Track when river crossed into runnable/green state
        if (not was_in) and in_range:
            site_state["last_in_epoch"] = now

        # Save temperature and wind data if available
        if obs_data:
            site_state["last_temp_f"] = obs_data.get("temp_f")
            site_state["last_wind_mph"] = obs_data.get("wind_mph")
            site_state["last_wind_dir"] = obs_data.get("wind_dir")
            site_state["last_wind_gust_mph"] = obs_data.get("wind_gust_mph")

        set_site_state(site, site_state)

    # Publish feeds/pages
    if args.dump_json:
        payload = {"generated_at": now_iso, "sites": feed_rows}
        ensure_parent_dir(args.dump_json)
        with open(args.dump_json, "w") as f:
            json.dump(payload, f, indent=2)
        if not args.quiet: print(f"[FEED] wrote {args.dump_json} ({len(feed_rows)} sites)")

    if args.dump_html:
        html = render_static_html(now_iso, feed_rows, wind_threshold_mph, wind_alert_color, temp_threshold_f, temp_alert_color, temp_cold_threshold_f, temp_cold_alert_color)
        ensure_parent_dir(args.dump_html)
        with open(args.dump_html, "w", encoding="utf-8") as f:
            f.write(html)
        if not args.quiet: print(f"[PAGE] wrote {args.dump_html} ({len(feed_rows)} sites)")

        # Generate individual detail pages for each site
        if SITE_DETAIL_AVAILABLE:
            # Create details subdirectory
            html_dir = os.path.dirname(args.dump_html)
            details_dir = os.path.join(html_dir, "details")
            os.makedirs(details_dir, exist_ok=True)

            for row in feed_rows:
                site_id = row.get("site")
                if not site_id:
                    continue

                try:
                    # Fetch 7-day historical data
                    cfs_history = fetch_usgs_7day_data(site_id, "00060")  # Discharge
                    feet_history = fetch_usgs_7day_data(site_id, "00065")  # Gage height

                    # Get state data for last_in_epoch
                    site_state = get_site_state(site_id) if conn else {}
                    last_in_epoch = site_state.get("last_in_epoch", 0)

                    # Format last_in_time as human-readable
                    if last_in_epoch and last_in_epoch > 0:
                        last_in_dt = datetime.fromtimestamp(last_in_epoch)
                        last_in_time = last_in_dt.strftime("%b %d, %Y %I:%M %p")
                    else:
                        last_in_time = None

                    # Prepare site data for detail page
                    # Prefer primary obs, but fall back to secondary if primary is unavailable
                    obs_data = row.get("obs", {})
                    obs_secondary = row.get("obs_secondary", {})

                    # Use primary obs if temp_f is available, otherwise use secondary
                    active_obs = obs_data if obs_data and obs_data.get("temp_f") is not None else obs_secondary

                    site_data = {
                        "name": row.get("name"),
                        "site": site_id,
                        "cfs": row.get("cfs"),
                        "stage_ft": row.get("stage_ft"),
                        "temp_f": active_obs.get("temp_f") if active_obs else None,
                        "wind_mph": active_obs.get("wind_mph") if active_obs else None,
                        "wind_dir": active_obs.get("wind_dir") if active_obs else "",
                        "wind_chill_f": active_obs.get("wind_chill_f") if active_obs else None,
                        "wind_chill_emoji": active_obs.get("wind_chill_emoji") if active_obs else None,
                        "wind_chill_desc": active_obs.get("wind_chill_desc") if active_obs else None,
                        "threshold_ft": row.get("threshold_ft"),
                        "threshold_cfs": row.get("threshold_cfs"),
                        "in_range": row.get("in_range", False),
                        "last_in_time": last_in_time
                    }

                    # Generate HTML
                    detail_html = generate_site_detail_html(site_data, cfs_history, feet_history)

                    # Write to file
                    detail_path = os.path.join(details_dir, f"{site_id}.html")
                    with open(detail_path, "w", encoding="utf-8") as f:
                        f.write(detail_html)

                    if not args.quiet:
                        print(f"[DETAIL] wrote {detail_path}")

                except Exception as e:
                    if not args.quiet:
                        print(f"[WARN] Failed to generate detail page for {site_id}: {e}")

    # close DB
    if state_db and 'conn' in locals() and conn:
        conn.commit(); conn.close()

if __name__ == "__main__":
    main()


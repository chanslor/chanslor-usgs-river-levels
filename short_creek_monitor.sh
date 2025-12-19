#!/bin/bash
# Short Creek Monitoring Tool
# Quick command-line display of Short Creek gauge readings

set -euo pipefail

PROD_API="https://docker-blue-sound-1751.fly.dev/api/river-levels/name/short"
STREAMBEAM_URL="https://www.streambeam.net/Home/Gauge?siteID=1"
STATE_DB="usgs-data/state.sqlite"

echo "=================================================="
echo "    SHORT CREEK GAUGE MONITOR"
echo "=================================================="
echo ""

# Function to display current production reading
show_current() {
    echo "📊 CURRENT READING (Production API):"
    echo "--------------------------------------------------"

    if command -v jq >/dev/null 2>&1; then
        # Pretty display with jq
        curl -s "$PROD_API" | jq -r '
            "Site:      " + .name,
            "Stage:     " + (.stage_ft | tostring) + " ft",
            "Flow:      " + .flow,
            "Trend:     " + .trend,
            "In Range:  " + (.in_range | tostring),
            "Timestamp: " + .timestamp,
            "",
            "Weather:",
            "  Temp:    " + (if .weather.temp_f then (.weather.temp_f | tostring) + "°F" else "N/A" end),
            "  Wind:    " + (if .weather.wind_mph then (.weather.wind_mph | tostring) + " mph " + .weather.wind_dir else "N/A" end),
            "",
            "Rainfall Forecast (QPF):",
            "  Today:    " + (.qpf.today | tostring) + "\"",
            "  Tomorrow: " + (.qpf.tomorrow | tostring) + "\"",
            "  Day 3:    " + (.qpf.day3 | tostring) + "\""
        '
    else
        # Fallback without jq
        curl -s "$PROD_API"
    fi
    echo ""
}

# Function to display local state database
show_state() {
    echo "💾 LOCAL STATE DATABASE:"
    echo "--------------------------------------------------"

    if [ ! -f "$STATE_DB" ]; then
        echo "❌ No state database found at $STATE_DB"
        echo ""
        return
    fi

    sqlite3 "$STATE_DB" <<'SQL'
.mode column
.headers on
.width 15 12 25 8
SELECT
    site as "Site ID",
    printf('%.2f', last_stage_ft) as "Last Stage",
    last_ts_iso as "Last Timestamp",
    CASE last_in WHEN 1 THEN 'YES' ELSE 'NO' END as "In Range"
FROM site_state
WHERE site = '1';
SQL
    echo ""
}

# Function to display StreamBeam link
show_streambeam() {
    echo "🌐 STREAMBEAM GAUGE:"
    echo "--------------------------------------------------"
    echo "Website: $STREAMBEAM_URL"
    echo ""
    echo "Note: StreamBeam website shows 72-hour chart."
    echo "      Use your browser to view historical graph."
    echo ""
}

# Function to monitor continuously
monitor_loop() {
    local interval=${1:-60}
    echo "🔄 CONTINUOUS MONITORING (every ${interval}s)"
    echo "   Press Ctrl+C to stop"
    echo "=================================================="
    echo ""

    while true; do
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')

        # Get current reading
        if command -v jq >/dev/null 2>&1; then
            reading=$(curl -s "$PROD_API" | jq -r '
                .stage_ft as $stage |
                .timestamp as $ts |
                "[\($ts)] Stage: \($stage) ft"
            ')
            echo "[$timestamp] $reading"
        else
            echo "[$timestamp] Fetching..."
        fi

        sleep "$interval"
    done
}

# Function to compare readings
compare_readings() {
    echo "🔍 READING COMPARISON:"
    echo "--------------------------------------------------"
    echo ""

    echo "1. Production API Reading:"
    if command -v jq >/dev/null 2>&1; then
        curl -s "$PROD_API" | jq -r '"   Stage: " + (.stage_ft | tostring) + " ft at " + .timestamp'
    else
        echo "   (install jq for formatted output)"
    fi
    echo ""

    echo "2. Local State DB Reading:"
    if [ -f "$STATE_DB" ]; then
        sqlite3 "$STATE_DB" "SELECT '   Stage: ' || printf('%.2f', last_stage_ft) || ' ft at ' || last_ts_iso FROM site_state WHERE site = '1';"
    else
        echo "   No local database"
    fi
    echo ""

    echo "3. StreamBeam Website:"
    echo "   Check manually: $STREAMBEAM_URL"
    echo ""
}

# Function to log reading to file
log_reading() {
    local logfile=${1:-short_creek_log.txt}

    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    if command -v jq >/dev/null 2>&1; then
        reading=$(curl -s "$PROD_API" | jq -r '"stage_ft: \(.stage_ft), timestamp: \(.timestamp), in_range: \(.in_range)"')
        echo "[$timestamp] $reading" | tee -a "$logfile"
        echo "✓ Logged to $logfile"
    else
        echo "Error: jq required for logging" >&2
        exit 1
    fi
}

# Parse command line arguments
case "${1:-current}" in
    current|now)
        show_current
        show_state
        ;;

    state|db)
        show_state
        ;;

    streambeam|web)
        show_streambeam
        ;;

    compare)
        compare_readings
        ;;

    monitor|watch)
        interval=${2:-60}
        monitor_loop "$interval"
        ;;

    log)
        logfile=${2:-short_creek_log.txt}
        log_reading "$logfile"
        ;;

    all)
        show_current
        show_state
        show_streambeam
        ;;

    help|--help|-h)
        cat <<'HELP'
Usage: ./short_creek_monitor.sh [command] [options]

Commands:
  current, now     Show current reading from production API (default)
  state, db        Show local state database entry
  streambeam, web  Show StreamBeam website link
  compare          Compare all three data sources
  monitor [secs]   Continuously monitor (default: 60 seconds)
  log [file]       Log current reading to file (default: short_creek_log.txt)
  all              Show everything
  help             Show this help

Examples:
  ./short_creek_monitor.sh                    # Show current reading
  ./short_creek_monitor.sh compare            # Compare all sources
  ./short_creek_monitor.sh monitor 30         # Monitor every 30 seconds
  ./short_creek_monitor.sh log mylog.txt      # Log reading to file

  # Create a cron job to log every 15 minutes:
  */15 * * * * cd /path/to/docker && ./short_creek_monitor.sh log

Dependencies:
  - curl (required)
  - jq (recommended for formatted output)
  - sqlite3 (for state database access)

HELP
        ;;

    *)
        echo "Unknown command: $1"
        echo "Run './short_creek_monitor.sh help' for usage"
        exit 1
        ;;
esac

#!/usr/bin/env python3
"""
River Predictions Module
Calculates likelihood and timing of rivers reaching runnable levels
based on QPF forecast and historical response patterns.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

def calculate_predictions(sites_data: List[Dict], river_chars: Dict[str, Dict]) -> List[Dict]:
    """
    Calculate predictions for each river based on QPF and characteristics.

    Args:
        sites_data: List of site dictionaries with QPF data
        river_chars: River characteristics from config (response times, rain needed)

    Returns:
        List of prediction dictionaries sorted by likelihood
    """
    predictions = []

    for site in sites_data:
        site_id = site.get('site', '')
        name = site.get('name', '')

        # Find matching river characteristics
        # Try site_id first, then special cases like "short_creek"
        char_key = site_id
        if site_id not in river_chars:
            # Check for StreamBeam/Short Creek
            if 'short' in name.lower():
                char_key = 'short_creek'
            else:
                continue  # No prediction data for this river

        if char_key not in river_chars:
            continue

        chars = river_chars[char_key]

        # Get QPF totals
        qpf = site.get('qpf', {})
        if not qpf:
            continue

        sorted_dates = sorted(qpf.keys())
        qpf_today = qpf.get(sorted_dates[0], 0) if len(sorted_dates) > 0 else 0
        qpf_tomorrow = qpf.get(sorted_dates[1], 0) if len(sorted_dates) > 1 else 0
        qpf_day3 = qpf.get(sorted_dates[2], 0) if len(sorted_dates) > 2 else 0

        total_qpf = qpf_today + qpf_tomorrow + qpf_day3

        # Calculate prediction
        rain_needed = chars.get('rain_needed_inches', 2.0)
        avg_response = chars.get('avg_response_hours', 30)
        response_range = chars.get('response_range', [24, 36])
        responsiveness = chars.get('responsiveness', 'moderate')

        # Calculate likelihood percentage
        if total_qpf <= 0:
            likelihood = 0
        elif total_qpf >= rain_needed * 1.5:
            likelihood = 95  # Very likely
        elif total_qpf >= rain_needed:
            likelihood = 70 + (25 * (total_qpf - rain_needed) / (rain_needed * 0.5))
        elif total_qpf >= rain_needed * 0.75:
            likelihood = 40 + (30 * (total_qpf - rain_needed * 0.75) / (rain_needed * 0.25))
        elif total_qpf >= rain_needed * 0.5:
            likelihood = 15 + (25 * (total_qpf - rain_needed * 0.5) / (rain_needed * 0.25))
        else:
            likelihood = max(0, 15 * total_qpf / (rain_needed * 0.5))

        likelihood = min(95, max(0, int(likelihood)))

        # Determine which day has the most rain (for timing)
        max_rain_day = 0
        max_rain = qpf_today
        if qpf_tomorrow > max_rain:
            max_rain_day = 1
            max_rain = qpf_tomorrow
        if qpf_day3 > max_rain:
            max_rain_day = 2
            max_rain = qpf_day3

        # Calculate estimated peak time
        now = datetime.now(timezone.utc)
        rain_start = now + timedelta(days=max_rain_day)

        # Set rain start to morning of the day with most rain
        rain_start = rain_start.replace(hour=6, minute=0, second=0, microsecond=0)

        peak_earliest = rain_start + timedelta(hours=response_range[0])
        peak_latest = rain_start + timedelta(hours=response_range[1])

        # Status classification
        if likelihood >= 70:
            status = "likely"
            status_emoji = "🟢"
            status_text = "Likely"
        elif likelihood >= 40:
            status = "possible"
            status_emoji = "🟡"
            status_text = "Possible"
        elif likelihood >= 15:
            status = "unlikely"
            status_emoji = "🟠"
            status_text = "Unlikely"
        else:
            status = "very_unlikely"
            status_emoji = "🔴"
            status_text = "Very Unlikely"

        # Is it already running?
        in_range = site.get('in_range', False)
        if in_range:
            status = "running"
            status_emoji = "✅"
            status_text = "Running Now!"
            likelihood = 100

        prediction = {
            'site_id': site_id,
            'name': name,
            'likelihood': likelihood,
            'status': status,
            'status_emoji': status_emoji,
            'status_text': status_text,
            'qpf_total': round(total_qpf, 2),
            'rain_needed': rain_needed,
            'rain_surplus': round(total_qpf - rain_needed, 2),
            'responsiveness': responsiveness,
            'avg_response_hours': avg_response,
            'peak_window': {
                'earliest': peak_earliest.isoformat(),
                'latest': peak_latest.isoformat(),
                'earliest_local': format_local_time(peak_earliest),
                'latest_local': format_local_time(peak_latest)
            },
            'notes': chars.get('notes', ''),
            'in_range': in_range,
            'qpf_breakdown': {
                'today': round(qpf_today, 2),
                'tomorrow': round(qpf_tomorrow, 2),
                'day3': round(qpf_day3, 2)
            }
        }

        predictions.append(prediction)

    # Sort by likelihood (highest first), then by name
    predictions.sort(key=lambda p: (-p['likelihood'], p['name']))

    return predictions


def format_local_time(dt: datetime) -> str:
    """Format datetime as local-friendly string like 'Mon 6pm' or 'Tue morning'"""
    # Convert to Central time (approximate - just subtract 6 hours from UTC)
    local = dt - timedelta(hours=6)

    day_name = local.strftime('%a')
    hour = local.hour

    if 5 <= hour < 12:
        time_str = "morning"
    elif 12 <= hour < 17:
        time_str = "afternoon"
    elif 17 <= hour < 21:
        time_str = "evening"
    else:
        time_str = "night"

    return f"{day_name} {time_str}"


def generate_predictions_html(predictions: List[Dict]) -> str:
    """
    Generate HTML panel for predictions.

    Returns:
        HTML string for the predictions panel
    """
    if not predictions:
        return ""

    # Calculate overall QPF summary
    max_qpf = max(p['qpf_total'] for p in predictions) if predictions else 0

    # Build prediction rows
    rows = []
    for p in predictions:
        likelihood = p['likelihood']

        # Color based on status
        if p['status'] == 'running':
            bg_color = '#c8e6c9'  # Green - running now
            bar_color = '#4caf50'
        elif p['status'] == 'likely':
            bg_color = '#c8e6c9'  # Light green
            bar_color = '#4caf50'
        elif p['status'] == 'possible':
            bg_color = '#fff9c4'  # Yellow
            bar_color = '#ffc107'
        elif p['status'] == 'unlikely':
            bg_color = '#ffe0b2'  # Orange
            bar_color = '#ff9800'
        else:
            bg_color = '#f6f7f9'  # Gray
            bar_color = '#9e9e9e'

        # Timing text
        if p['in_range']:
            timing = "Currently runnable!"
        elif likelihood >= 15:
            timing = f"Peak: {p['peak_window']['earliest_local']} - {p['peak_window']['latest_local']}"
        else:
            timing = "Insufficient rain forecast"

        # Rain comparison
        rain_text = f"{p['qpf_total']:.2f}\" / {p['rain_needed']:.2f}\" needed"
        if p['rain_surplus'] >= 0:
            rain_text += f" (+{p['rain_surplus']:.2f}\")"

        row = f'''
        <div class="pred-row" style="background: {bg_color};">
          <div class="pred-header">
            <span class="pred-name">{p['status_emoji']} {p['name']}</span>
            <span class="pred-likelihood">{likelihood}%</span>
          </div>
          <div class="pred-bar-container">
            <div class="pred-bar" style="width: {likelihood}%; background: {bar_color};"></div>
          </div>
          <div class="pred-details">
            <span class="pred-rain">{rain_text}</span>
            <span class="pred-timing">{timing}</span>
          </div>
        </div>'''
        rows.append(row)

    rows_html = '\n'.join(rows)

    return f'''
    <div class="predictions-panel">
      <div class="pred-title">🔮 River Predictions</div>
      <div class="pred-subtitle">Based on {max_qpf:.2f}" QPF over 72 hours</div>
      {rows_html}
      <div class="pred-footer">
        Response times based on 90-day historical analysis
      </div>
    </div>'''


def get_predictions_css() -> str:
    """Return CSS for the predictions panel"""
    return '''
    /* Predictions Panel */
    .predictions-panel {
      margin: 16px 0;
      padding: 16px;
      background: white;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .pred-title {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 4px;
    }
    .pred-subtitle {
      font-size: 13px;
      color: #666;
      margin-bottom: 16px;
    }
    .pred-row {
      padding: 12px;
      margin-bottom: 8px;
      border-radius: 6px;
    }
    .pred-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .pred-name {
      font-weight: 600;
      font-size: 15px;
    }
    .pred-likelihood {
      font-weight: 700;
      font-size: 16px;
    }
    .pred-bar-container {
      height: 8px;
      background: rgba(0,0,0,0.1);
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 8px;
    }
    .pred-bar {
      height: 100%;
      border-radius: 4px;
      transition: width 0.3s ease;
    }
    .pred-details {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: #555;
    }
    .pred-rain {
      font-weight: 500;
    }
    .pred-timing {
      color: #666;
    }
    .pred-footer {
      margin-top: 12px;
      padding-top: 8px;
      border-top: 1px solid #eee;
      font-size: 11px;
      color: #888;
      text-align: center;
    }

    /* Mobile */
    @media (max-width: 768px) {
      .predictions-panel { padding: 12px; }
      .pred-title { font-size: 16px; }
      .pred-name { font-size: 14px; }
      .pred-details { flex-direction: column; gap: 2px; }
    }
    '''


if __name__ == "__main__":
    # Test the prediction logic
    test_sites = [
        {
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': False,
            'qpf': {'2025-11-30': 0.20, '2025-12-01': 0.10, '2025-12-02': 1.27}
        },
        {
            'site': '03572900',
            'name': 'Town Creek',
            'in_range': False,
            'qpf': {'2025-11-30': 0.20, '2025-12-01': 0.11, '2025-12-02': 1.11}
        },
        {
            'site': 'streambeam_1',
            'name': 'Short Creek',
            'in_range': False,
            'qpf': {'2025-11-30': 0.18, '2025-12-01': 0.10, '2025-12-02': 1.12}
        }
    ]

    test_chars = {
        '02455000': {
            'name': 'Locust Fork',
            'avg_response_hours': 33,
            'response_range': [26, 38],
            'rain_needed_inches': 1.75,
            'responsiveness': 'moderate'
        },
        '03572900': {
            'name': 'Town Creek',
            'avg_response_hours': 32,
            'response_range': [24, 36],
            'rain_needed_inches': 1.25,
            'responsiveness': 'moderate'
        },
        'short_creek': {
            'name': 'Short Creek',
            'avg_response_hours': 12,
            'response_range': [6, 18],
            'rain_needed_inches': 0.65,
            'responsiveness': 'fast'
        }
    }

    predictions = calculate_predictions(test_sites, test_chars)

    print("=== Prediction Test Results ===\n")
    for p in predictions:
        print(f"{p['status_emoji']} {p['name']}: {p['likelihood']}% ({p['status_text']})")
        print(f"   QPF: {p['qpf_total']:.2f}\" / Needed: {p['rain_needed']:.2f}\"")
        print(f"   Peak: {p['peak_window']['earliest_local']} - {p['peak_window']['latest_local']}")
        print()

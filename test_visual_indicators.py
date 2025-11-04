#!/usr/bin/env python3
"""
Visual Indicators Test Generator
Generates a standalone HTML file to test all color zones and alert indicators
"""

import os
import json
import sys

def generate_test_html(wind_threshold_mph=10, wind_alert_color="#ffc107", temp_threshold_f=55, temp_alert_color="#add8e6", temp_cold_threshold_f=45, temp_cold_alert_color="#1e90ff"):
    """Generate comprehensive test HTML for all visual indicators"""

    # CSS copied from usgs_multi_alert.py
    css = """
  :root { --green:#b7ff9c; }
  body { font-family: system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; margin:0; color:#111; background:#fafafa; }
  .wrap { max-width: 1200px; margin: 0 auto; padding: 16px; }
  h1 { margin:0 0 4px; font-size:22px; }
  h2 { margin:24px 0 8px; font-size:18px; color:#444; border-bottom:2px solid #ddd; padding-bottom:4px; }
  .muted{color:#555;font-size:13px}
  table { width:100%; border-collapse:collapse; margin-top:8px; margin-bottom:24px; }
  thead td { font-weight:600; font-size:16px; padding:8px; border-bottom:1px solid #ddd; background:#f0f0f0; }
  tbody tr td { padding:10px 6px; vertical-align:middle; border:1px solid #e0e0e0; }
  tbody tr.in { background: var(--green); }
  tbody tr.out { background: #f6f7f9; }
  tbody tr.good-low { background: #fff9c4; }
  tbody tr.shitty-medium { background: #d4a574; }
  tbody tr.good-medium { background: #c8e6c9; }
  tbody tr.good-high { background: var(--green); }
  tbody tr.too-high { background: #ffcdd2; }
  .river { font-weight:600; }
  .sub{font-size:14px;color:#444}
  .num { text-align:right; white-space:nowrap; }
  .center { text-align:center; white-space:nowrap; }
  .temp-alert { color:TEMP_COLOR_PLACEHOLDER; font-weight:600; }
  .temp-cold-alert { color:TEMP_COLD_COLOR_PLACEHOLDER; font-weight:600; }
  .wind-alert { color:WIND_COLOR_PLACEHOLDER; font-weight:600; }
  .rain-alert { color:#1e90ff; font-weight:600; }
  .legend { display:inline-block; width:20px; height:20px; margin-right:8px; border:1px solid #999; vertical-align:middle; }
  .note { background:#fffbea; border-left:4px solid #ffc107; padding:12px; margin:16px 0; font-size:14px; }
  .test-section { margin-bottom: 32px; }
"""
    # Replace color placeholders with actual config values
    css = css.replace("TEMP_COLOR_PLACEHOLDER", temp_alert_color)
    css = css.replace("TEMP_COLD_COLOR_PLACEHOLDER", temp_cold_alert_color)
    css = css.replace("WIND_COLOR_PLACEHOLDER", wind_alert_color)

    # Test data for Little River Canyon (all CFS levels)
    lrc_tests = [
        # Gray zone (out)
        (0, "out", "< 250 CFS: Not runnable"),
        (100, "out", "< 250 CFS: Not runnable"),
        (200, "out", "< 250 CFS: Not runnable"),
        # Yellow zone (good-low)
        (250, "good-low", "250-400 CFS: Good low water"),
        (300, "good-low", "250-400 CFS: Good low water"),
        (350, "good-low", "250-400 CFS: Good low water"),
        # Brown zone (shitty-medium)
        (400, "shitty-medium", "400-800 CFS: Shitty medium"),
        (500, "shitty-medium", "400-800 CFS: Shitty medium"),
        (600, "shitty-medium", "400-800 CFS: Shitty medium"),
        (700, "shitty-medium", "400-800 CFS: Shitty medium"),
        # Light green zone (good-medium)
        (800, "good-medium", "800-1,500 CFS: Good medium flow"),
        (1000, "good-medium", "800-1,500 CFS: Good medium flow"),
        (1200, "good-medium", "800-1,500 CFS: Good medium flow"),
        (1400, "good-medium", "800-1,500 CFS: Good medium flow"),
        # Green zone (good-high) - BEST CONDITIONS
        (1500, "good-high", "1,500-2,500 CFS: Good high - BEST!"),
        (1750, "good-high", "1,500-2,500 CFS: Good high - BEST!"),
        (2000, "good-high", "1,500-2,500 CFS: Good high - BEST!"),
        (2250, "good-high", "1,500-2,500 CFS: Good high - BEST!"),
        # Red zone (too-high)
        (2500, "too-high", "2,500+ CFS: Too high for most"),
        (3000, "too-high", "2,500+ CFS: Too high for most"),
        (3500, "too-high", "2,500+ CFS: Too high for most"),
        (4000, "too-high", "2,500+ CFS: Too high for most"),
    ]

    # Test data for temperature alerts (generate around both thresholds)
    temp_tests = [
        35,  # Below cold threshold - should be dark blue with snowflake
        40,  # Below cold threshold - should be dark blue with snowflake
        temp_cold_threshold_f - 2,  # Just below cold threshold
        temp_cold_threshold_f,  # At cold threshold (still below, so cold alert)
        temp_cold_threshold_f + 2,  # Just above cold but below regular threshold - light blue
        temp_threshold_f - 3,  # Below regular threshold - light blue
        temp_threshold_f,  # At regular threshold (still below, so alert)
        temp_threshold_f + 10,  # Above threshold - normal
        temp_threshold_f + 20,  # Above threshold - normal
        85  # Well above threshold - normal
    ]

    # Test data for wind alerts (generate around threshold)
    wind_tests = [
        0,
        wind_threshold_mph - 5,
        wind_threshold_mph,
        wind_threshold_mph + 1,
        wind_threshold_mph + 5,
        wind_threshold_mph + 10,
        wind_threshold_mph + 15,
        wind_threshold_mph + 20
    ]

    # Test data for gauge heights
    height_tests = [0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0]

    # Build HTML
    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Visual Indicators Test - USGS River Monitor</title>
<style>
{css}
</style>
</head><body>
<div class="wrap">
  <h1>🧪 Visual Indicators Test Suite</h1>
  <p class="muted">Generated test cases for all color zones and alert conditions</p>

  <div class="note">
    <strong>⚠️ Testing Instructions:</strong><br>
    1. Verify each color matches the expected zone<br>
    2. Check that temperature alerts (&lt; {temp_threshold_f}°F) appear in {temp_alert_color}<br>
    3. Check that wind alerts (&gt; {wind_threshold_mph} mph) appear in {wind_alert_color}<br>
    4. Verify text is readable on all background colors<br>
    5. Compare colors with live dashboard at http://localhost:8080
  </div>

  <!-- Little River Canyon Multi-Level Tests -->
  <div class="test-section">
    <h2>🎨 Little River Canyon - Multi-Level Color Classification</h2>
    <p class="muted">Testing all 6 CFS-based color zones (USGS 02399200)</p>
    <table>
      <thead>
        <tr>
          <td>CFS</td>
          <td>Expected Color</td>
          <td>Zone Description</td>
          <td class="num">Stage (ft)</td>
          <td>CSS Class</td>
        </tr>
      </thead>
      <tbody>
"""

    # Generate Little River test rows
    for cfs, css_class, description in lrc_tests:
        # Fake stage calculation (rough approximation)
        stage_ft = 2.0 + (cfs / 500.0)
        html += f"""        <tr class="{css_class}">
          <td class="center"><strong>{cfs:,}</strong></td>
          <td>{get_color_name(css_class)}</td>
          <td>{description}</td>
          <td class="num">{stage_ft:.2f}</td>
          <td><code>{css_class}</code></td>
        </tr>
"""

    html += """      </tbody>
    </table>
  </div>

  <!-- Temperature Alert Tests -->
  <div class="test-section">
    <h2>🌡️ Temperature Alert Testing</h2>
    <p class="muted">Temperatures below {temp_cold_threshold_f}°F should be highlighted in {temp_cold_alert_color} with snowflake ❄️<br>
    Temperatures {temp_cold_threshold_f}°F-{temp_threshold_f}°F should be highlighted in {temp_alert_color}</p>
    <table>
      <thead>
        <tr>
          <td>Temperature</td>
          <td>Display</td>
          <td>Expected Behavior</td>
        </tr>
      </thead>
      <tbody>
"""

    for temp in temp_tests:
        if temp < temp_cold_threshold_f:
            display = f'❄️ <span class="temp-cold-alert">{temp}°F</span>'
            expected = f"Cold alert with snowflake (&lt; {temp_cold_threshold_f}°F) - {temp_cold_alert_color}"
        elif temp < temp_threshold_f:
            display = f'<span class="temp-alert">{temp}°F</span>'
            expected = f"Cool alert ({temp_cold_threshold_f}°F-{temp_threshold_f}°F) - {temp_alert_color}"
        else:
            display = f"{temp}°F"
            expected = f"Normal text (≥ {temp_threshold_f}°F)"

        html += f"""        <tr class="out">
          <td class="center"><strong>{temp}°F</strong></td>
          <td>{display}</td>
          <td>{expected}</td>
        </tr>
"""

    html += """      </tbody>
    </table>
  </div>

  <!-- Wind Alert Tests -->
  <div class="test-section">
    <h2>💨 Wind Alert Testing</h2>
    <p class="muted">Wind speeds above {wind_threshold_mph} mph should be highlighted in {wind_alert_color}</p>
    <table>
      <thead>
        <tr>
          <td>Wind Speed</td>
          <td>Display</td>
          <td>Expected Behavior</td>
        </tr>
      </thead>
      <tbody>
"""

    for wind in wind_tests:
        if wind > wind_threshold_mph:
            display = f'Wind: <span class="wind-alert">{wind} mph</span> N'
            expected = f"Alert highlight (&gt; {wind_threshold_mph} mph)"
        else:
            display = f"Wind: {wind} mph N"
            expected = f"Normal text (≤ {wind_threshold_mph} mph)"

        html += f"""        <tr class="out">
          <td class="center"><strong>{wind} mph</strong></td>
          <td>{display}</td>
          <td>{expected}</td>
        </tr>
"""

    html += """      </tbody>
    </table>
  </div>

  <!-- Gauge Height Tests -->
  <div class="test-section">
    <h2>📏 Gauge Height Testing</h2>
    <p class="muted">Testing various water levels (standard rivers use binary in/out)</p>
    <table>
      <thead>
        <tr>
          <td>River</td>
          <td>Stage (ft)</td>
          <td>CFS</td>
          <td>Status</td>
        </tr>
      </thead>
      <tbody>
"""

    for height in height_tests:
        # Simulate in/out based on threshold (e.g., 1.7 ft for Locust Fork)
        if height >= 1.70:
            css_class = "in"
            status = "IN - Above threshold"
        else:
            css_class = "out"
            status = "OUT - Below threshold"

        cfs = int(height * 50)  # Fake CFS calculation

        html += f"""        <tr class="{css_class}">
          <td>Locust Fork</td>
          <td class="num">{height:.2f}</td>
          <td class="center">{cfs}</td>
          <td>{status}</td>
        </tr>
"""

    html += """      </tbody>
    </table>
  </div>

  <!-- Combined Conditions Tests -->
  <div class="test-section">
    <h2>🔀 Combined Conditions Testing</h2>
    <p class="muted">Testing multiple alerts simultaneously</p>
    <table>
      <thead>
        <tr>
          <td>Scenario</td>
          <td>Conditions</td>
          <td>Display</td>
        </tr>
      </thead>
      <tbody>
        <tr class="good-high">
          <td>Perfect Day</td>
          <td>High water + warm + calm</td>
          <td>65°F · Wind: 5 mph N</td>
        </tr>
        <tr class="good-high">
          <td>Cold High Water</td>
          <td>High water + cold temp</td>
          <td><span class="temp-alert">45°F</span> · Wind: 8 mph N</td>
        </tr>
        <tr class="good-medium">
          <td>Windy Medium Flow</td>
          <td>Medium water + high wind</td>
          <td>58°F · Wind: <span class="wind-alert">18 mph</span> NW</td>
        </tr>
        <tr class="good-low">
          <td>Cold & Windy Low</td>
          <td>Low water + cold + windy</td>
          <td><span class="temp-alert">50°F</span> · Wind: <span class="wind-alert">22 mph</span> N</td>
        </tr>
        <tr class="too-high">
          <td>Extreme Conditions</td>
          <td>Flood stage + alerts</td>
          <td><span class="temp-alert">42°F</span> · Wind: <span class="wind-alert">25 mph</span> NNW</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Color Legend -->
  <div class="test-section">
    <h2>🎨 Color Legend</h2>
    <table>
      <thead>
        <tr>
          <td>Color Sample</td>
          <td>CSS Class</td>
          <td>Use Case</td>
          <td>Hex/RGB</td>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><span class="legend" style="background:#f6f7f9;"></span> Gray</td>
          <td><code>out</code></td>
          <td>Not runnable / Below threshold</td>
          <td>#f6f7f9</td>
        </tr>
        <tr>
          <td><span class="legend" style="background:#fff9c4;"></span> Yellow</td>
          <td><code>good-low</code></td>
          <td>Little River: 250-400 CFS</td>
          <td>#fff9c4</td>
        </tr>
        <tr>
          <td><span class="legend" style="background:#d4a574;"></span> Brown</td>
          <td><code>shitty-medium</code></td>
          <td>Little River: 400-800 CFS</td>
          <td>#d4a574</td>
        </tr>
        <tr>
          <td><span class="legend" style="background:#c8e6c9;"></span> Light Green</td>
          <td><code>good-medium</code></td>
          <td>Little River: 800-1,500 CFS</td>
          <td>#c8e6c9</td>
        </tr>
        <tr>
          <td><span class="legend" style="background:#b7ff9c;"></span> Green</td>
          <td><code>good-high</code> / <code>in</code></td>
          <td>Best conditions / Above threshold</td>
          <td>#b7ff9c</td>
        </tr>
        <tr>
          <td><span class="legend" style="background:#ffcdd2;"></span> Red</td>
          <td><code>too-high</code></td>
          <td>Little River: 2,500+ CFS</td>
          <td>#ffcdd2</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="note" style="margin-top:32px;">
    <strong>✅ Test Checklist:</strong><br>
    □ All 6 Little River color zones display correctly<br>
    □ Temperature &lt; {temp_threshold_f}°F shows {temp_alert_color}<br>
    □ Wind &gt; {wind_threshold_mph} mph shows {wind_alert_color}<br>
    □ Text is readable on all backgrounds<br>
    □ Colors match the live dashboard<br>
    □ Mobile view looks correct (resize window)
  </div>

  <p class="muted" style="text-align:center; margin-top:32px; padding:16px; border-top:1px solid #ddd;">
    Generated by test_visual_indicators.py •
    <a href="http://localhost:8080" target="_blank">View Live Dashboard</a>
  </p>
</div>
</body></html>
"""

    return html


def get_color_name(css_class):
    """Get human-readable color name for CSS class"""
    colors = {
        "out": "Gray",
        "good-low": "Yellow",
        "shitty-medium": "Brown",
        "good-medium": "Light Green",
        "good-high": "Green (Best!)",
        "too-high": "Red",
        "in": "Green"
    }
    return colors.get(css_class, css_class)


if __name__ == "__main__":
    print("🧪 Generating visual indicators test file...")

    # Load config file to get visual indicators settings
    config_path = sys.argv[1] if len(sys.argv) > 1 else "gauges.conf.json"
    try:
        with open(config_path, "r") as f:
            cfg = json.load(f)
        visual_indicators = cfg.get("visual_indicators", {})
        wind_threshold_mph = float(visual_indicators.get("wind_threshold_mph", 10))
        wind_alert_color = visual_indicators.get("wind_alert_color", "#ffc107")
        temp_threshold_f = float(visual_indicators.get("temp_threshold_f", 55))
        temp_alert_color = visual_indicators.get("temp_alert_color", "#add8e6")
        temp_cold_threshold_f = float(visual_indicators.get("temp_cold_threshold_f", 45))
        temp_cold_alert_color = visual_indicators.get("temp_cold_alert_color", "#1e90ff")
        print(f"   Using config: {config_path}")
        print(f"   Wind threshold: {wind_threshold_mph} mph ({wind_alert_color})")
        print(f"   Temp thresholds: < {temp_cold_threshold_f}°F ({temp_cold_alert_color}), < {temp_threshold_f}°F ({temp_alert_color})")
    except FileNotFoundError:
        print(f"   Warning: Config file '{config_path}' not found, using defaults")
        wind_threshold_mph = 10
        wind_alert_color = "#ffc107"
        temp_threshold_f = 55
        temp_alert_color = "#add8e6"
        temp_cold_threshold_f = 45
        temp_cold_alert_color = "#1e90ff"
    except Exception as e:
        print(f"   Warning: Error reading config: {e}, using defaults")
        wind_threshold_mph = 10
        wind_alert_color = "#ffc107"
        temp_threshold_f = 55
        temp_alert_color = "#add8e6"
        temp_cold_threshold_f = 45
        temp_cold_alert_color = "#1e90ff"

    html = generate_test_html(wind_threshold_mph, wind_alert_color, temp_threshold_f, temp_alert_color, temp_cold_threshold_f, temp_cold_alert_color)

    # Determine output directory - use script's directory by default
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "test_visual_indicators.html")

    with open(output_file, "w") as f:
        f.write(html)

    print(f"✅ Test file generated: {output_file}")
    print(f"\n📋 To view the tests:")
    print(f"   1. Open in browser: file://{output_file}")
    print(f"   2. Or run: xdg-open {output_file}")
    print(f"   3. Or run from project dir: python3 -m http.server 8080")
    print(f"      Then visit: http://localhost:8080/test_visual_indicators.html")
    print(f"\n🔍 What to look for:")
    print(f"   • Little River: 6 distinct color zones from gray→yellow→brown→light green→green→red")
    print(f"   • Temperatures < {temp_cold_threshold_f}°F should be {temp_cold_alert_color} with ❄️ snowflake")
    print(f"   • Temperatures {temp_cold_threshold_f}-{temp_threshold_f}°F should be {temp_alert_color}")
    print(f"   • Wind > {wind_threshold_mph} mph should be {wind_alert_color}")
    print(f"   • All text should be readable on colored backgrounds")
    print(f"   • Compare side-by-side with live dashboard at http://localhost:8080")

    import os
    print(f"\n🚀 Quick start: xdg-open {output_file}")

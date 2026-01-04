#!/usr/bin/env python3
"""
Ocoee Dam Cascade Correlation Page Generator

Creates visualization pages showing the relationship between all 3 Ocoee dams
as water cascades downstream: #3 (Upper) -> #2 (Middle) -> #1 (Lower/Parksville)

Dam positions (top to bottom of mountain):
- OCCT1: Ocoee #3 (Upper Dam) - top of the mountain
- OCBT1: Ocoee #2 (Middle Dam) - main whitewater put-in
- OCAT1: Ocoee #1 (Lower/Parksville Dam) - bottom

Features:
- View 1: Overlapping lines (all 3 dams on one chart)
- View 2: Multi-panel synced (3 stacked charts, synced x-axis)
- View 3: Full metrics (CFS + pool + tailwater with dual y-axes)
"""

import html
from typing import Dict, Any, Optional

# Ocoee site configuration with colors
OCOEE_SITES = {
    "OCCT1": {
        "name": "Ocoee #3 (Upper)",
        "short_name": "Upper (#3)",
        "position": 1,
        "color": "#ef4444",      # Red
        "color_light": "#fecaca",
        "description": "Top of mountain - water starts here"
    },
    "OCBT1": {
        "name": "Ocoee #2 (Middle)",
        "short_name": "Middle (#2)",
        "position": 2,
        "color": "#eab308",      # Yellow
        "color_light": "#fef08a",
        "description": "Middle section - main whitewater put-in"
    },
    "OCAT1": {
        "name": "Ocoee #1 (Lower)",
        "short_name": "Lower (#1)",
        "position": 3,
        "color": "#22c55e",      # Green
        "color_light": "#bbf7d0",
        "description": "Bottom of mountain - Parksville Dam"
    }
}


def generate_ocoee_cascade_html(current_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate the main Ocoee cascade correlation page with 3 view tabs.

    Args:
        current_data: Dict with current observations for each site
            {
                "OCCT1": {"discharge_cfs": N, "pool_elevation_ft": N, "tailwater_ft": N},
                "OCBT1": {...},
                "OCAT1": {...}
            }

    Returns:
        Complete HTML string for the correlation page
    """
    h = html.escape

    # Build current status cards
    status_cards_html = ""
    for site_code, config in OCOEE_SITES.items():
        data = (current_data or {}).get(site_code, {})
        cfs = data.get("discharge_cfs", 0) or 0
        pool = data.get("pool_elevation_ft", 0) or 0
        tailwater = data.get("tailwater_ft", 0) or 0

        # Determine status
        threshold = 1000  # Default threshold for Ocoee
        if cfs >= threshold:
            status = "RUNNING"
            status_color = config["color"]
        elif cfs >= threshold * 0.5:
            status = "GETTING CLOSE"
            status_color = "#eab308"
        else:
            status = "LOW"
            status_color = "#9ca3af"

        status_cards_html += f'''
        <div class="status-card dam-{config["position"]}">
          <div class="card-header" style="border-top: 4px solid {config["color"]};">
            <span class="card-position">#{config["position"]}</span>
            <span class="card-title">{h(config["short_name"])}</span>
          </div>
          <div class="card-cfs" style="color: {status_color};">{cfs:,}</div>
          <div class="card-unit">CFS</div>
          <div class="card-status" style="background: {status_color};">{status}</div>
          <div class="card-details">
            <span>Pool: {pool:.1f} ft</span>
            <span>Tail: {tailwater:.1f} ft</span>
          </div>
        </div>
        '''

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ocoee Dam Cascade Correlation</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  background: #f5f5f5;
  padding: 20px;
}}
.container {{ max-width: 1400px; margin: 0 auto; }}

.back-link {{
  display: inline-block;
  margin-bottom: 16px;
  color: #1a73e8;
  text-decoration: none;
  font-size: 14px;
}}
.back-link:hover {{ text-decoration: underline; }}

.cascade-header {{
  background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  color: white;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}}
.cascade-title {{
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}}
.cascade-subtitle {{
  font-size: 14px;
  opacity: 0.8;
  margin-bottom: 16px;
}}
.cascade-flow {{
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(255,255,255,0.1);
  border-radius: 8px;
  font-size: 14px;
}}
.flow-dam {{
  padding: 6px 12px;
  border-radius: 16px;
  font-weight: bold;
}}
.flow-arrow {{
  color: #60a5fa;
  font-size: 20px;
}}

.view-tabs {{
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 20px;
}}
.view-tab {{
  padding: 12px 24px;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 24px;
  color: #374151;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}}
.view-tab:hover {{
  background: #f3f4f6;
  border-color: #3b82f6;
}}
.view-tab.active {{
  background: #3b82f6;
  border-color: #3b82f6;
  color: white;
}}

.status-cards {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}}
.status-card {{
  background: white;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}}
.card-header {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-top: 8px;
}}
.card-position {{
  font-size: 12px;
  font-weight: bold;
  color: #6b7280;
}}
.card-title {{
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}}
.card-cfs {{
  font-size: 36px;
  font-weight: bold;
  line-height: 1;
}}
.card-unit {{
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 8px;
}}
.card-status {{
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  color: white;
  margin-bottom: 8px;
}}
.card-details {{
  display: flex;
  justify-content: center;
  gap: 16px;
  font-size: 12px;
  color: #6b7280;
}}

.chart-section {{
  background: linear-gradient(135deg, #1a2f4a 0%, #243b55 100%);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  color: white;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}}
.chart-header {{
  text-align: center;
  margin-bottom: 20px;
}}
.chart-title {{
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 4px;
}}
.chart-subtitle {{
  font-size: 13px;
  opacity: 0.7;
}}

.time-controls {{
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 20px;
}}
.range-btn {{
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
}}
.range-btn:hover {{
  background: rgba(255,255,255,0.2);
}}
.range-btn.active {{
  background: #3b82f6;
  border-color: #3b82f6;
  font-weight: bold;
}}

.chart-container {{
  background: rgba(255,255,255,0.95);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}}
.chart-container.single {{ height: 400px; }}
.chart-container.multi {{ height: 250px; margin-bottom: 12px; }}
.chart-container.full {{ height: 500px; }}

.chart-legend {{
  display: flex;
  justify-content: center;
  gap: 24px;
  flex-wrap: wrap;
  margin-top: 12px;
}}
.legend-item {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}}
.legend-color {{
  width: 20px;
  height: 4px;
  border-radius: 2px;
}}
.legend-color.dashed {{
  background: repeating-linear-gradient(
    to right,
    currentColor,
    currentColor 4px,
    transparent 4px,
    transparent 8px
  );
  height: 3px;
}}

.stats-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}}
.stat-card {{
  background: rgba(0,0,0,0.3);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}}
.stat-label {{
  font-size: 11px;
  text-transform: uppercase;
  opacity: 0.7;
  margin-bottom: 4px;
}}
.stat-value {{
  font-size: 18px;
  font-weight: bold;
  color: #60a5fa;
}}

.view-content {{ display: none; }}
.view-content.active {{ display: block; }}

.dam-links {{
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 20px;
}}
.dam-link {{
  padding: 12px 24px;
  background: white;
  border-radius: 24px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transition: all 0.2s;
}}
.dam-link:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}

@media (max-width: 768px) {{
  .status-cards {{ grid-template-columns: 1fr; }}
  .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .cascade-flow {{ flex-direction: column; }}
  .view-tabs {{ flex-wrap: wrap; }}
  .dam-links {{ flex-direction: column; align-items: center; }}
}}
</style>
</head>
<body>
<div class="container">
  <a href="/" class="back-link">&larr; Back to All Rivers</a>

  <div class="cascade-header">
    <div class="cascade-title">Ocoee Dam Cascade Correlation</div>
    <div class="cascade-subtitle">See how water flows from Upper to Lower Ocoee during heavy rain or releases</div>
    <div class="cascade-flow">
      <span class="flow-dam" style="background: {OCOEE_SITES["OCCT1"]["color"]};">Upper #3</span>
      <span class="flow-arrow">&rarr;</span>
      <span class="flow-dam" style="background: {OCOEE_SITES["OCBT1"]["color"]};">Middle #2</span>
      <span class="flow-arrow">&rarr;</span>
      <span class="flow-dam" style="background: {OCOEE_SITES["OCAT1"]["color"]};">Lower #1</span>
    </div>
  </div>

  <div class="view-tabs">
    <button class="view-tab active" data-view="overlapping">Overlapping Lines</button>
    <button class="view-tab" data-view="multipanel">Multi-Panel Synced</button>
    <button class="view-tab" data-view="fullmetrics">Full Metrics</button>
  </div>

  <div class="status-cards">
    {status_cards_html}
  </div>

  <!-- View 1: Overlapping Lines -->
  <div class="view-content active" id="view-overlapping">
    <div class="chart-section">
      <div class="chart-header">
        <div class="chart-title">Discharge Comparison (All 3 Dams)</div>
        <div class="chart-subtitle">See when upstream spikes cascade downstream</div>
      </div>
      <div class="time-controls">
        <button class="range-btn active" data-days="7">7 Days</button>
        <button class="range-btn" data-days="30">30 Days</button>
        <button class="range-btn" data-days="90">90 Days</button>
        <button class="range-btn" data-days="365">1 Year</button>
      </div>
      <div class="stats-grid" id="stats-overlapping">
        <div class="stat-card"><div class="stat-label">Upper Max</div><div class="stat-value" id="stat-upper-max">--</div></div>
        <div class="stat-card"><div class="stat-label">Middle Max</div><div class="stat-value" id="stat-middle-max">--</div></div>
        <div class="stat-card"><div class="stat-label">Lower Max</div><div class="stat-value" id="stat-lower-max">--</div></div>
        <div class="stat-card"><div class="stat-label">Data Points</div><div class="stat-value" id="stat-count">--</div></div>
      </div>
      <div class="chart-container single">
        <canvas id="chart-overlapping"></canvas>
      </div>
      <div class="chart-legend">
        <div class="legend-item"><span class="legend-color" style="background: {OCOEE_SITES["OCCT1"]["color"]};"></span>Upper #3 (OCCT1)</div>
        <div class="legend-item"><span class="legend-color" style="background: {OCOEE_SITES["OCBT1"]["color"]};"></span>Middle #2 (OCBT1)</div>
        <div class="legend-item"><span class="legend-color" style="background: {OCOEE_SITES["OCAT1"]["color"]};"></span>Lower #1 (OCAT1)</div>
      </div>
    </div>
  </div>

  <!-- View 2: Multi-Panel Synced -->
  <div class="view-content" id="view-multipanel">
    <div class="chart-section">
      <div class="chart-header">
        <div class="chart-title">Multi-Panel View (Synced Time Axis)</div>
        <div class="chart-subtitle">Each dam on its own chart for clearer comparison</div>
      </div>
      <div class="time-controls">
        <button class="range-btn active" data-days="7">7 Days</button>
        <button class="range-btn" data-days="30">30 Days</button>
        <button class="range-btn" data-days="90">90 Days</button>
        <button class="range-btn" data-days="365">1 Year</button>
      </div>
      <div class="chart-container multi" style="border-left: 4px solid {OCOEE_SITES["OCCT1"]["color"]};">
        <canvas id="chart-panel-upper"></canvas>
      </div>
      <div class="chart-container multi" style="border-left: 4px solid {OCOEE_SITES["OCBT1"]["color"]};">
        <canvas id="chart-panel-middle"></canvas>
      </div>
      <div class="chart-container multi" style="border-left: 4px solid {OCOEE_SITES["OCAT1"]["color"]};">
        <canvas id="chart-panel-lower"></canvas>
      </div>
    </div>
  </div>

  <!-- View 3: Full Metrics -->
  <div class="view-content" id="view-fullmetrics">
    <div class="chart-section">
      <div class="chart-header">
        <div class="chart-title">Full Metrics (CFS + Pool + Tailwater)</div>
        <div class="chart-subtitle">Complete picture of dam operations - see when lakes fill before spilling</div>
      </div>
      <div class="time-controls">
        <button class="range-btn active" data-days="7">7 Days</button>
        <button class="range-btn" data-days="30">30 Days</button>
        <button class="range-btn" data-days="90">90 Days</button>
        <button class="range-btn" data-days="365">1 Year</button>
      </div>
      <div class="stats-grid" id="stats-fullmetrics">
        <div class="stat-card"><div class="stat-label">Upper Max Pool</div><div class="stat-value" id="stat-upper-pool">--</div></div>
        <div class="stat-card"><div class="stat-label">Middle Max Pool</div><div class="stat-value" id="stat-middle-pool">--</div></div>
        <div class="stat-card"><div class="stat-label">Lower Max Pool</div><div class="stat-value" id="stat-lower-pool">--</div></div>
        <div class="stat-card"><div class="stat-label">Observations</div><div class="stat-value" id="stat-obs-count">--</div></div>
      </div>
      <div class="chart-container full">
        <canvas id="chart-fullmetrics"></canvas>
      </div>
      <div class="chart-legend">
        <div class="legend-item"><span class="legend-color" style="background: {OCOEE_SITES["OCCT1"]["color"]};"></span>Upper CFS</div>
        <div class="legend-item"><span class="legend-color" style="background: {OCOEE_SITES["OCBT1"]["color"]};"></span>Middle CFS</div>
        <div class="legend-item"><span class="legend-color" style="background: {OCOEE_SITES["OCAT1"]["color"]};"></span>Lower CFS</div>
        <div class="legend-item"><span class="legend-color dashed" style="color: {OCOEE_SITES["OCCT1"]["color"]};"></span>Upper Pool (ft)</div>
        <div class="legend-item"><span class="legend-color dashed" style="color: {OCOEE_SITES["OCBT1"]["color"]};"></span>Middle Pool (ft)</div>
        <div class="legend-item"><span class="legend-color dashed" style="color: {OCOEE_SITES["OCAT1"]["color"]};"></span>Lower Pool (ft)</div>
      </div>
    </div>
  </div>

  <div class="dam-links">
    <a href="OCCT1.html" class="dam-link" style="border-left: 4px solid {OCOEE_SITES["OCCT1"]["color"]};">Ocoee #3 (Upper) Details</a>
    <a href="OCBT1.html" class="dam-link" style="border-left: 4px solid {OCOEE_SITES["OCBT1"]["color"]};">Ocoee #2 (Middle) Details</a>
    <a href="OCAT1.html" class="dam-link" style="border-left: 4px solid {OCOEE_SITES["OCAT1"]["color"]};">Ocoee #1 (Lower) Details</a>
  </div>
</div>

<script>
(function() {{
  // Chart instances
  let chartOverlapping = null;
  let chartPanelUpper = null;
  let chartPanelMiddle = null;
  let chartPanelLower = null;
  let chartFullMetrics = null;

  // Site colors
  const COLORS = {{
    OCCT1: {{ main: '{OCOEE_SITES["OCCT1"]["color"]}', light: '{OCOEE_SITES["OCCT1"]["color_light"]}' }},
    OCBT1: {{ main: '{OCOEE_SITES["OCBT1"]["color"]}', light: '{OCOEE_SITES["OCBT1"]["color_light"]}' }},
    OCAT1: {{ main: '{OCOEE_SITES["OCAT1"]["color"]}', light: '{OCOEE_SITES["OCAT1"]["color_light"]}' }}
  }};

  // Fetch combined data
  async function fetchData(days) {{
    try {{
      const response = await fetch(`/api/tva-history/ocoee/combined?days=${{days}}`);
      return await response.json();
    }} catch (err) {{
      console.error('Failed to fetch data:', err);
      return null;
    }}
  }}

  // Format timestamp for labels
  function formatLabel(ts, days) {{
    const d = new Date(ts);
    if (days <= 7) {{
      return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric', hour: 'numeric' }});
    }} else {{
      return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }});
    }}
  }}

  // Get common timestamps from all sites
  function getCommonLabels(data, days) {{
    const occt1 = data.sites?.OCCT1?.observations || [];
    return occt1.map(o => formatLabel(o.timestamp, days));
  }}

  // Update overlapping chart
  function updateOverlappingChart(data, days) {{
    const ctx = document.getElementById('chart-overlapping').getContext('2d');

    if (chartOverlapping) chartOverlapping.destroy();

    const sites = data.sites || {{}};
    const labels = getCommonLabels(data, days);

    // Update stats
    if (sites.OCCT1?.stats?.discharge_cfs?.max) {{
      document.getElementById('stat-upper-max').textContent = sites.OCCT1.stats.discharge_cfs.max.toLocaleString() + ' CFS';
    }}
    if (sites.OCBT1?.stats?.discharge_cfs?.max) {{
      document.getElementById('stat-middle-max').textContent = sites.OCBT1.stats.discharge_cfs.max.toLocaleString() + ' CFS';
    }}
    if (sites.OCAT1?.stats?.discharge_cfs?.max) {{
      document.getElementById('stat-lower-max').textContent = sites.OCAT1.stats.discharge_cfs.max.toLocaleString() + ' CFS';
    }}
    const totalCount = (sites.OCCT1?.observation_count || 0) + (sites.OCBT1?.observation_count || 0) + (sites.OCAT1?.observation_count || 0);
    document.getElementById('stat-count').textContent = totalCount.toLocaleString();

    chartOverlapping = new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [
          {{
            label: 'Upper #3',
            data: (sites.OCCT1?.observations || []).map(o => o.discharge_cfs),
            borderColor: COLORS.OCCT1.main,
            backgroundColor: COLORS.OCCT1.light + '40',
            borderWidth: 2,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4
          }},
          {{
            label: 'Middle #2',
            data: (sites.OCBT1?.observations || []).map(o => o.discharge_cfs),
            borderColor: COLORS.OCBT1.main,
            backgroundColor: COLORS.OCBT1.light + '40',
            borderWidth: 2,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4
          }},
          {{
            label: 'Lower #1',
            data: (sites.OCAT1?.observations || []).map(o => o.discharge_cfs),
            borderColor: COLORS.OCAT1.main,
            backgroundColor: COLORS.OCAT1.light + '40',
            borderWidth: 2,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(0,0,0,0.8)',
            callbacks: {{
              label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString() + ' CFS'
            }}
          }}
        }},
        scales: {{
          x: {{ ticks: {{ maxRotation: 45, autoSkip: true, maxTicksLimit: 12 }}, grid: {{ display: false }} }},
          y: {{ beginAtZero: true, title: {{ display: true, text: 'Discharge (CFS)' }} }}
        }}
      }}
    }});
  }}

  // Update multi-panel charts
  function updateMultiPanelCharts(data, days) {{
    const sites = data.sites || {{}};
    const labels = getCommonLabels(data, days);

    const panelConfig = [
      {{ id: 'chart-panel-upper', site: 'OCCT1', name: 'Upper #3', color: COLORS.OCCT1 }},
      {{ id: 'chart-panel-middle', site: 'OCBT1', name: 'Middle #2', color: COLORS.OCBT1 }},
      {{ id: 'chart-panel-lower', site: 'OCAT1', name: 'Lower #1', color: COLORS.OCAT1 }}
    ];

    // Destroy existing charts
    if (chartPanelUpper) chartPanelUpper.destroy();
    if (chartPanelMiddle) chartPanelMiddle.destroy();
    if (chartPanelLower) chartPanelLower.destroy();

    const charts = [];
    panelConfig.forEach((cfg, idx) => {{
      const ctx = document.getElementById(cfg.id).getContext('2d');
      const siteData = sites[cfg.site]?.observations || [];

      const chart = new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: labels,
          datasets: [{{
            label: cfg.name,
            data: siteData.map(o => o.discharge_cfs),
            borderColor: cfg.color.main,
            backgroundColor: cfg.color.light + '40',
            borderWidth: 2,
            fill: true,
            tension: 0.3,
            pointRadius: 0
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ display: true, position: 'top', align: 'start' }},
            tooltip: {{ callbacks: {{ label: ctx => ctx.parsed.y.toLocaleString() + ' CFS' }} }}
          }},
          scales: {{
            x: {{ display: idx === 2, ticks: {{ maxRotation: 45, autoSkip: true, maxTicksLimit: 12 }}, grid: {{ display: false }} }},
            y: {{ beginAtZero: true, title: {{ display: true, text: 'CFS' }} }}
          }}
        }}
      }});
      charts.push(chart);
    }});

    [chartPanelUpper, chartPanelMiddle, chartPanelLower] = charts;
  }}

  // Update full metrics chart
  function updateFullMetricsChart(data, days) {{
    const ctx = document.getElementById('chart-fullmetrics').getContext('2d');

    if (chartFullMetrics) chartFullMetrics.destroy();

    const sites = data.sites || {{}};
    const labels = getCommonLabels(data, days);

    // Update stats
    if (sites.OCCT1?.stats?.pool_elevation_ft?.max) {{
      document.getElementById('stat-upper-pool').textContent = sites.OCCT1.stats.pool_elevation_ft.max.toFixed(1) + ' ft';
    }}
    if (sites.OCBT1?.stats?.pool_elevation_ft?.max) {{
      document.getElementById('stat-middle-pool').textContent = sites.OCBT1.stats.pool_elevation_ft.max.toFixed(1) + ' ft';
    }}
    if (sites.OCAT1?.stats?.pool_elevation_ft?.max) {{
      document.getElementById('stat-lower-pool').textContent = sites.OCAT1.stats.pool_elevation_ft.max.toFixed(1) + ' ft';
    }}
    const totalCount = (sites.OCCT1?.observation_count || 0) + (sites.OCBT1?.observation_count || 0) + (sites.OCAT1?.observation_count || 0);
    document.getElementById('stat-obs-count').textContent = totalCount.toLocaleString();

    chartFullMetrics = new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [
          // CFS lines (solid)
          {{
            label: 'Upper CFS',
            data: (sites.OCCT1?.observations || []).map(o => o.discharge_cfs),
            borderColor: COLORS.OCCT1.main,
            borderWidth: 2,
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            yAxisID: 'yCfs'
          }},
          {{
            label: 'Middle CFS',
            data: (sites.OCBT1?.observations || []).map(o => o.discharge_cfs),
            borderColor: COLORS.OCBT1.main,
            borderWidth: 2,
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            yAxisID: 'yCfs'
          }},
          {{
            label: 'Lower CFS',
            data: (sites.OCAT1?.observations || []).map(o => o.discharge_cfs),
            borderColor: COLORS.OCAT1.main,
            borderWidth: 2,
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            yAxisID: 'yCfs'
          }},
          // Pool elevation lines (dashed)
          {{
            label: 'Upper Pool',
            data: (sites.OCCT1?.observations || []).map(o => o.pool_elevation_ft),
            borderColor: COLORS.OCCT1.main,
            borderWidth: 2,
            borderDash: [5, 5],
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            yAxisID: 'yFt'
          }},
          {{
            label: 'Middle Pool',
            data: (sites.OCBT1?.observations || []).map(o => o.pool_elevation_ft),
            borderColor: COLORS.OCBT1.main,
            borderWidth: 2,
            borderDash: [5, 5],
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            yAxisID: 'yFt'
          }},
          {{
            label: 'Lower Pool',
            data: (sites.OCAT1?.observations || []).map(o => o.pool_elevation_ft),
            borderColor: COLORS.OCAT1.main,
            borderWidth: 2,
            borderDash: [5, 5],
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            yAxisID: 'yFt'
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(0,0,0,0.8)',
            callbacks: {{
              label: function(ctx) {{
                const val = ctx.parsed.y;
                if (ctx.dataset.label.includes('CFS')) {{
                  return ctx.dataset.label + ': ' + val.toLocaleString() + ' CFS';
                }} else {{
                  return ctx.dataset.label + ': ' + val.toFixed(1) + ' ft';
                }}
              }}
            }}
          }}
        }},
        scales: {{
          x: {{ ticks: {{ maxRotation: 45, autoSkip: true, maxTicksLimit: 12 }}, grid: {{ display: false }} }},
          yCfs: {{
            type: 'linear',
            display: true,
            position: 'left',
            title: {{ display: true, text: 'Discharge (CFS)', color: '#ef4444' }},
            ticks: {{ color: '#ef4444' }},
            grid: {{ color: 'rgba(239, 68, 68, 0.1)' }}
          }},
          yFt: {{
            type: 'linear',
            display: true,
            position: 'right',
            title: {{ display: true, text: 'Pool Elevation (ft)', color: '#3b82f6' }},
            ticks: {{ color: '#3b82f6' }},
            grid: {{ drawOnChartArea: false }}
          }}
        }}
      }}
    }});
  }}

  // Load data and update all charts
  async function loadAndUpdate(days) {{
    const data = await fetchData(days);
    if (!data) return;

    updateOverlappingChart(data, days);
    updateMultiPanelCharts(data, days);
    updateFullMetricsChart(data, days);
  }}

  // View tab switching
  document.querySelectorAll('.view-tab').forEach(tab => {{
    tab.addEventListener('click', function() {{
      document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));

      this.classList.add('active');
      document.getElementById('view-' + this.dataset.view).classList.add('active');
    }});
  }});

  // Time range buttons
  document.querySelectorAll('.time-controls').forEach(controls => {{
    controls.querySelectorAll('.range-btn').forEach(btn => {{
      btn.addEventListener('click', function() {{
        // Update active state in this control group
        this.parentElement.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');

        // Load new data
        loadAndUpdate(parseInt(this.dataset.days));
      }});
    }});
  }});

  // Initial load
  loadAndUpdate(7);
}})();
</script>
</body>
</html>'''

    return html_content


if __name__ == "__main__":
    # Test generation
    print("Testing Ocoee cascade page generation...")

    test_data = {
        "OCCT1": {"discharge_cfs": 1200, "pool_elevation_ft": 1520.5, "tailwater_ft": 1480.2},
        "OCBT1": {"discharge_cfs": 1100, "pool_elevation_ft": 1435.3, "tailwater_ft": 1410.1},
        "OCAT1": {"discharge_cfs": 950, "pool_elevation_ft": 830.8, "tailwater_ft": 780.5}
    }

    html = generate_ocoee_cascade_html(test_data)

    with open("test_ocoee_cascade.html", "w") as f:
        f.write(html)

    print(f"Generated test_ocoee_cascade.html ({len(html)} bytes)")

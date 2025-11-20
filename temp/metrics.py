"""Prometheus metrics helpers and Flask endpoint wiring."""
from __future__ import annotations

from time import time
from contextlib import contextmanager
from typing import Iterator, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CONTENT_TYPE_LATEST,
    generate_latest,
)

# --- Metric objects ---
FETCH_TOTAL = Counter("fetch_total", "Total fetch attempts", ["source"])
FETCH_ERRORS_TOTAL = Counter("fetch_errors_total", "Total fetch errors", ["source"])
FETCH_LATENCY = Histogram("fetch_latency_seconds", "Fetch latency seconds", ["source"])

GAUGE_READING = Gauge("river_reading_cfs", "Latest reading (CFS) per gauge", ["gauge_id", "name"])
GAUGE_FRESHNESS = Gauge(
    "river_reading_timestamp_seconds", "Last reading timestamp (unix seconds)", ["gauge_id", "name"]
)

def register_metrics_endpoint(app) -> None:
    """Add /metrics endpoint to a Flask app."""
    @app.get("/metrics")
    def _metrics():
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

@contextmanager
def record_fetch(source: str):
    """Context manager to time+count a fetch block.

    Example:
        with record_fetch("usgs"):
            data = fetch_usgs(...)
    """
    FETCH_TOTAL.labels(source=source).inc()
    start = time()
    try:
        yield
    except Exception:
        FETCH_ERRORS_TOTAL.labels(source=source).inc()
        raise
    finally:
        FETCH_LATENCY.labels(source=source).observe(time() - start)

def update_gauge_metrics(gauge_id: str, name: str, cfs: Optional[float], ts: Optional[float]) -> None:
    if cfs is not None:
        GAUGE_READING.labels(gauge_id=gauge_id, name=name).set(cfs)
    if ts is not None:
        GAUGE_FRESHNESS.labels(gauge_id=gauge_id, name=name).set(ts)

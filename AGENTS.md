# Repository Guidelines

## Project Structure & Module Organization
- `usgs_multi_alert.py` orchestrates gauge polling, alerting, and static site publishing; it reads thresholds from `gauges.conf*.json`.
- `qpf.py` and `observations.py` fetch forecast precipitation and live weather; keep the required NWS User-Agent and contact info current.
- `site_detail.py` builds optional Chart.js dashboards; keep its functions import-safe.
- `entrypoint.sh` drives the container image, looping the alert job and serving `/site`; runtime state lives in `/data`.
- Configs live in `gauges.conf*.json`, state in `usgs-data/state.sqlite`, and generated assets under `usgs-site/`.
- Deployment files `Containerfile.cloud` and `fly.toml` define the Fly.io build; add automated tests under `test/`.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate` prepares an isolated env (install `requests` + `python-dateutil`).
- `python3 usgs_multi_alert.py --config gauges.conf.json --cfs --dump-json usgs-site/gauges.json --dump-html usgs-site/index.html --trend-hours 8` runs the pipeline locally.
- `python3 qpf.py --lat 34.1736 --lon -85.6164 --days 3 --ua "$NWS_UA" --email "$NWS_CONTACT"` validates rainfall forecasts.
- `python3 observations.py` confirms NOAA station access; run after adding or renaming stations.
- `podman build -f Containerfile.cloud -t usgs-alert .` followed by `podman run --rm -p 8080:8080 -v "$PWD/usgs-data:/data" usgs-alert` reproduces the production container loop.

## Coding Style & Naming Conventions
- Follow PEP 8: 4-space indents, snake_case for functions/modules, UpperCamelCase for classes, and uppercase module constants.
- Keep CLI flags and log strings concise and imperative; update argparse help alongside new functionality.

## Testing Guidelines
- Use `pytest` within `test/` using the `test_*.py` pattern; import modules rather than shelling out so scripts remain import-safe.
- Mock HTTP calls to USGS/NWS/NOAA (e.g., with `responses` or `pytest-httpserver`) to keep tests deterministic.
- For manual smoke checks, bind-mount `usgs-data/` and confirm `usgs-site/index.html` and `gauges.json` reflect expected thresholds.

## Commit & Pull Request Guidelines
- Adopt Conventional Commits (`feat:`, `fix:`, `docs:`, etc.) with ≤72-character subjects and optional wrapped bodies.
- PR descriptions should cover behavior changes, config migrations, deployment steps, and include updated HTML screenshots when applicable.
- Link related issues or alert tickets, verify secrets stay out of diffs, and call out any required follow-up tasks.

## Security & Configuration Tips
- Never commit real SMTP credentials; pass `SMTP_USER`, `SMTP_PASS`, and `SMTP_TO` via environment variables and avoid logging secrets.
- Set `NWS_UA`, `NWS_CONTACT`, and `QPF_CACHE` before calling NWS APIs to satisfy usage policies and control cache placement.
- Ensure `/data` persists between runs so alert cooldown and QPF cache data survive restarts.

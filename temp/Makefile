.PHONY: dev lint test container run

PY ?= python3

dev:
	$(PY) -m http.server 8080

lint:
	ruff check .
	black --check --line-length 100 .
	mypy --ignore-missing-imports

test:
	pytest -q || true

container:
	docker build -t usgs-alert:dev .

run:
	$(PY) usgs_multi_alert.py

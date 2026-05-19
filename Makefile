.PHONY: help install install-dev test test-cov smoke verify readiness demo lint format type-check clean-smoke secret-scan

PYTHON ?= python3

help:
	@printf 'AffiliPilot commands:\n'
	@printf '  make install       Install package in editable mode\n'
	@printf '  make install-dev   Install with dev + browser extras\n'
	@printf '  make test          Run pytest (quiet)\n'
	@printf '  make test-cov      Run pytest with coverage report\n'
	@printf '  make smoke         Run deterministic happy-path smoke\n'
	@printf '  make verify        Compile + tests + smoke + secret scan\n'
	@printf '  make readiness     Show readiness gates\n'
	@printf '  make demo          Run demo-happy-path directly\n'
	@printf '  make lint          Run ruff linter\n'
	@printf '  make format        Auto-format with ruff\n'
	@printf '  make type-check    Run mypy\n'
	@printf '  make secret-scan   Scan source/docs/data for obvious secrets\n'
	@printf '  make clean-smoke   Remove smoke output artifacts\n'

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev,browser]"

test:
	PYTHONPATH=. $(PYTHON) -m pytest -q

test-cov:
	PYTHONPATH=. $(PYTHON) -m pytest --cov=affilipilot --cov-report=term-missing --cov-report=html

smoke:
	scripts/smoke_affilipilot.sh

verify:
	scripts/verify_all.sh

readiness:
	PYTHONPATH=. $(PYTHON) -m affilipilot readiness

demo:
	PYTHONPATH=. $(PYTHON) -m affilipilot demo-happy-path

lint:
	$(PYTHON) -m ruff check affilipilot tests

format:
	$(PYTHON) -m ruff format affilipilot tests
	$(PYTHON) -m ruff check --fix affilipilot tests

type-check:
	$(PYTHON) -m mypy affilipilot

secret-scan:
	$(PYTHON) scripts/secret_scan.py

clean-smoke:
	rm -rf data/smoke-happy-path data/smoke-happy-path.db data/demo-happy-path data/demo-happy-path.db htmlcov .coverage

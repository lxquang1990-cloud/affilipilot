.PHONY: help test smoke verify readiness demo clean-smoke secret-scan

PYTHON ?= python3

help:
	@printf 'AffiliPilot commands:\n'
	@printf '  make test         Run pytest\n'
	@printf '  make smoke        Run deterministic happy-path smoke\n'
	@printf '  make verify       Compile + tests + smoke + secret scan\n'
	@printf '  make readiness    Show readiness gates\n'
	@printf '  make demo         Run demo-happy-path directly\n'
	@printf '  make secret-scan  Scan source/docs/data for obvious secrets\n'
	@printf '  make clean-smoke  Remove smoke output artifacts\n'

test:
	PYTHONPATH=. $(PYTHON) -m pytest -q

smoke:
	scripts/smoke_affilipilot.sh

verify:
	scripts/verify_all.sh

readiness:
	PYTHONPATH=. $(PYTHON) -m affilipilot readiness

demo:
	PYTHONPATH=. $(PYTHON) -m affilipilot demo-happy-path

secret-scan:
	$(PYTHON) scripts/secret_scan.py

clean-smoke:
	rm -rf data/smoke-happy-path data/smoke-happy-path.db data/demo-happy-path data/demo-happy-path.db

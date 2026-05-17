#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m compileall -q affilipilot
PYTHONPATH=. python3 -m pytest -q
scripts/smoke_affilipilot.sh >/tmp/affilipilot-verify-smoke.out
python3 scripts/secret_scan.py
printf 'AffiliPilot verify: PASS\n'

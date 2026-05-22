#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m compileall -q affilipilot
if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import pytest
PY
then
  PYTHONPATH=. "$PYTHON_BIN" -m pytest -q
else
  printf 'AffiliPilot verify: SKIP pytest (pytest not installed for %s)\n' "$PYTHON_BIN"
fi
scripts/smoke_affilipilot.sh >/tmp/affilipilot-verify-smoke.out
"$PYTHON_BIN" scripts/secret_scan.py
printf 'AffiliPilot verify: PASS\n'

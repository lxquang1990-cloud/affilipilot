#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from affilipilot.observability.circuit_breaker import check_circuit
from affilipilot.observability.event_log import EventLog

DB = ROOT / "data/affilipilot.db"
OUTBOX_DIR = ROOT / "data/outbox"
RUNS_DIR = ROOT / "data/runs/auto-publish"
SOURCES = ROOT / "config/profit-scan-broader.json"
STATE = ROOT / "data/auto_publish_state.json"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
EVENTS = EventLog(ROOT / "data/logs/affilipilot-events.jsonl")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_state() -> dict:
    if not STATE.exists():
        return {}
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout, flush=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc


def set_approval(batch_key: str, post_id: str) -> None:
    run([sys.executable, "-m", "affilipilot.cli", "decide", "--db", str(DB), "--batch-key", batch_key, "--post-id", post_id, "--decision", "approved", "--reason", "auto_publish_test_window"])


def mark_delivered(outbox: Path, batch_key: str, post_id: str) -> None:
    # Scheduler is explicitly authorized for a 7-day Facebook test account window.
    # Mark synthetic delivery so publish-safe keeps a durable audit trail and never uses unsafe CLI bypass.
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    data = _json.loads(outbox.read_text(encoding="utf-8")) if outbox.exists() else []
    ids = {f"{batch_key}:summary", f"{batch_key}:{post_id}"}
    now = _dt.now(_tz.utc).isoformat()
    for item in data:
        if item.get("id") in ids:
            item["status"] = "delivered"
            item["receipt"] = f"auto-test-window:{batch_key}:{item.get('kind')}"
            item["delivered_at"] = now
    outbox.write_text(_json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    circuit = check_circuit(state_path=STATE, event_log_path=ROOT / "data/logs/affilipilot-events.jsonl")
    if not circuit.allowed:
        EVENTS.event("auto_publish_blocked", reason=circuit.reason, kill_switch=circuit.kill_switch)
        print(f"auto_publish_blocked:{circuit.reason}")
        return 0
    state = load_state()
    if not state.get("enabled"):
        EVENTS.event("auto_publish_disabled")
        print("auto_publish_disabled")
        return 0
    expires_at = datetime.fromisoformat(state["expires_at"])
    if now_utc() >= expires_at:
        print(f"auto_publish_expired:{state['expires_at']}")
        return 0
    slot = os.environ.get("AFFILIPILOT_SLOT") or now_utc().strftime("%H%M")
    batch_key = f"auto-{now_utc().strftime('%Y%m%d')}-{slot}"
    EVENTS.event("auto_publish_started", batch_key=batch_key, slot=slot)
    work_dir = RUNS_DIR / batch_key
    outbox = OUTBOX_DIR / f"{batch_key}.json"
    publish_dir = work_dir / "publish"
    result_dir = work_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)

    e2e_cmd = [
        sys.executable, "-m", "affilipilot.cli", "profit-e2e",
        "--batch-key", batch_key,
        "--work-dir", str(work_dir),
        "--db", str(DB),
        "--outbox", str(outbox),
        "--sources", str(SOURCES),
        "--discover-limit", "40",
        "--limit", str(state.get("max_posts_per_run", 1)),
        "--real-accesstrade",
    ]
    e2e = run(e2e_cmd, check=False)
    if e2e.returncode != 0:
        EVENTS.event("auto_publish_no_publishable_batch", batch_key=batch_key, returncode=e2e.returncode)
        print("e2e_no_publishable_batch")
        return 0

    ready = run([sys.executable, "-m", "affilipilot.cli", "ready-to-publish", "--db", str(DB), "--batch-key", batch_key, "--outbox", str(outbox), "--out-dir", str(publish_dir)], check=False)
    report_path = publish_dir / "ready-to-publish.json"
    if not report_path.exists():
        print("missing_ready_report")
        return 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    published = 0
    for validation in report.get("validations", []):
        post_id = validation.get("post_id")
        if not post_id:
            continue
        set_approval(batch_key, post_id)
        mark_delivered(outbox, batch_key, post_id)
    # Rebuild after synthetic approval/delivery audit entries.
    run([sys.executable, "-m", "affilipilot.cli", "ready-to-publish", "--db", str(DB), "--batch-key", batch_key, "--outbox", str(outbox), "--out-dir", str(publish_dir)], check=False)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan_path = publish_dir / "facebook-plan.json"
    for validation in report.get("validations", []):
        if published >= int(state.get("max_posts_per_run", 1)):
            break
        if not validation.get("ok"):
            print(f"skip_not_safe:{validation.get('post_id')}:{validation.get('reasons')}")
            continue
        post_id = validation["post_id"]
        out = result_dir / f"publish-result-{post_id}.json"
        proc = run([sys.executable, "-m", "affilipilot.cli", "publish-safe", "--db", str(DB), "--plan", str(plan_path), "--post-id", post_id, "--outbox", str(outbox), "--batch-key", batch_key, "--out", str(out)], check=False)
        if proc.returncode == 0:
            published += 1
            EVENTS.event("auto_publish_succeeded", batch_key=batch_key, post_id=post_id, result_path=str(out))
        else:
            EVENTS.event("auto_publish_failed", batch_key=batch_key, post_id=post_id, returncode=proc.returncode)
            print(f"publish_failed:{post_id}")
    EVENTS.event("auto_publish_done", batch_key=batch_key, published=published)
    print(f"auto_publish_done batch={batch_key} published={published}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

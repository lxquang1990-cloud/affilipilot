#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
RUNS_DIR = ROOT / "data/runs/seed-auto"
OUTBOX_DIR = ROOT / "data/outbox"
STATE = ROOT / "data/auto_publish_state.json"
EVENTS = EventLog(ROOT / "data/logs/affilipilot-events.jsonl")


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout, flush=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def mark_delivered(outbox: Path, batch_key: str, post_id: str) -> None:
    data = json.loads(outbox.read_text(encoding="utf-8")) if outbox.exists() else []
    now = datetime.now(timezone.utc).isoformat()
    ids = {f"{batch_key}:summary", f"{batch_key}:{post_id}"}
    for item in data:
        if item.get("id") in ids:
            item["status"] = "delivered"
            item["receipt"] = f"seed-auto-test-window:{batch_key}:{item.get('kind')}"
            item["delivered_at"] = now
    outbox.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Curated seed file -> Seed Hunter -> Accesstrade -> quality gates -> optional guarded publish")
    parser.add_argument("--seed-file", required=True, help="Curated PDP input file in AffiliPilot link-line format")
    parser.add_argument("--batch-key", default="")
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--db", default=str(DB))
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--publish", action="store_true", help="Publish if safe and circuit/test state allows it")
    parser.add_argument("--real-accesstrade", action="store_true", help="Call real Accesstrade conversion API")
    parser.add_argument("--campaign-key", default="", help="Optional Accesstrade campaign key override")
    parser.add_argument("--event-log", default="data/logs/affilipilot-events.jsonl")
    args = parser.parse_args()

    batch_key = args.batch_key or f"seed-auto-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    work_dir = Path(args.work_dir) if args.work_dir else RUNS_DIR / batch_key
    work_dir.mkdir(parents=True, exist_ok=True)
    outbox = OUTBOX_DIR / f"{batch_key}.json"
    event_log = EventLog(args.event_log)
    event_log.event("seed_auto_started", batch_key=batch_key, seed_file=args.seed_file, publish=args.publish)

    hunter_dir = work_dir / "seed-hunter"
    hunter = run([sys.executable, "scripts/seed_hunter.py", "--source", "seed_file", "--seed-file", args.seed_file, "--out-dir", str(hunter_dir), "--limit", str(args.limit)], check=False)
    hunter_summary = load_json(hunter_dir / "seed-hunter-summary.json")
    if hunter.returncode != 0 or not hunter_summary.get("count"):
        event_log.event("seed_auto_no_valid_seeds", batch_key=batch_key, returncode=hunter.returncode)
        print("seed_auto_no_valid_seeds")
        return 0

    seed_input = Path(hunter_summary["input_path"])
    converted_json = work_dir / "accesstrade-converted.json"
    converted_input = work_dir / "converted.input.txt"
    convert_cmd = [sys.executable, "-m", "affilipilot.cli", "accesstrade-convert", "--input", str(seed_input), "--out", str(converted_json), "--write-input", str(converted_input), "--limit", str(args.limit)]
    if args.real_accesstrade:
        convert_cmd.append("--real")
    if args.campaign_key:
        convert_cmd.extend(["--campaign-key", args.campaign_key])
    convert = run(convert_cmd, check=False)
    converted = load_json(converted_json)
    if convert.returncode != 0 or converted.get("ok_count", 0) == 0:
        event_log.event("seed_auto_conversion_failed", batch_key=batch_key, returncode=convert.returncode, failed=converted.get("failed_count"))
        print("seed_auto_conversion_failed")
        return 0

    draft_dir = work_dir / "drafts"
    run([sys.executable, "-m", "affilipilot.cli", "draft-links", "--input", str(converted_input), "--work-dir", str(draft_dir), "--db", args.db, "--batch-key", batch_key, "--limit", str(args.limit), "--outbox", str(outbox)], check=True)

    ready_dir = work_dir / "ready"
    run([sys.executable, "-m", "affilipilot.cli", "ready-to-publish", "--db", args.db, "--batch-key", batch_key, "--outbox", str(outbox), "--out-dir", str(ready_dir)], check=False)
    ready_report = load_json(ready_dir / "ready-to-publish.json")
    publishable = [v for v in ready_report.get("validations", []) if v.get("ok")]
    event_log.event("seed_auto_ready", batch_key=batch_key, publishable=len(publishable), validations=len(ready_report.get("validations", [])))

    published = 0
    if args.publish and publishable:
        circuit = check_circuit(state_path=STATE, event_log_path=args.event_log)
        if not circuit.allowed:
            event_log.event("seed_auto_publish_blocked", batch_key=batch_key, reason=circuit.reason)
            print(f"seed_auto_publish_blocked:{circuit.reason}")
        else:
            for validation in publishable[: args.limit]:
                post_id = validation["post_id"]
                run([sys.executable, "-m", "affilipilot.cli", "decide", "--db", args.db, "--batch-key", batch_key, "--post-id", post_id, "--decision", "approved", "--reason", "seed_auto_test_window"], check=True)
                mark_delivered(outbox, batch_key, post_id)
            run([sys.executable, "-m", "affilipilot.cli", "ready-to-publish", "--db", args.db, "--batch-key", batch_key, "--outbox", str(outbox), "--out-dir", str(ready_dir)], check=False)
            plan = ready_dir / "facebook-plan.json"
            result_dir = work_dir / "publish-results"
            result_dir.mkdir(exist_ok=True)
            for validation in load_json(ready_dir / "ready-to-publish.json").get("validations", []):
                if published >= args.limit or not validation.get("ok"):
                    continue
                post_id = validation["post_id"]
                out = result_dir / f"publish-result-{post_id}.json"
                proc = run([sys.executable, "-m", "affilipilot.cli", "publish-safe", "--db", args.db, "--plan", str(plan), "--post-id", post_id, "--outbox", str(outbox), "--batch-key", batch_key, "--out", str(out)], check=False)
                if proc.returncode == 0:
                    published += 1
                    event_log.event("seed_auto_publish_succeeded", batch_key=batch_key, post_id=post_id, result_path=str(out))
                else:
                    event_log.event("seed_auto_publish_failed", batch_key=batch_key, post_id=post_id, returncode=proc.returncode)

    summary = {
        "batch_key": batch_key,
        "work_dir": str(work_dir),
        "seed_count": hunter_summary.get("count", 0),
        "converted_ok": converted.get("ok_count", 0),
        "publishable": len(publishable),
        "published": published,
        "outbox": str(outbox),
    }
    (work_dir / "seed-auto-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    event_log.event("seed_auto_done", **summary)
    print("seed_auto_done " + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

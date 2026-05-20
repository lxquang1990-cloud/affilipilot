from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def run_seed_auto(
    *,
    seed_file: str | Path,
    batch_key: str,
    work_dir: str | Path,
    db_path: str | Path,
    outbox_path: str | Path,
    limit: int = 3,
    campaign_key: str = "",
    real_accesstrade: bool = False,
    publish: bool = False,
) -> dict[str, Any]:
    """Run curated PDP seeds through validation, Accesstrade conversion, gates, and optional publish.

    This is a thin programmatic wrapper around ``scripts/seed_to_auto_e2e.py`` so the
    normal CLI/reporting stack can treat curated seeds as the primary product source.
    It never publishes unless ``publish=True`` is explicitly passed to the script.
    """

    root = Path(__file__).resolve().parents[2]
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "scripts/seed_to_auto_e2e.py",
        "--seed-file",
        str(seed_file),
        "--batch-key",
        batch_key,
        "--work-dir",
        str(work_dir),
        "--db",
        str(db_path),
        "--limit",
        str(limit),
        "--event-log",
        str(work_dir / "events.jsonl"),
    ]
    if campaign_key:
        cmd.extend(["--campaign-key", campaign_key])
    if real_accesstrade:
        cmd.append("--real-accesstrade")
    if publish:
        cmd.append("--publish")

    proc = _run(cmd, cwd=root)
    summary_path = work_dir / "seed-auto-summary.json"
    summary = _load_json(summary_path)
    summary.setdefault("batch_key", batch_key)
    summary.setdefault("work_dir", str(work_dir))
    summary["returncode"] = proc.returncode
    summary["stdout"] = proc.stdout
    summary["summary_path"] = str(summary_path)
    summary["seed_file"] = str(seed_file)
    summary["db_path"] = str(db_path)
    summary["outbox_path"] = str(outbox_path)
    summary["real_accesstrade"] = real_accesstrade
    summary["publish_requested"] = publish
    return summary


def render_seed_auto_summary(summary: dict[str, Any]) -> str:
    stdout_tail = "\n".join((summary.get("stdout") or "").splitlines()[-8:])
    lines = [
        "🐌 AffiliPilot curated-seed E2E",
        f"Batch: {summary.get('batch_key')}",
        f"Status: {'OK' if summary.get('returncode') == 0 else 'BLOCK'} returncode={summary.get('returncode')}",
        f"Work dir: {summary.get('work_dir')}",
        f"Seed file: {summary.get('seed_file')}",
        "",
        "Pipeline:",
        f"- valid seeds: {summary.get('seed_count', 0)}",
        f"- converted ok: {summary.get('converted_ok', 0)}",
        f"- publishable: {summary.get('publishable', 0)}",
        f"- published: {summary.get('published', 0)}",
        f"- outbox: {summary.get('outbox') or summary.get('outbox_path')}",
    ]
    if stdout_tail:
        lines.extend(["", "Last log lines:", stdout_tail])
    return "\n".join(lines)

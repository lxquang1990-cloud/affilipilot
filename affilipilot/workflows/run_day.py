from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from affilipilot.analytics.report import write_day_report
from affilipilot.publishing.ready_package import build_ready_to_post_package
from affilipilot.workflows.approval import create_approval_batch


def run_day(input_path: str | Path, work_dir: str | Path, db_path: str | Path, *, batch_key: str | None = None, limit: int = 5) -> dict:
    batch_key = batch_key or f"day-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    work_dir = Path(work_dir)
    drafts_dir = work_dir / "drafts" / batch_key
    ready_dir = work_dir / "ready" / batch_key
    reports_dir = work_dir / "reports"

    demo_day = date(2026, 5, 16) if batch_key.endswith("-test") else None
    manifest = create_approval_batch(input_path, drafts_dir, db_path, batch_key=batch_key, limit=limit, day=demo_day)
    ready = build_ready_to_post_package(db_path, batch_key=batch_key, out_dir=ready_dir)
    report = write_day_report(db_path, batch_key=batch_key, out_path=reports_dir / f"{batch_key}.md")

    return {
        "batch_key": batch_key,
        "manifest": manifest,
        "drafts_dir": str(drafts_dir),
        "ready_dir": str(ready_dir),
        "report": str(report),
        "ready_count": ready["ready_count"],
        "held_count": ready["held_count"],
        "approval_preview": str(drafts_dir / "approval_batch_preview.txt"),
    }

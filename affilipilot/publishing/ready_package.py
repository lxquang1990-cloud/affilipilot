from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from affilipilot.db import AffiliPilotDB
from affilipilot.publishing.gate import evaluate_publish_gate


def build_ready_to_post_package(db_path: str | Path, *, batch_key: str, out_dir: str | Path, facebook_verified: bool = False, dry_run_passed: bool = False) -> dict[str, Any]:
    db = AffiliPilotDB(db_path)
    batch = db.get_batch(batch_key)
    if not batch:
        raise KeyError(f"Batch not found: {batch_key}")
    approvals = {row["post_id"]: row for row in db.get_approvals(batch_key)}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ready = []
    held = []
    for post in batch["manifest"].get("posts", []):
        approval = approvals.get(post["post_id"], {})
        approved = approval.get("status") == "approved"
        gate = evaluate_publish_gate(post, approved=approved, facebook_verified=facebook_verified, dry_run_passed=dry_run_passed)
        post_text = Path(post["files"]["post_text"]).read_text(encoding="utf-8", errors="ignore") if Path(post["files"]["post_text"]).exists() else ""
        record = {
            "post_id": post["post_id"],
            "product": post.get("product", {}),
            "tracking": post.get("tracking", {}),
            "utm": post.get("utm", {}),
            "approval": approval,
            "publish_gate": {"allowed": gate.allowed, "reasons": gate.reasons, "fallback_required": gate.fallback_required},
            "post_text": post_text,
        }
        if approved and gate.fallback_required:
            ready.append(record)
            (out_dir / f"{post['post_id']}.ready-to-post.txt").write_text(post_text, encoding="utf-8")
        elif gate.allowed:
            ready.append(record)
        else:
            held.append(record)

    package = {
        "batch_key": batch_key,
        "facebook_verified": facebook_verified,
        "dry_run_passed": dry_run_passed,
        "ready_count": len(ready),
        "held_count": len(held),
        "ready": ready,
        "held": held,
    }
    (out_dir / "ready_package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return package

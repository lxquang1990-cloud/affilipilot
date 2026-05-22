from __future__ import annotations

from pathlib import Path
from typing import Any

from affilipilot.publishing.publish_safe_v2 import render_publish_safe_v2, validate_publish_safe_v2



def validate_publish_safe(
    *,
    db_path: str | Path,
    batch_key: str,
    post_id: str,
    plan_path: str | Path,
    outbox_path: str | Path,
) -> dict[str, Any]:
    """Validate all preconditions required before a real Facebook publish.

    This function performs no network calls and no publish side effects.
    The public API remains stable, but the implementation is publish-safe v2.
    """
    return validate_publish_safe_v2(
        db_path=db_path,
        batch_key=batch_key,
        post_id=post_id,
        plan_path=plan_path,
        outbox_path=outbox_path,
    )


def render_publish_safe_validation(result: dict[str, Any]) -> str:
    return render_publish_safe_v2(result)

#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from affilipilot.publishing.facebook import FacebookConfig, check_facebook_config  # noqa: E402


def delete_post(facebook_post_id: str, *, timeout: int = 30) -> dict:
    config = FacebookConfig.from_env()
    health = check_facebook_config(config)
    if not health.verified:
        raise SystemExit("Facebook config not verified: " + ",".join(health.reasons))
    endpoint = f"https://graph.facebook.com/v19.0/{facebook_post_id}"
    data = urllib.parse.urlencode({"access_token": config.page_access_token}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "response": parsed, "facebook_post_id": facebook_post_id}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500]}
        return {"ok": False, "status": exc.code, "response": parsed, "facebook_post_id": facebook_post_id}


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/runs/delete-facebook-posts")
    posts = sys.argv[2:]
    if not posts:
        raise SystemExit("Usage: delete_facebook_posts.py <out_dir> <facebook_post_id>...")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_ok = True
    for post_id in posts:
        result = delete_post(post_id)
        (out_dir / f"{post_id.replace('/', '_').replace(':', '_')}.delete.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        all_ok = all_ok and result.get("ok") and result.get("response", {}).get("success") is True
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

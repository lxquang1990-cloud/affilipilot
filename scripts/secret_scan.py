from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"ACCESSTRADE_TOKEN\s*=\s*[^.\n][^\n]+"),
    re.compile(r"FACEBOOK_PAGE_ACCESS_TOKEN\s*=\s*[^.\n][^\n]+"),
    re.compile(r"OPENROUTER_API_KEY\s*=\s*[^.\n][^\n]+"),
    re.compile(r"(access_token|page_access_token|token)\"?\s*:\s*\"(?!\.|\*|token|placeholder|redacted)[^\"]{12,}\"", re.IGNORECASE),
]
ALLOWLIST = {"build-proposal.md", "test_config_budget_digest.py", "security.py", "test_security_readiness.py", "smoke_affilipilot.sh"}


def main() -> int:
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.suffix not in {".py", ".md", ".txt", ".csv", ".sh", ".env", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PATTERNS:
            if pattern.search(text) and path.name not in ALLOWLIST:
                hits.append(str(path.relative_to(ROOT)))
    if hits:
        print("Potential secret material found:")
        for hit in sorted(set(hits)):
            print(f"- {hit}")
        return 1
    print("Secret scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

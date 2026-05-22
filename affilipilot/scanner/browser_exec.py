from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from affilipilot.scanner.discovery import DiscoveryResult, discover_product_details_from_html
from affilipilot.scanner.core import write_scan_result

@dataclass
class BrowserExecutionResult:
    ok: bool
    scan_path: str = ""
    total: int = 0
    error: str = ""
    notes: list[str] = field(default_factory=list)


def browser_render_discover(url: str, *, out_path: str | Path, source: str = "AUTO", category: str = "unknown", limit: int = 10, timeout_ms: int = 45000, wait_ms: int = 3000, headless: bool = True) -> BrowserExecutionResult:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return BrowserExecutionResult(
            ok=False,
            error="playwright_not_installed",
            notes=["Install Playwright and browser runtime before using browser-render discovery."],
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(wait_ms)
            html = page.content()
            # Shopee may redirect anonymous browser sessions to a verify/error page,
            # while still embedding PDP initial data in the returned HTML. If the
            # first wait catches only the shell, give it one more short settle pass.
            if "text/mfe-initial-data" not in html and "shopee.vn/verify/traffic" in page.url:
                page.wait_for_timeout(min(wait_ms, 5000))
                html = page.content()
            browser.close()
    except Exception as exc:
        return BrowserExecutionResult(ok=False, error=f"browser_render_failed:{exc}")

    discovery: DiscoveryResult = discover_product_details_from_html(html, page_url=url, source=source, category=category, limit=limit)
    path = write_scan_result(discovery.to_scan_result(), out_path)
    notes = ["discovery_only_no_publish"]
    if not discovery.items:
        # Contract: when ok=False, error must be populated so downstream workflows can log a reason.
        # Empty HTML, anti-bot blocks, or unparseable layouts all hit this path.
        return BrowserExecutionResult(
            ok=False,
            scan_path=str(path),
            total=0,
            error="no_products_discovered",
            notes=notes,
        )
    return BrowserExecutionResult(
        ok=True,
        scan_path=str(path),
        total=len(discovery.items),
        notes=notes,
    )

from affilipilot.scanner.browser_exec import browser_render_discover


def test_browser_render_discover_gracefully_handles_missing_runtime(tmp_path, monkeypatch):
    result = browser_render_discover("https://example.com", out_path=tmp_path / "scan.json")
    # CI/local machines may or may not have Playwright. The important contract is no exception and structured result.
    assert isinstance(result.ok, bool)
    if not result.ok:
        assert result.error

import json
from pathlib import Path

import affilipilot.publishing.facebook_token_manager as tm


def test_update_secret_file_preserves_and_chmods(tmp_path):
    env = tmp_path / "affilipilot.env"
    env.write_text("FACEBOOK_APP_ID=app\nOTHER=value\n", encoding="utf-8")
    updated = tm.update_secret_file(env, {"FACEBOOK_PAGE_ACCESS_TOKEN": ".page-token", "FACEBOOK_USER_TOKEN_EXPIRES": "2026-07-01"})
    text = env.read_text(encoding="utf-8")
    assert "OTHER=value" in text
    assert "FACEBOOK_PAGE_ACCESS_TOKEN=.page-token" in text
    assert "FACEBOOK_USER_TOKEN_EXPIRES=2026-07-01" in text
    assert set(updated) == {"FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_USER_TOKEN_EXPIRES"}
    assert oct(env.stat().st_mode & 0o777) == "0o600"


def test_exchange_short_token_updates_user_and_page_token(tmp_path, monkeypatch):
    env = tmp_path / "affilipilot.env"
    env.write_text("FACEBOOK_APP_ID=app\nFACEBOOK_APP_SECRET=secret\nFACEBOOK_PAGE_ID=page-1\n", encoding="utf-8")

    def fake_get_json(endpoint, params, timeout=30):
        if endpoint.endswith("/oauth/access_token"):
            assert params["fb_exchange_token"] == ".short"
            return {"access_token": ".long-user", "expires_in": 5184000}
        if endpoint.endswith("/me/accounts"):
            assert params["access_token"] == ".long-user"
            return {"data": [{"id": "page-1", "name": "Page", "access_token": ".page-token"}]}
        raise AssertionError(endpoint)

    monkeypatch.setattr(tm, "_get_json", fake_get_json)
    result = tm.exchange_short_token(".short", secret_path=env)
    assert result.ok
    text = env.read_text(encoding="utf-8")
    assert "FACEBOOK_USER_ACCESS_TOKEN=.long-user" in text
    assert "FACEBOOK_PAGE_ACCESS_TOKEN=.page-token" in text
    assert "FACEBOOK_USER_TOKEN_EXPIRES=" in text
    rendered = tm.render_token_manager_result(result)
    assert ".long-user" not in rendered
    assert ".page-token" not in rendered


def test_refresh_blocks_expired_user_token(tmp_path, monkeypatch):
    env = tmp_path / "affilipilot.env"
    env.write_text("FACEBOOK_APP_ID=app\nFACEBOOK_APP_SECRET=secret\nFACEBOOK_PAGE_ID=page-1\nFACEBOOK_USER_ACCESS_TOKEN=expired\n", encoding="utf-8")
    monkeypatch.setattr(tm, "inspect_token", lambda *args, **kwargs: {"is_valid": False})
    result = tm.refresh_from_user_token(secret_path=env)
    assert not result.ok
    assert "manual OAuth exchange required" in result.message


def test_refresh_auto_skips_when_not_near_expiry(tmp_path):
    env = tmp_path / "affilipilot.env"
    env.write_text("FACEBOOK_APP_ID=app\nFACEBOOK_APP_SECRET=secret\nFACEBOOK_PAGE_ID=page-1\nFACEBOOK_USER_ACCESS_TOKEN=user\nFACEBOOK_USER_TOKEN_EXPIRES=2099-01-01\n", encoding="utf-8")
    result = tm.refresh_from_user_token(secret_path=env, auto=True, threshold_days=15)
    assert result.ok
    assert result.message.startswith("skip_refresh")


def test_derive_page_token_lists_pages_when_missing(tmp_path, monkeypatch):
    env = tmp_path / "affilipilot.env"
    env.write_text("FACEBOOK_PAGE_ID=missing\nFACEBOOK_USER_ACCESS_TOKEN=user\n", encoding="utf-8")
    monkeypatch.setattr(tm, "get_page_token", lambda *args, **kwargs: ("", [{"id": "page-2", "name": "Other"}]))
    result = tm.derive_page_token(secret_path=env)
    assert not result.ok
    rendered = tm.render_token_manager_result(result)
    assert "page-2" in rendered
    assert "user" not in rendered

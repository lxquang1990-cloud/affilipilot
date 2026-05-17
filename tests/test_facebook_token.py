from affilipilot.publishing.facebook_token import FacebookTokenReport, render_facebook_token_report


def test_render_facebook_token_report_no_secret():
    report = FacebookTokenReport(
        valid=False,
        app_id_present=True,
        app_secret_present=True,
        token_present=True,
        page_id_present=True,
        scopes=["pages_read_engagement"],
        missing_scopes=["pages_manage_posts"],
        page_probe_ok=False,
        error="bad token",
    )
    text = render_facebook_token_report(report)
    assert "pages_manage_posts" in text
    assert "bad token" in text
    assert "secret" not in text.lower() or "App Secret" in text

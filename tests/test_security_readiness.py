import stat

from affilipilot.readiness import build_readiness_report, render_readiness_report
from affilipilot.security import check_secret_file_permissions, write_secret_template


def test_write_secret_template_secure_permissions(tmp_path):
    path = tmp_path / "affilipilot.env"
    write_secret_template(path)
    info = check_secret_file_permissions(path)
    assert info["exists"] is True
    assert info["secure"] is True
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    text = path.read_text(encoding="utf-8")
    assert "ACCESSTRADE_TOKEN=" in text
    assert "FACEBOOK_PAGE_ACCESS_TOKEN=" in text


def test_readiness_report_renders(monkeypatch, tmp_path):
    secret = tmp_path / "missing.env"
    monkeypatch.setattr("affilipilot.config.DEFAULT_SECRET_PATH", secret)
    report = build_readiness_report()
    rendered = render_readiness_report(report)
    assert "AffiliPilot readiness report" in rendered
    assert any(c.name == "product_input" and c.status == "pass" for c in report.checks)

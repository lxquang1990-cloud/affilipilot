from affilipilot.content.compliance import check_mom_baby_compliance, default_affiliate_disclosure
from affilipilot.models import ComplianceStatus


def test_passes_safe_post_with_disclosure():
    text = "Hộp chia sữa giúp mẹ sắp xếp đồ ăn dặm gọn hơn.\n" + default_affiliate_disclosure()
    result = check_mom_baby_compliance(text, category="feeding")
    assert result.status == ComplianceStatus.PASS


def test_blocks_medical_claim():
    text = "Sản phẩm này giúp bé hết ho nhanh chóng.\n" + default_affiliate_disclosure()
    result = check_mom_baby_compliance(text, category="unknown")
    assert result.status == ComplianceStatus.BLOCK
    assert "medical_claim" in result.risk_flags


def test_missing_disclosure_needs_review():
    result = check_mom_baby_compliance("Một món đồ tiện giúp góc đồ của bé gọn hơn.", category="storage")
    assert result.status == ComplianceStatus.NEEDS_REVIEW
    assert "missing_affiliate_disclosure" in result.risk_flags


def test_blocks_high_risk_category():
    text = "Vitamin cho bé.\n" + default_affiliate_disclosure()
    result = check_mom_baby_compliance(text, category="vitamin")
    assert result.status == ComplianceStatus.BLOCK

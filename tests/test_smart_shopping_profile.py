from affilipilot.content.ai_caption import build_ai_caption_prompt
from affilipilot.content.early_filter import normalize_category
from affilipilot.content.niche_policy import POSITIONING, evaluate_niche_fit
from affilipilot.content.page_fit import configured_page_audience, evaluate_page_audience_fit
from affilipilot.models import ProductCandidate
from affilipilot.scoring.portfolio import PREFERRED_ORDER


def test_smart_shopping_positioning_is_default():
    assert POSITIONING == "Mua sắm thông minh — món nhỏ, tiện, đáng tiền, dễ kiểm chứng."


def test_home_consumable_is_core_smart_shopping_category():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Thùng giấy ăn gấu trúc 4 lớp dày dặn dùng trong nhà bếp phòng khách",
        category="home_consumable",
        price_vnd=99000,
        image_url="https://img.example/p.jpg",
        notes="khăn giấy; giấy ăn; dùng hằng ngày; voucher; brand bonus",
    )
    result = evaluate_niche_fit(product)
    assert result.passed is True
    assert any(reason.startswith("core_smart_shopping_category:home_consumable") for reason in result.reasons)


def test_ai_caption_prompt_not_mother_baby_or_old_page_anchored():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Kệ nhà bếp gọn",
        category="home_organization",
        price_vnd=199000,
        notes="merchant=shopee",
    )
    prompt = build_ai_caption_prompt(product)
    lowered = prompt.lower()
    assert "mua sắm thông minh" in lowered
    assert "nâng niu" not in lowered
    assert "mẹ và bé" not in lowered
    assert "facebook page bán đồ gia đình" not in lowered


def test_page_audience_defaults_to_smart_shopping(monkeypatch):
    monkeypatch.delenv("AFFILIPILOT_PAGE_AUDIENCE", raising=False)
    monkeypatch.delenv("AFFILIPILOT_PAGE_PROFILE", raising=False)
    assert configured_page_audience() == "smart_shopping"


def test_smart_shopping_page_fit_accepts_household_consumable():
    result = evaluate_page_audience_fit({"category": "home_consumable", "title": "Khăn giấy dùng hằng ngày"})
    assert result.passed is True


def test_early_filter_normalizes_household_consumable_and_organization():
    tissue = ProductCandidate(url="https://shopee.vn/p", title="Thùng giấy ăn 4 lớp", category="unknown")
    rack = ProductCandidate(url="https://shopee.vn/p", title="Kệ để đồ phòng tắm sắp xếp gọn", category="unknown")
    assert normalize_category(tissue) == "home_consumable"
    assert normalize_category(rack) == "home_organization"


def test_portfolio_prefers_smart_shopping_verticals_before_mother_baby():
    assert PREFERRED_ORDER.index("home_consumable") < PREFERRED_ORDER.index("mother_baby")
    assert PREFERRED_ORDER.index("home_organization") < PREFERRED_ORDER.index("mother_baby")

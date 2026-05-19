from affilipilot.models import ProductCandidate
from affilipilot.scoring.portfolio import select_portfolio


def _item(title: str, category: str, score: int):
    return {"product": ProductCandidate(url=f"https://example.com/{title}", title=title, category=category, image_url="https://example.com/i.jpg"), "score": score}


def test_portfolio_prioritizes_preferred_categories_over_many_toys():
    ranked = [
        _item("toy high 1", "toy", 95),
        _item("toy high 2", "toy", 94),
        _item("home useful", "home_appliance", 88),
        _item("office useful", "office_productivity", 84),
    ]
    selected, blocked = select_portfolio(ranked, limit=3)
    categories = [item["product"].category for item in selected]
    assert "home_appliance" in categories
    assert "office_productivity" in categories
    assert categories.count("toy") <= 1
    assert any(item.get("portfolio_block_reason") == "category_quota_full:toy" for item in blocked)


def test_portfolio_blocks_low_fit_unknown_without_exception_score():
    ranked = [_item("unknown ok", "unknown", 80), _item("home useful", "home_living", 70)]
    selected, blocked = select_portfolio(ranked, limit=2)
    assert [item["product"].category for item in selected] == ["home_living"]
    assert any(item.get("portfolio_block_reason") == "low_fit_category_cap:unknown" for item in blocked)

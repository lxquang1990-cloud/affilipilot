from affilipilot.content.early_filter import normalize_category
from affilipilot.models import ProductCandidate
from affilipilot.workflows.auto_source_hunter import _auto_broad_fit, _title_adjustment


def test_normalize_category_promotes_unknown_home_appliance_title():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Máy hút bụi cầm tay hút khô hút nước cho gia đình",
        category="unknown",
    )
    assert normalize_category(product) == "home_appliance"


def test_normalize_category_marks_books_low_fit():
    product = ProductCandidate(
        url="https://tiki.vn/book-p1.html",
        title="Sách Tiếng Anh Dành Cho Người Đi Du Lịch Nước Ngoài",
        category="unknown",
    )
    assert normalize_category(product) == "book"


def test_auto_broad_fit_blocks_generic_book_even_with_travel_word():
    product = ProductCandidate(
        url="https://tiki.vn/book-p1.html",
        title="Sách Tiếng Anh Dành Cho Người Đi Du Lịch Nước Ngoài",
        category="book",
    )
    _score, reasons = _title_adjustment(product.title)
    ok, fit_reasons = _auto_broad_fit(product, reasons)
    assert not ok
    assert "low_automation_fit_title" in fit_reasons


def test_auto_broad_fit_allows_unknown_only_with_high_intent_home_title():
    product = ProductCandidate(
        url="https://shopee.vn/product/1/2",
        title="Bộ khuôn làm bánh cuốn tại nhà size 21 tặng kèm công thức",
        category="unknown",
    )
    _score, reasons = _title_adjustment(product.title)
    ok, fit_reasons = _auto_broad_fit(product, reasons)
    assert ok
    assert fit_reasons == ["conditional_category_with_high_intent_title"]

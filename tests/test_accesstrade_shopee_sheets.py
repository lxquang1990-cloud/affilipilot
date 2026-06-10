from affilipilot.accesstrade import shopee_sheets
from affilipilot.accesstrade.shopee_sheets import (
    SHOPEE_SHORTLINK_DOMAIN,
    google_sheet_csv_url,
    google_sheet_gviz_csv_url,
    parse_sheet_csv,
)
from affilipilot.workflows import e2e_profit


def test_parse_shopee_best_seller_like_csv():
    csv_text = "Tên sản phẩm,Link sản phẩm,Giá,Shop,Hoa hồng,Ảnh\n" \
        "Set bàn chải đánh răng ba mặt cho bé,https://shopee.vn/test-product-i.1.2,đ39.000,kingbabyvn,9,72%,https://img.example/p.jpg\n"

    products = parse_sheet_csv(csv_text)

    assert len(products) == 1
    assert products[0].url == "https://shopee.vn/test-product-i.1.2"
    assert products[0].title.startswith("Set bàn chải")
    assert products[0].price_vnd == 39000
    assert products[0].merchant == "kingbabyvn"


def test_google_sheet_export_url_uses_csv_gid():
    url = google_sheet_csv_url("sheet123", "3026657")
    assert url == "https://docs.google.com/spreadsheets/d/sheet123/export?format=csv&gid=3026657"


def test_parse_sheet_csv_supports_offset_for_deep_sheet_rotation():
    csv_text = "Tên sản phẩm,Link sản phẩm,Giá,Shop\n" + "\n".join(
        f"Item {idx},https://shopee.vn/product/1/{idx},đ{idx}000,shop{idx}"
        for idx in range(1, 6)
    )

    products = parse_sheet_csv(csv_text, limit=2, offset=2)

    assert [p.title for p in products] == ["Item 3", "Item 4"]


def test_fetch_shopee_sheet_products_falls_back_to_gviz_csv(monkeypatch):
    export_url = google_sheet_csv_url("sheet123", "gid123")
    gviz_url = google_sheet_gviz_csv_url("sheet123", "gid123")
    calls = []

    def fake_fetch(url, *, timeout=30):
        calls.append(url)
        if url == export_url:
            raise RuntimeError("export_400")
        assert url == gviz_url
        return "Tên sản phẩm,Link sản phẩm,Giá,Shop\nItem 1,https://shopee.vn/product/1/2,đ39000,shop1\n"

    monkeypatch.setattr(shopee_sheets, "_fetch_text", fake_fetch)

    report = shopee_sheets.fetch_shopee_sheet_products(sheet_id="sheet123", gid="gid123", limit=5)

    assert calls == [export_url, gviz_url]
    assert report["ok"] is True
    assert report["source_url"] == gviz_url
    assert report["total"] == 1
    assert report["products"][0]["url"] == "https://shopee.vn/product/1/2"


def test_e2e_fetch_source_accepts_shopee_sheet(monkeypatch, tmp_path):
    def fake_fetch(**kwargs):
        return {
            "ok": True,
            "source": "shopee_sheet",
            "products": [
                {
                    "url": "https://shopee.vn/product-i.1.2",
                    "title": "Bàn chải đánh răng ba mặt cho bé",
                    "category": "mother_baby",
                    "price_vnd": 39000,
                    "discount_vnd": 39000,
                    "image_url": "https://img.example/p.jpg",
                    "merchant": "kingbabyvn",
                    "product_id": f"shortlink_domain={SHOPEE_SHORTLINK_DOMAIN}",
                }
            ],
        }

    monkeypatch.setattr(e2e_profit, "fetch_shopee_sheet_products", fake_fetch)
    report = e2e_profit._fetch_source(
        {"kind": "shopee_sheet", "name": "sheet", "sheet_id": "x", "gid": "1", "campaign_key": "SHOPEE"},
        tmp_path,
        cache_dir=tmp_path / "cache",
        cursor_path=tmp_path / "source-cursors.json",
    )

    assert report["ok"] is True
    assert report["requested_page"] is None
    assert report["campaign_key"] == "SHOPEE"
    assert report["products"][0]["url"].startswith("https://shopee.vn/")


def test_shopee_product_url_variants_dedup_by_shop_item_id():
    assert e2e_profit._norm_url("shopee.vn/product/729014007/17532975547?sp_atk=x") == "shopee:729014007:17532975547"
    assert e2e_profit._norm_url("https://shopee.vn/some-title-i.729014007.17532975547?x=1") == "shopee:729014007:17532975547"


def test_e2e_enrich_selected_media_uses_pdp_when_sheet_has_no_image(monkeypatch):
    from affilipilot.models import ProductCandidate

    def fake_enrich(url, **kwargs):
        assert url == "https://shopee.vn/product/1/2"
        return {
            "image_urls": ["https://down-vn.img.susercontent.com/file/test-image"],
            "media_source": "shopee_pdp",
            "media_confidence": "official",
        }

    monkeypatch.setattr(e2e_profit, "enrich_product_from_url", fake_enrich)
    item = {"product": ProductCandidate(url="https://shopee.vn/product/1/2", title="Khăn giấy cho gia đình", category="home_living")}

    selected, metrics = e2e_profit._enrich_selected_media([item])

    product = selected[0]["product"]
    assert metrics == {"attempted": 1, "updated": 1, "failed": 0, "skipped": 0}
    assert product.image_url == "https://down-vn.img.susercontent.com/file/test-image"
    assert product.media_source == "shopee_pdp"
    assert "pdp_media_enriched" in product.notes


def test_recent_selected_urls_can_dedup_main_profit_flow_batches(tmp_path):
    from affilipilot.db import AffiliPilotDB

    db_path = tmp_path / "affilipilot.db"
    AffiliPilotDB(db_path).save_batch(
        "profit-first-yesterday",
        "fixture",
        {"posts": [{"post_id": "old-post", "product": {"url": "https://shopee.vn/product/729014007/17532975547?old=1"}}]},
    )

    recent = e2e_profit._recent_selected_urls(db_path)

    assert "shopee:729014007:17532975547" in recent


def test_manual_e2e_batches_use_recent_duplicate_filter():
    assert e2e_profit._uses_recent_duplicate_filter("manual-e2e-20260610-094626") is True
    assert e2e_profit._uses_recent_duplicate_filter("auto-source-scheduled-20260610-0700") is True
    assert e2e_profit._uses_recent_duplicate_filter("adhoc-debug") is False


def test_fetch_source_rotates_shopee_sheet_cursor(monkeypatch, tmp_path):
    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "source": "shopee_sheet",
            "offset": kwargs["offset"],
            "limit": kwargs["limit"],
            "total_available": 5,
            "products": [{"url": f"https://shopee.vn/product/1/{kwargs['offset'] + 1}", "title": "Item", "price_vnd": 10000}],
        }

    cursor_path = tmp_path / "source-cursors.json"
    monkeypatch.setattr(e2e_profit, "fetch_shopee_sheet_products", fake_fetch)

    source = {"kind": "shopee_sheet", "name": "sheet", "sheet_id": "x", "gid": "1", "limit": 2, "campaign_key": "SHOPEE"}
    e2e_profit._fetch_source(source, tmp_path / "run1", cache_dir=tmp_path / "cache", cursor_path=cursor_path)
    e2e_profit._fetch_source(source, tmp_path / "run2", cache_dir=tmp_path / "cache", cursor_path=cursor_path)
    e2e_profit._fetch_source(source, tmp_path / "run3", cache_dir=tmp_path / "cache", cursor_path=cursor_path)

    assert [call["offset"] for call in calls] == [0, 2, 4]
    assert e2e_profit._load_source_cursors(cursor_path)["sheet"]["offset"] == 0

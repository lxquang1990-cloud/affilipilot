import json

from affilipilot.cli import main
from affilipilot.scanner.core import parse_price_vnd, parse_products_from_html, scan_result_to_input_lines, scan_url, write_scan_result
from affilipilot.workflows.scan_to_draft import draft_from_scan

SAMPLE_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Bình giữ nhiệt cho mẹ","image":"/img/a.jpg","url":"/binh-giu-nhiet","offers":{"@type":"Offer","price":"129000"}}
</script>
</head><body>
<a class="product" href="/khuyen-mai/yem-an-dam"><img src="/img/b.jpg" alt="Yếm ăn dặm silicone"/><span>79.000đ</span></a>
</body></html>
"""


def test_parse_price_vnd():
    assert parse_price_vnd("129.000đ") == 129000
    assert parse_price_vnd("Liên hệ") is None


def test_parse_products_from_html_jsonld_and_anchor():
    items = parse_products_from_html(SAMPLE_HTML, page_url="https://cellphones.com.vn/danh-sach-khuyen-mai", source="CELLPHONES", category="deal", limit=3)
    assert len(items) == 2
    assert items[0].title == "Bình giữ nhiệt cho mẹ"
    assert items[0].price_vnd == 129000
    assert items[0].url == "https://cellphones.com.vn/binh-giu-nhiet"
    assert items[1].title == "Yếm ăn dặm silicone"
    assert items[1].price_vnd == 79000


def test_scan_url_with_injected_html_and_write_lines(tmp_path):
    result = scan_url("https://cellphones.com.vn/danh-sach-khuyen-mai", source="CELLPHONES", category="deal", limit=2, html_text=SAMPLE_HTML)
    out = write_scan_result(result, tmp_path / "scan.json")
    lines = scan_result_to_input_lines(out)
    assert len(lines) == 2
    assert "category=deal" in lines[0]
    assert "price=129000" in lines[0]


def test_scan_draft_workflow(tmp_path):
    result = scan_url("https://cellphones.com.vn/danh-sach-khuyen-mai", source="CELLPHONES", category="deal", limit=2, html_text=SAMPLE_HTML)
    scan_path = write_scan_result(result, tmp_path / "scan.json")
    summary = draft_from_scan(scan_path, work_dir=tmp_path / "work", db_path=tmp_path / "db.sqlite", batch_key="scan-batch", outbox_path=tmp_path / "outbox.json", limit=2)
    assert summary["selected"] == 2
    assert summary["outbox_messages"] == 3


def test_scan_products_cli_with_file_url_monkeypatch(tmp_path, monkeypatch, capsys):
    import affilipilot.scanner.core as core

    monkeypatch.setattr(core, "fetch_html", lambda url, timeout=30: SAMPLE_HTML)
    code = main(["scan-products", "--url", "https://cellphones.com.vn/danh-sach-khuyen-mai", "--source", "CELLPHONES", "--category", "deal", "--out", str(tmp_path / "scan.json"), "--limit", "2"])
    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot scan-products: 2 items" in out
    data = json.loads((tmp_path / "scan.json").read_text(encoding="utf-8"))
    assert data["total"] == 2


def test_lazada_channel_scan_filters_navigation_links():
    html = """
    <a href="https://sellercenter.lazada.vn/apps/register/index">BÁN HÀNG CÙNG LAZADA</a>
    <a href="https://helpcenter.lazada.vn/s/faq">Trung tâm hỗ trợ</a>
    <a href="https://www.lazada.vn/tag/khan-sua-em-be/">Khăn sữa em bé</a>
    <a href="https://www.lazada.vn/products/khan-sua-cotton-i123-s456.html"><img src="https://img.lazcdn.com/product/khan.jpg" alt="Khăn sữa cotton mềm"/> 69.000đ</a>
    """
    items = parse_products_from_html(html, page_url="https://www.lazada.vn/tag/khan-sua-em-be/", source="LAZADA", category="baby_care", limit=5)
    assert len(items) == 1
    assert items[0].url == "https://www.lazada.vn/products/khan-sua-cotton-i123-s456.html"
    assert items[0].title == "Khăn sữa cotton mềm"
    assert items[0].price_vnd == 69000


def test_lazada_channel_scan_does_not_meta_fallback_to_channel_page():
    html = """
    <html><head><title>Khăn sữa em bé giá tốt | Lazada</title><meta property="og:image" content="https://lazada.vn/logo.png"></head>
    <body><a href="https://helpcenter.lazada.vn/s/faq">Trung tâm hỗ trợ</a></body></html>
    """
    items = parse_products_from_html(html, page_url="https://www.lazada.vn/tag/khan-sua-em-be/", source="LAZADA", category="baby_care", limit=5)
    assert items == []

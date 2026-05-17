import json
from pathlib import Path

from affilipilot.scanner.browser_plan import build_browser_scan_plan
from affilipilot.scanner.core import ScanResult, ScanSource, parse_products_from_html, scan_result_to_input_lines, write_scan_result


def test_jsonld_scan_lines_include_media_provenance(tmp_path):
    html = '''<script type="application/ld+json">{
      "@type":"Product","name":"Ghế ăn dặm","image":"https://img.lazcdn.com/media/catalog/product/ghe.jpg","offers":{"price":"299000"}
    }</script>'''
    items = parse_products_from_html(html, page_url="https://www.lazada.vn/products/ghe-i1-s2.html", source="LAZADA", category="feeding")
    out = write_scan_result(ScanResult(source=ScanSource(url="u", source="LAZADA", category="feeding"), fetched_at="now", items=items), tmp_path / "scan.json")
    lines = scan_result_to_input_lines(out)
    assert "media_source=jsonld_product_image" in lines[0]
    assert "media_confidence=high" in lines[0]


def test_browser_scan_plan_writes_json(tmp_path):
    path = tmp_path / "plan.json"
    plan = build_browser_scan_plan("https://www.lazada.vn/mother-baby/", source="LAZADA", category="feeding", out_path=path)
    data = json.loads(path.read_text())
    assert data["safety"] == "discovery_only_no_publish"
    assert "title" in data["extract_fields"]
    assert plan.url.startswith("https://")

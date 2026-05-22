import json
from datetime import date

from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ComplianceStatus, ProductCandidate
from affilipilot.workflows.daily_batch import build_batch


def test_generate_safe_facebook_draft_has_disclosure_and_passes():
    product = ProductCandidate(url="https://shopee.vn/a", title="Hộp chia sữa", category="feeding", price_vnd=99000)
    draft = generate_safe_facebook_draft(product)
    assert "tiếp thị liên kết" in draft.full_text.lower()
    assert draft.compliance.status == ComplianceStatus.PASS


def test_build_batch_outputs_manifest_and_cards(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("\n".join([
        "https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000",
        "https://shopee.vn/b | title=Vitamin tăng đề kháng | category=vitamin | price=299000",
    ]), encoding="utf-8")
    out_dir = tmp_path / "out"
    manifest = build_batch(input_file, out_dir, limit=2, day=date(2026, 5, 16))
    assert manifest["selected"] == 2
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "approval_batch_preview.txt").exists()
    data = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert data["posts"][0]["post_id"] == "post_20260516_001"
    assert data["posts"][0]["compliance"]["status"] == "pass"

def test_build_batch_reuses_conversion_tracking_post_id(tmp_path):
    input_file = tmp_path / "converted.txt"
    input_file.write_text(
        "https://go.isclix.com/deep | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | "
        "tracking_post_id=post_20260522_1419_gio-sap-xep_001 | tracking_product_id=gio-sap-xep | "
        "tracking_sub1=facebook | tracking_sub2=smartshopping | tracking_sub3=post_20260522_1419_gio-sap-xep_001 | tracking_sub4=gio-sap-xep\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    manifest = build_batch(input_file, out_dir, limit=1, day=date(2026, 5, 16))
    post = manifest["posts"][0]
    assert post["post_id"] == "post_20260522_1419_gio-sap-xep_001"
    assert post["utm"]["utm_content"] == "post_20260522_1419_gio-sap-xep_001"
    assert post["tracking"]["product_id"] == "gio-sap-xep"

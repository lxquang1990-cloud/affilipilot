from affilipilot.publishing.facebook import FacebookConfig
from affilipilot.publishing.facebook_plan import build_graph_payload, plan_facebook_batch, render_facebook_plan, _publish_text
from affilipilot.workflows.approval import create_approval_batch, decide_post


def test_build_graph_payload():
    graph = build_graph_payload(page_id="page", message="hello", link="https://example.com")
    assert graph["endpoint"] == "/page/feed"
    assert graph["payload"]["message"] == "hello"
    assert graph["payload"]["link"] == "https://example.com"


def test_facebook_plan_blocks_without_approval(tmp_path):
    input_file = tmp_path / "links.txt"
    input_file.write_text("https://shopee.vn/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    plan = plan_facebook_batch(db, batch_key="batch", out_path=tmp_path / "plan.json", config=FacebookConfig(page_id="page", page_access_token="token"))
    assert plan.publishable_count == 0
    assert "not_approved_by_snail" in plan.plans[0].reasons


def test_facebook_plan_publishable_after_approval(tmp_path):
    image_file = tmp_path / "product.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file = tmp_path / "links.txt"
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé tiện gọn | category=storage | price=129000 | image_path={image_file}", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan = plan_facebook_batch(db, batch_key="batch", out_path=tmp_path / "plan.json", config=FacebookConfig(page_id="page", page_access_token="token"))
    rendered = render_facebook_plan(plan)
    assert plan.publishable_count == 1
    assert plan.plans[0].endpoint == "/page/photos"
    assert "would POST" in rendered
    assert (tmp_path / "plan.json").exists()

def test_facebook_plan_blocks_market_fit_before_publish_safe(tmp_path):
    image_file = tmp_path / "product.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file = tmp_path / "links.txt"
    input_file.write_text(f"https://go.isclix.com/deep_link/a | title=Samsung Galaxy S26 Ultra | category=electronics | price=30490000 | image_path={image_file} | original_url=https://cellphones.com.vn/dien-thoai-samsung-galaxy-s26-ultra.html | media_source=product_card_image | media_confidence=high", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    (tmp_path / "drafts" / "post_20260516_001.post.txt").write_text("Một gợi ý nhỏ cho mẹ đang tìm đồ tiện dùng trong sinh hoạt hằng ngày với bé. Samsung Galaxy S26 Ultra. Bài viết có chứa link tiếp thị liên kết. #CellphoneSAffiliate", encoding="utf-8")
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan = plan_facebook_batch(db, batch_key="batch", out_path=tmp_path / "plan.json", config=FacebookConfig(page_id="page", page_access_token="token"))
    assert plan.publishable_count == 0
    assert any(reason.startswith("market_fit:") for reason in plan.plans[0].reasons)

def test_publish_text_prefers_manifest_caption_over_stale_post_text(tmp_path):
    stale_file = tmp_path / "stale.post.txt"
    stale_file.write_text("Nội dung cũ chỉ đáng mua nếu nó giải quyết đúng một việc cụ thể.", encoding="utf-8")
    post = {
        "caption": "Caption mới tự nhiên hơn cho sản phẩm.",
        "files": {"post_text": str(stale_file)},
    }
    text = _publish_text(post)
    assert text == "Caption mới tự nhiên hơn cho sản phẩm."
    assert "chỉ đáng mua" not in text

def test_publish_text_falls_back_to_post_text_for_legacy_batches(tmp_path):
    post_file = tmp_path / "post.txt"
    post_file.write_text("Caption legacy trong file", encoding="utf-8")
    assert _publish_text({"files": {"post_text": str(post_file)}}) == "Caption legacy trong file"

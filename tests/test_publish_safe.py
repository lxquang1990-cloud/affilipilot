import json

from affilipilot.cli import main
from affilipilot.publishing.safe_publish import validate_publish_safe
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post


def _write_plan(path, post_id="post_20260516_001", status="publishable_dry_run", endpoint="/page/photos", image_path="/tmp/product.jpg"):
    plan = {
        "batch_key": "batch",
        "plans": [
            {
                "post_id": post_id,
                "status": status,
                "endpoint": endpoint,
                "payload_preview": {"caption": "hello", "url": "https://go.isclix.com/x", "local_image_path": image_path},
            }
        ],
    }
    path.write_text(json.dumps(plan), encoding="utf-8")


def _create_ready_batch(tmp_path, db, *, text="Camera chụp con rõ hơn, pin dùng cả ngày, bộ nhớ rộng cho ảnh video gia đình. Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ.", url="https://go.isclix.com/deep_link/a"):
    image = tmp_path / "product.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    input_file = tmp_path / "links.txt"
    input_file.write_text(f"{url} | title=Samsung Galaxy S26 Ultra | category=electronics | price=30490000 | image_path={image} | original_url=https://cellphones.com.vn/dien-thoai-samsung-galaxy-s26-ultra.html | media_source=product_card_image | media_confidence=high", encoding="utf-8")
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    post_file = tmp_path / "drafts" / "post_20260516_001.post.txt"
    post_file.write_text(text, encoding="utf-8")
    return image


def _delivered_outbox(path):
    Outbox(path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])


def test_publish_safe_blocks_until_approval_delivery_and_plan_pass(tmp_path):
    db = tmp_path / "affilipilot.db"
    image = _create_ready_batch(tmp_path, db)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, image_path=str(image))
    outbox_path = tmp_path / "outbox.json"
    Outbox(outbox_path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="pending"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="pending"),
    ])

    result = validate_publish_safe(db_path=db, batch_key="batch", post_id="post_20260516_001", plan_path=plan_path, outbox_path=outbox_path)

    assert not result["ok"]
    assert "approval_not_approved:pending" in result["reasons"]
    assert any(reason.startswith("delivery_not_delivered") for reason in result["reasons"])


def test_publish_safe_check_only_passes_after_required_proofs(tmp_path, capsys):
    db = tmp_path / "affilipilot.db"
    image = _create_ready_batch(tmp_path, db)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, image_path=str(image))
    outbox_path = tmp_path / "outbox.json"
    _delivered_outbox(outbox_path)

    code = main([
        "publish-safe",
        "--check-only",
        "--db", str(db),
        "--batch-key", "batch",
        "--post-id", "post_20260516_001",
        "--plan", str(plan_path),
        "--outbox", str(outbox_path),
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert "Status: PASS" in out


def test_publish_safe_blocks_market_fit_mismatch_even_if_plan_passes(tmp_path):
    db = tmp_path / "affilipilot.db"
    image = _create_ready_batch(tmp_path, db, text="Một gợi ý nhỏ cho mẹ đang tìm đồ tiện dùng trong sinh hoạt hằng ngày với bé. Samsung Galaxy S26 Ultra. Bài viết có chứa link tiếp thị liên kết. #CellphoneSAffiliate")
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, image_path=str(image))
    outbox_path = tmp_path / "outbox.json"
    _delivered_outbox(outbox_path)

    result = validate_publish_safe(db_path=db, batch_key="batch", post_id="post_20260516_001", plan_path=plan_path, outbox_path=outbox_path)

    assert not result["ok"]
    assert "market_fit:generic_mother_baby_template_mismatch" in result["reasons"]
    assert "market_fit:missing_family_electronics_angle" in result["reasons"]


def test_publish_safe_blocks_demo_offer_even_if_plan_passes(tmp_path):
    db = tmp_path / "affilipilot.db"
    image = _create_ready_batch(tmp_path, db, url="https://go.isclix.com/deep_link/test-safe-mom-baby")
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, image_path=str(image))
    outbox_path = tmp_path / "outbox.json"
    _delivered_outbox(outbox_path)

    result = validate_publish_safe(db_path=db, batch_key="batch", post_id="post_20260516_001", plan_path=plan_path, outbox_path=outbox_path)

    assert not result["ok"]
    assert "offer:demo_or_test_offer_url" in result["reasons"]


def test_facebook_publish_one_uses_publish_safe_gate(tmp_path):
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, post_id="post_1")
    try:
        main([
            "facebook-publish-one",
            "--plan", str(plan_path),
            "--post-id", "post_1",
            "--db", str(tmp_path / "missing.db"),
            "--outbox", str(tmp_path / "missing-outbox.json"),
            "--batch-key", "batch",
        ])
    except SystemExit as exc:
        assert "publish-safe validation failed" in str(exc)
    else:
        raise AssertionError("facebook-publish-one should require publish-safe gate")

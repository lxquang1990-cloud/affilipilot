import json
from pathlib import Path

from affilipilot.cli import main
from affilipilot.publishing.safe_publish import render_publish_safe_validation, validate_publish_safe
from affilipilot.telegram.outbox import Outbox, OutboxMessage
from affilipilot.workflows.approval import create_approval_batch, decide_post


def _jpeg(path: Path, width: int = 900, height: int = 900) -> None:
    path.write_bytes(
        b"\xff\xd8"
        + b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def _write_plan(path: Path, *, post_id="post_20260516_001", status="publishable_dry_run", image_path=""):
    path.write_text(json.dumps({
        "batch_key": "batch",
        "plans": [{
            "post_id": post_id,
            "status": status,
            "endpoint": "/page/photos",
            "payload_preview": {
                "caption": "caption ready",
                "url": "https://go.isclix.com/x",
                "local_image_path": image_path,
            },
        }],
    }), encoding="utf-8")


def _delivered_outbox(path: Path):
    Outbox(path).save([
        OutboxMessage(id="batch:summary", kind="summary", text="summary", status="delivered", receipt="telegram:1:10"),
        OutboxMessage(id="batch:post_20260516_001", kind="approval_card", text="card", status="delivered", receipt="telegram:1:11"),
    ])


def _ready_batch(tmp_path, db, *, title="Kệ để đồ nhà bếp chịu lực kích thước rõ gọn góc bếp", category="storage", image_size=(900, 900)):
    image = tmp_path / "product.jpg"
    _jpeg(image, *image_size)
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        f"https://go.isclix.com/deep_link/a | title={title} | category={category} | price=199000 | image_path={image} | original_url=https://shopee.vn/ke-bep-i.1.2 | media_source=user_uploaded_image | media_confidence=high",
        encoding="utf-8",
    )
    create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    post_file = tmp_path / "drafts" / "post_20260516_001.post.txt"
    post_file.write_text(
        "Phù hợp với nhà bếp cần sắp xếp chai lọ và đồ dùng nhỏ cho gọn. "
        "Lý do đáng xem: kệ giúp gom đồ vào một chỗ, dễ lấy và giảm lộn xộn trên mặt bếp. "
        "Điểm kiểm chứng hiện có: giá tham khảo khoảng 199.000đ, có hình sản phẩm để đối chiếu. "
        "Trước khi chốt, nên kiểm tra: kích thước, tải trọng, chất liệu, cách lắp, ảnh review trong không gian thật. "
        "Lưu ý: đo góc định đặt trước khi mua; kiểm tra đánh giá shop và chính sách đổi trả. "
        "Bài viết có chứa link tiếp thị liên kết. Nếu bạn mua qua link, page có thể nhận hoa hồng nhỏ.",
        encoding="utf-8",
    )
    return image


def test_publish_safe_v2_passes_with_warning_for_trusted_small_media(tmp_path):
    db = tmp_path / "affilipilot.db"
    image = _ready_batch(tmp_path, db, image_size=(422, 422))
    # Make manifest media trusted PDP so small image is warning, not block.
    from affilipilot.db import AffiliPilotDB
    store = AffiliPilotDB(db)
    batch = store.get_batch("batch")
    post = batch["manifest"]["posts"][0]
    post["media"]["source"] = "shopee_pdp"
    post["media"]["confidence"] = "high"
    post["product"]["media_source"] = "shopee_pdp"
    post["product"]["media_confidence"] = "high"
    store.save_batch("batch", "manual", batch["manifest"])
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan = tmp_path / "plan.json"
    _write_plan(plan, image_path=str(image))
    outbox = tmp_path / "outbox.json"
    _delivered_outbox(outbox)

    result = validate_publish_safe(db_path=db, batch_key="batch", post_id="post_20260516_001", plan_path=plan, outbox_path=outbox)

    assert result["version"] == "publish-safe-v2"
    assert result["ok"]
    assert "media_image_small_but_trusted:422x422" in result["warnings"]
    rendered = render_publish_safe_validation(result)
    assert "publish-safe v2" in rendered
    assert "media: PASS_WITH_WARNING" in rendered


def test_publish_safe_v2_blocks_low_niche_even_if_legacy_plan_passes(tmp_path):
    db = tmp_path / "affilipilot.db"
    image = _ready_batch(tmp_path, db, title="Ốp xe máy trang trí anime random", category="bike_accessory")
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan = tmp_path / "plan.json"
    _write_plan(plan, image_path=str(image))
    outbox = tmp_path / "outbox.json"
    _delivered_outbox(outbox)

    result = validate_publish_safe(db_path=db, batch_key="batch", post_id="post_20260516_001", plan_path=plan, outbox_path=outbox)

    assert not result["ok"]
    assert any(reason.startswith("niche_score:") for reason in result["reasons"])
    assert any(check["name"] == "niche" and check["status"] == "block" for check in result["checks"])


def test_publish_safe_cli_renders_v2_checks(tmp_path, capsys):
    db = tmp_path / "affilipilot.db"
    image = _ready_batch(tmp_path, db)
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan = tmp_path / "plan.json"
    _write_plan(plan, image_path=str(image))
    outbox = tmp_path / "outbox.json"
    _delivered_outbox(outbox)

    code = main([
        "publish-safe", "--check-only",
        "--db", str(db), "--batch-key", "batch", "--post-id", "post_20260516_001",
        "--plan", str(plan), "--outbox", str(outbox),
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert "AffiliPilot publish-safe v2" in out
    assert "- approval: PASS" in out
    assert "- facebook_plan: PASS" in out


def test_publish_safe_accepts_video_description_caption(tmp_path):
    from affilipilot.publishing.publish_safe_v2 import _check_plan

    plan = tmp_path / "facebook-plan.json"
    plan.write_text(
        '{"plans":[{"post_id":"post_video","status":"publishable_dry_run","payload_preview":{"description":"Caption for video","url":"https://shorten.asia/x","local_video_path":"video.mp4"}}]}',
        encoding="utf-8",
    )
    check = _check_plan(plan, "post_video")
    assert check.status == "pass"

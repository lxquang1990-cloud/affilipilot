from pathlib import Path

from affilipilot.media import validate_image_path
from affilipilot.workflows.approval import create_approval_batch, decide_post
from affilipilot.publishing.facebook import FacebookConfig
from affilipilot.publishing.facebook_plan import plan_facebook_batch

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000100ffff030000060005"
    "57bfab0000000049454e44ae426082"
)


def test_validate_image_path(tmp_path):
    img = tmp_path / "p.png"
    img.write_bytes(PNG_1X1)
    result = validate_image_path(img)
    assert result.ok
    assert result.media_type == "png"


def test_batch_copies_media_into_manifest_and_photo_plan(tmp_path):
    img = tmp_path / "p.png"
    img.write_bytes(PNG_1X1)
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        f"https://go.isclix.com/deep_link/a | title=Giỏ sắp xếp đồ bé | category=storage | price=129000 | image_path={img}",
        encoding="utf-8",
    )
    db = tmp_path / "db.sqlite"
    manifest = create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="batch", limit=1)
    post = manifest["posts"][0]
    assert post["media"]["ok"] is True
    assert post["files"]["image"]
    decide_post(db, batch_key="batch", post_id="post_20260516_001", decision="approved")
    plan = plan_facebook_batch(db, batch_key="batch", out_path=tmp_path / "plan.json", config=FacebookConfig(page_id="page", page_access_token="token"))
    assert plan.publishable_count == 1
    assert plan.plans[0].endpoint == "/page/photos"
    assert plan.plans[0].payload_preview["local_image_path"]

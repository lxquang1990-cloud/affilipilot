from pathlib import Path

import pytest

from affilipilot.content.generator import generate_safe_facebook_draft, product_has_caption_inputs
from affilipilot.models import ProductCandidate
from affilipilot.telegram.delivery import queue_approval_batch
from affilipilot.workflows.approval import create_approval_batch
from affilipilot.workflows.daily_batch import build_batch


def test_missing_title_or_media_is_held_before_caption_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION", "0")
    product = ProductCandidate(
        url="https://go.isclix.com/deep_link/x",
        category="mother_baby",
        affiliate_url="https://go.isclix.com/deep_link/x",
        short_url="https://shorten.asia/abc123",
    )

    assert not product_has_caption_inputs(product)
    draft = generate_safe_facebook_draft(product)

    assert draft.full_text == ""
    assert draft.metadata["caption_source"] == "HELD_FOR_ENRICHMENT"
    assert draft.metadata["caption_quality_passed"] is False


def test_build_batch_holds_unenriched_product_and_does_not_write_approval_card(tmp_path, monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION", "0")
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        "https://go.isclix.com/deep_link/x | category=mother_baby | affiliate_url=https://go.isclix.com/deep_link/x | short_url=https://shorten.asia/abc123\n",
        encoding="utf-8",
    )

    manifest = build_batch(input_file, tmp_path / "drafts", limit=1)
    post = manifest["posts"][0]

    assert manifest["approval_eligible"] == 0
    assert manifest["held_for_enrichment"] == 1
    assert post["approval_eligible"] is False
    assert post["hold_reasons"] == ["missing_caption_inputs"]
    assert post["files"]["telegram_card"] == ""
    assert post["files"]["post_text"] == ""
    assert post["content_gate"]["caption_source"] == "HELD_FOR_ENRICHMENT"


def test_create_approval_batch_fails_closed_when_all_products_need_enrichment(tmp_path, monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION", "0")
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        "https://go.isclix.com/deep_link/x | category=mother_baby | affiliate_url=https://go.isclix.com/deep_link/x | short_url=https://shorten.asia/abc123\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="No approval-eligible products"):
        create_approval_batch(input_file, tmp_path / "drafts", tmp_path / "affilipilot.db", batch_key="prod-batch", limit=1)


def test_queue_approval_batch_skips_held_posts(tmp_path, monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION", "0")
    image = tmp_path / "real.jpg"
    image.write_bytes(b"fake")
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        "\n".join([
            "https://go.isclix.com/deep_link/held | category=mother_baby | affiliate_url=https://go.isclix.com/deep_link/held | short_url=https://shorten.asia/held",
            f"https://go.isclix.com/deep_link/ok | title=Khăn sữa cotton mềm cho bé | category=baby_care | image_path={image} | affiliate_url=https://go.isclix.com/deep_link/ok | short_url=https://shorten.asia/ok",
        ]) + "\n",
        encoding="utf-8",
    )
    db = tmp_path / "affilipilot.db"
    manifest = create_approval_batch(input_file, tmp_path / "drafts", db, batch_key="mixed-batch", limit=2)

    messages = queue_approval_batch(db, batch_key="mixed-batch", outbox_path=tmp_path / "outbox.json")

    assert manifest["approval_eligible"] == 1
    assert manifest["held_for_enrichment"] == 1
    assert [m.kind for m in messages].count("approval_card") == 1
    assert "Held for enrichment: 1" in messages[0].text

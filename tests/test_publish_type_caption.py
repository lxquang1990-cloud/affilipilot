from affilipilot.content.ai_caption import build_ai_caption_prompt
from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate
from affilipilot.telegram.approval_context import build_approval_context
from affilipilot.telegram.cards import render_approval_card


def _product(**kwargs):
    data = {
        "url": "https://shopee.vn/p",
        "title": "Cầu trượt gấp gọn cho bé trong nhà",
        "category": "baby_play",
        "price_vnd": 199000,
        "image_url": "https://img.example/p.jpg",
    }
    data.update(kwargs)
    return ProductCandidate(**data)


def test_ai_prompt_includes_publish_type_guidance():
    prompt = build_ai_caption_prompt(_product(video_path="/tmp/demo.mp4"), publish_type="reel", metrics_profile="reel")
    assert "Publish type: reel; metrics profile: reel." in prompt
    assert "Reel ngắn" in prompt
    assert "hook để trống" in prompt


def test_generator_passes_publish_type_to_ai(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    calls = []

    def fake_ai(product, **kwargs):
        calls.append(kwargs)
        class Result:
            ok = True
            hook = ""
            body = "Video ngắn giúp nhìn nhanh cách bé trượt và cất gọn trong nhà, hợp khi muốn có góc vận động nhỏ mà không chiếm nhiều chỗ."
            reason = "ai_caption_ok"
            provider = "test"
        return Result()

    monkeypatch.setattr("affilipilot.content.generator.generate_ai_caption", fake_ai)
    draft = generate_safe_facebook_draft(_product(video_path="/tmp/reel-demo.mp4"), publish_type="reel", metrics_profile="reel")

    assert calls[0]["publish_type"] == "reel"
    assert calls[0]["metrics_profile"] == "reel"
    assert draft.metadata["publish_type"] == "reel"
    assert draft.metadata["metrics_profile"] == "reel"
    assert any("publish_type=reel" in item for item in draft.metadata["ai_feedback"])


def test_approval_card_shows_publish_type():
    product = _product()
    draft = generate_safe_facebook_draft(product, prefer_ai=False, publish_type="photo_post", metrics_profile="feed_post")
    ctx = build_approval_context(draft, content_gate={"passed": True, "score": 0.8, "publish_type": "photo_post", "metrics_profile": "feed_post"})
    card = render_approval_card(draft, post_id="post1", batch_key="batch", context=ctx)
    assert "Publish type: photo_post/feed_post" in card

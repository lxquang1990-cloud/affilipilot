from affilipilot.content.regenerator import generate_until_content_gate_passes
from affilipilot.models import ContentDraft, ProductCandidate
from affilipilot.content.compliance import default_affiliate_disclosure, check_mom_baby_compliance
from affilipilot.workflows.daily_batch import build_batch


def test_regenerator_uses_gate_feedback_and_stops_after_pass(monkeypatch):
    monkeypatch.setenv("AFFILIPILOT_AI_CAPTION_JUDGE", "false")
    product = ProductCandidate(url="https://shopee.vn/p", title="Bình thìa ăn dặm silicone", category="feeding")
    calls = []

    def fake_generator(product, *, feedback=None):
        calls.append(feedback)
        if not feedback:
            hook = "Đang cân nhắc sản phẩm này?"
            body = "Đừng chỉ nhìn giá — hãy xem nó giải quyết nhu cầu nào của mình trước. Sản phẩm này phù hợp hơn khi nhu cầu, ngân sách và bối cảnh dùng thật sự rõ ràng."
        else:
            hook = "Đồ ăn dặm nên dễ vệ sinh, chất liệu rõ ràng và hợp tay bé khi dùng hằng ngày."
            body = "Bình thìa ăn dặm silicone phù hợp nếu cần món dễ rửa mỗi ngày. Trước khi chốt nên kiểm tra: chất liệu an toàn thực phẩm, dung tích, có tháo rời để vệ sinh không, bé cầm/nắm có tiện không, review ảnh thật. Giá/ưu đãi có thể thay đổi theo thời điểm, nên kiểm tra lại trước khi mua."
        cta = "Xem ảnh thật, review và giá hiện tại ở link bên dưới nhé 👇"
        disclosure = default_affiliate_disclosure()
        return ContentDraft(product, hook, body, cta, disclosure, check_mom_baby_compliance("\n\n".join([hook, body, cta, disclosure]), category=product.category))

    result = generate_until_content_gate_passes(product, max_regenerations=2, generator=fake_generator)
    assert result.gate.passed, result.gate.reasons
    assert result.regenerated_count == 1
    assert calls[0] is None
    assert calls[1]
    assert "gate_A:no.generic_template" in calls[1]


def test_build_batch_records_content_gate_attempts(tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"fake")
    input_file = tmp_path / "links.txt"
    input_file.write_text(
        f"https://shopee.vn/p | title=Bình thìa ăn dặm silicone cho bé | category=feeding | price=79000 | image_path={image} | media_source=product_card_image | media_confidence=high",
        encoding="utf-8",
    )
    manifest = build_batch(input_file, tmp_path / "drafts", limit=1)
    post = manifest["posts"][0]
    assert post["content_gate"]["passed"] is True
    assert "attempts" in post["content_gate"]
    assert post["content_gate"]["regenerated_count"] >= 0

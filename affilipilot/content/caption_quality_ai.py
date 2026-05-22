from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from affilipilot.content.ai_caption import DEFAULT_MODEL, _chat_completions_endpoint, _env
from affilipilot.models import ProductCandidate

MIN_AI_JUDGE_SCORE = 72

@dataclass
class CaptionQualityJudgeResult:
    passed: bool
    score: int
    reasons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    source: str = "deterministic"
    raw: str = ""


def ai_caption_judge_enabled() -> bool:
    value = (_env("AFFILIPILOT_AI_CAPTION_JUDGE") or "auto").lower()
    return value in {"1", "true", "yes", "on", "auto"} and bool(_env("9ROUTER_API_KEY"))


def _product_payload(product: ProductCandidate) -> dict[str, Any]:
    return {
        "title": product.title,
        "category": product.category,
        "price_vnd": product.price_vnd,
        "notes": product.notes,
        "has_image": bool(product.image_url or product.image_urls or product.image_path),
    }


def _deterministic_caption_quality(product: ProductCandidate, text: str) -> CaptionQualityJudgeResult:
    lower = text.lower()
    score = 100
    reasons: list[str] = []
    recommendations: list[str] = []
    mechanical_phrases = (
        "đủ để lọc bước đầu",
        "không nên mua chỉ vì nhìn ảnh đẹp",
        "không chỉ vì nhìn ảnh đẹp",
        "đừng chỉ nhìn giá",
        "nhu cầu, ngân sách và bối cảnh",
        "thông tin sản phẩm đủ rõ",
        "các thông tin chính đều rõ ràng",
    )
    for phrase in mechanical_phrases:
        if phrase in lower:
            score -= 18
            reasons.append(f"mechanical_phrase:{phrase}")
            recommendations.append("Rewrite phrases that sound like internal evaluation notes into natural buyer language.")
    text_before_disclosure = lower.split("link affiliate", 1)[0].split("bài viết có link tiếp thị liên kết", 1)[0]
    if len(text_before_disclosure) > 520:
        score -= 18
        reasons.append("caption_too_long")
        recommendations.append("Shorten caption to one value paragraph plus CTA.")
    elif len(text_before_disclosure) > 420:
        score -= 8
        reasons.append("caption_slightly_long")
        recommendations.append("Trim to the ultra-short house style.")
    if len(re.findall(r"kiểm tra|check|xem kỹ|trước khi chốt|lưu ý rủi ro", lower)) >= 3:
        score -= 12
        reasons.append("too_checklist_heavy")
        recommendations.append("Remove long checklist wording; keep only one practical note if needed.")
    for phrase in ("hiện data", "ưu tiên xem tiếp", "lọc bước đầu", "điểm kiểm chứng hiện có"):
        if phrase in lower:
            score -= 12
            reasons.append(f"internal_evaluation_phrase:{phrase}")
            recommendations.append("Use buyer-facing language instead of internal scoring/evaluation language.")
    if not re.search(r"[😅🙂👇✨]|\bnhà\b|góc|bếp|phòng tắm|mẹ|bé", lower):
        score -= 8
        reasons.append("weak_human_context")
        recommendations.append("Add a lived-in household context or natural hook.")
    if "<provider" in lower or "<povider" in lower:
        score -= 40
        reasons.append("provider_placeholder_not_resolved")
        recommendations.append("Resolve provider name from URL/marketplace before rendering caption.")
    if "giá tham khảo trên" not in lower and product.price_vnd:
        score -= 8
        reasons.append("missing_provider_price_phrase")
        recommendations.append("Use buyer-facing price phrase: Giá tham khảo trên <provider> khoảng <price>đ.")
    if not any(term in lower for term in ("đáng xem", "hợp với", "phù hợp", "giúp", "gọn", "tiện")):
        score -= 8
        reasons.append("weak_purchase_angle")
        recommendations.append("Make the product value proposition clearer.")
    score = max(0, min(100, score))
    return CaptionQualityJudgeResult(
        passed=score >= MIN_AI_JUDGE_SCORE,
        score=score,
        reasons=reasons,
        recommendations=list(dict.fromkeys(recommendations)),
        source="deterministic",
    )


def build_caption_quality_prompt(product: ProductCandidate, text: str) -> str:
    return "\n".join([
        "Bạn là editor trưởng cho Facebook affiliate page tiếng Việt.",
        "Hãy chấm caption theo mục tiêu: tự nhiên, cụ thể, ngắn gọn, có khả năng bán hàng, không sáo rỗng, không nghe như checklist nội bộ.",
        "Positioning page: Đồ dùng gia đình nhỏ, tiện, an toàn, đáng tiền.",
        "Chấm 0-100. PASS nếu >=72 và không có lỗi nghiêm trọng.",
        "Phạt nặng nếu caption có cụm máy móc như: 'đủ để lọc bước đầu', 'không nên mua chỉ vì nhìn ảnh đẹp', 'đừng chỉ nhìn giá', 'nhu cầu, ngân sách và bối cảnh'.",
        "Phạt nếu caption dài hơn cần thiết, quá checklist BA, có cụm 'hiện data', 'ưu tiên xem tiếp', 'lọc bước đầu', thiếu hook đời thường, hoặc thiếu lý do mua cụ thể.",
        "Không yêu cầu caption phải hype; ưu tiên trust + conversion. Caption tốt thường chỉ cần 1 đoạn value 1-2 câu + câu giá theo provider + CTA.",
        "Trả về JSON hợp lệ duy nhất với keys: passed(boolean), score(number), reasons(array string), recommendations(array string).",
        "",
        "Product JSON:",
        json.dumps(_product_payload(product), ensure_ascii=False),
        "",
        "Caption:",
        text,
    ])


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def judge_caption_quality(product: ProductCandidate, text: str, *, timeout: int = 35) -> CaptionQualityJudgeResult:
    fallback = _deterministic_caption_quality(product, text)
    if not ai_caption_judge_enabled():
        return fallback
    api_key = _env("9ROUTER_API_KEY")
    endpoint = _chat_completions_endpoint(_env("9ROUTER_API_ENDPOINT"))
    model = _env("AFFILIPILOT_AI_CAPTION_JUDGE_MODEL") or _env("AFFILIPILOT_AI_CAPTION_MODEL") or DEFAULT_MODEL
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 500,
        "messages": [
            {"role": "system", "content": "Bạn chỉ trả về JSON hợp lệ. Không markdown."},
            {"role": "user", "content": build_caption_quality_prompt(product, text)},
        ],
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extract_json(content)
        score = int(float(parsed.get("score", fallback.score)))
        reasons = [str(item) for item in parsed.get("reasons", [])][:8]
        recommendations = [str(item) for item in parsed.get("recommendations", [])][:8]
        passed = bool(parsed.get("passed", score >= MIN_AI_JUDGE_SCORE)) and score >= MIN_AI_JUDGE_SCORE
        # Deterministic safety floor: known bad mechanical phrases can still block even if judge is lenient.
        if not fallback.passed:
            passed = False
            score = min(score, fallback.score)
            reasons = list(dict.fromkeys(reasons + fallback.reasons))
            recommendations = list(dict.fromkeys(recommendations + fallback.recommendations))
        return CaptionQualityJudgeResult(passed=passed, score=max(0, min(100, score)), reasons=reasons, recommendations=recommendations, source="ai", raw=content)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:160]
        fallback.reasons.append(f"ai_judge_http_error:{exc.code}:{detail}")
        fallback.source = "deterministic_fallback"
        return fallback
    except Exception as exc:  # noqa: BLE001
        fallback.reasons.append(f"ai_judge_error:{type(exc).__name__}:{str(exc)[:80]}")
        fallback.source = "deterministic_fallback"
        return fallback

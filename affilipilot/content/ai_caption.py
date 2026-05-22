from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from urllib.parse import urlparse, urlunparse

from affilipilot.config import DEFAULT_SECRET_PATH, load_env_file
from affilipilot.content.caption_planner import build_caption_plan
from affilipilot.models import ProductCandidate

DEFAULT_MODEL = "Tier1"
DEFAULT_ENDPOINT = "https://api.9router.com/v1/chat/completions"

@dataclass
class AICaptionResult:
    ok: bool
    hook: str = ""
    body: str = ""
    reason: str = ""
    raw: str = ""
    provider: str = "9router"


def _env(name: str) -> str:
    env_file = load_env_file(DEFAULT_SECRET_PATH)
    return os.environ.get(name) or env_file.get(name, "")


def ai_caption_enabled() -> bool:
    value = (_env("AFFILIPILOT_AI_CAPTION") or "auto").lower()
    return value in {"1", "true", "yes", "on", "auto"} and bool(_env("9ROUTER_API_KEY"))


def _product_payload(product: ProductCandidate) -> dict[str, Any]:
    return {
        "title": product.title,
        "category": product.category,
        "price_vnd": product.price_vnd,
        "notes": product.notes,
        "url_host": product.url.split("/")[2] if product.url.startswith("http") and len(product.url.split("/")) > 2 else "",
        "has_image": bool(product.image_url or product.image_urls or product.image_path),
        "has_video": bool(product.video_url or product.video_urls or product.video_path),
    }


def build_ai_caption_prompt(product: ProductCandidate, *, feedback: list[str] | None = None) -> str:
    plan = build_caption_plan(product)
    return "\n".join([
        "Bạn là copywriter affiliate tiếng Việt cho hệ thống mua sắm thông minh, không neo vào một page/niche cụ thể.",
        "Mục tiêu: viết caption cực ngắn, tự nhiên, cụ thể, không sáo rỗng.",
        "Positioning: Mua sắm thông minh — món nhỏ, tiện, đáng tiền, dễ kiểm chứng.",
        "Format bắt buộc: hook để trống; body chỉ 1 câu duy nhất, khoảng 90-180 ký tự, nêu lợi ích/situation chính của sản phẩm.",
        "Bắt buộc:",
        "- Không bịa claim, không claim y tế/sức khỏe/giảm cân/phát triển trẻ.",
        "- Không dùng hashtag nội bộ như #tiepthilienket #shopeeaffiliate #lazadaaffiliate.",
        "- Không dùng câu generic: 'đừng chỉ nhìn giá', 'nhu cầu, ngân sách và bối cảnh', 'thông tin sản phẩm đủ rõ'.",
        "- Caption phải cực ngắn: hook bắt buộc để trống; body đúng 1 câu. CTA/disclosure/hashtag do hệ thống thêm. Không viết checklist.",
        "- Body không quá 180 ký tự; không bê nguyên title marketplace dài/spam vào caption.",
        "- Nếu là đồ cho bé/đồ vận động trẻ em: không viết warning/checklist dài kiểu 'Trước khi mua...', 'luôn để người lớn...'. Chỉ viết benefit tự nhiên, ngắn gọn; safety để hệ thống kiểm duyệt riêng.",
        "- Không tự viết câu giá/provider/link. Hệ thống sẽ thêm template cố định sau caption.",
        "- Giọng: người thật gợi ý mua thông minh, ấm, cụ thể; không quảng cáo quá; không giống BA/checklist nội bộ.",
        "- Không đưa link vào hook/body; không tự viết CTA/disclosure/hashtag. Hệ thống sẽ thêm dòng giá + link affiliate riêng.",
        "- Không dùng các câu: 'Trước khi mua nên xem kỹ...', 'nhớ xem kỹ kích thước...', 'luôn để người lớn ở cạnh/quan sát khi bé chơi'.",
        "Trả về JSON hợp lệ duy nhất với keys: hook, body.",
        "Hook bắt buộc là chuỗi rỗng. Body 90-180 ký tự, đúng 1 câu. Tổng caption trước CTA chỉ gồm body.",
        "",
        "Feedback từ các gate trước đó — bắt buộc sửa nếu có:",
        json.dumps(feedback or [], ensure_ascii=False),
        "",
        "Product JSON:",
        json.dumps(_product_payload(product), ensure_ascii=False),
        "",
        "Caption plan:",
        json.dumps({
            "audience": plan.audience,
            "why_buy": plan.why_buy,
            "proof_points": list(plan.proof_points),
            "buying_checks": list(plan.buying_checks),
            "risk_notes": list(plan.risk_notes),
            "angle": plan.angle,
        }, ensure_ascii=False),
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


def _chat_completions_endpoint(endpoint: str) -> str:
    endpoint = (endpoint or DEFAULT_ENDPOINT).rstrip("/")
    parsed = urlparse(endpoint)
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        return endpoint
    if path.endswith("/v1"):
        path = path + "/chat/completions"
    elif path:
        path = path + "/v1/chat/completions"
    else:
        path = "/v1/chat/completions"
    return urlunparse(parsed._replace(path=path))


def generate_ai_caption(product: ProductCandidate, *, feedback: list[str] | None = None, timeout: int = 35) -> AICaptionResult:
    if not ai_caption_enabled():
        return AICaptionResult(False, reason="ai_caption_disabled_or_missing_key")
    api_key = _env("9ROUTER_API_KEY")
    endpoint = _chat_completions_endpoint(_env("9ROUTER_API_ENDPOINT") or DEFAULT_ENDPOINT)
    model = _env("AFFILIPILOT_AI_CAPTION_MODEL") or DEFAULT_MODEL
    payload = {
        "model": model,
        "temperature": 0.75,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": "Bạn chỉ trả về JSON hợp lệ. Không markdown. Key hook phải là chuỗi rỗng; body đúng 1 câu ngắn."},
            {"role": "user", "content": build_ai_caption_prompt(product, feedback=feedback)},
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
        hook = str(parsed.get("hook", "")).strip()
        body = str(parsed.get("body", "")).strip()
        if not body:
            return AICaptionResult(False, reason="ai_caption_missing_body", raw=content)
        return AICaptionResult(True, hook=hook, body=body, raw=content)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        return AICaptionResult(False, reason=f"ai_caption_http_error:{exc.code}:{detail}")
    except Exception as exc:  # noqa: BLE001 - generation must never block deterministic fallback
        return AICaptionResult(False, reason=f"ai_caption_error:{type(exc).__name__}:{str(exc)[:120]}")

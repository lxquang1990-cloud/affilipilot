from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.content.product_quality import evaluate_product_content


@dataclass
class GateCheck:
    id: str
    passed: bool
    weight: float = 1.0
    blocker: bool = False
    evidence: str = ""
    recommendation: str = ""


@dataclass
class GateLayerResult:
    layer: str
    passed: bool
    score: float
    checks: list[GateCheck] = field(default_factory=list)


@dataclass
class ContentGateResult:
    passed: bool
    score: float
    layers: list[GateLayerResult] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def layer(self, name: str) -> GateLayerResult | None:
        for item in self.layers:
            if item.layer == name:
                return item
        return None


def _score(checks: list[GateCheck]) -> float:
    total = sum(check.weight for check in checks) or 1.0
    earned = sum(check.weight for check in checks if check.passed)
    return round(earned / total, 3)


def _layer(layer: str, checks: list[GateCheck], threshold: float) -> GateLayerResult:
    score = _score(checks)
    blocker_failed = any(check.blocker and not check.passed for check in checks)
    return GateLayerResult(layer=layer, passed=score >= threshold and not blocker_failed, score=score, checks=checks)


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _category_specific_check(product: dict[str, Any], text: str) -> GateCheck:
    category = str(product.get("category", "")).lower()
    title = str(product.get("title", "")).lower()
    lower = text.lower()
    combined = f"{category} {title} {lower}"

    if category == "feeding" or _has_any(combined, ("ăn dặm", "bình thìa", "bình sữa", "yếm")):
        terms = ("ăn dặm", "vệ sinh", "chất liệu", "dễ rửa", "dung tích", "tháo rời", "an toàn thực phẩm")
        return GateCheck("category_specific.feeding", _has_any(lower, terms), 1.3, True, "feeding needs material/cleaning/size context", "Rewrite with material, cleaning, size/capacity, and real-use review context.")
    if category == "storage" or _has_any(combined, ("giỏ", "hộp đựng", "kệ", "sắp xếp", "organizer")):
        terms = ("gọn", "sắp xếp", "kích thước", "tải trọng", "chất liệu", "lắp", "treo", "đồ nhỏ", "review")
        return GateCheck("category_specific.storage", _has_any(lower, terms), 1.3, True, "storage needs real organization context", "Rewrite with real storage use case, dimensions/load/material/install/review-photo checks.")
    if category in {"baby_care", "mother_baby"} or _has_any(combined, ("khăn sữa", "khăn xô", "khăn muslin")):
        terms = ("mềm", "cotton", "muslin", "sợi tre", "thấm", "bụi vải", "giặt", "da bé", "lau")
        return GateCheck("category_specific.baby_care", _has_any(lower, terms), 1.3, True, "baby-care needs material/skin/usage context", "Rewrite with softness, material, absorbency, washing, lint, and baby-skin fit.")
    if category in {"home_appliance", "home_living"}:
        terms = ("công suất", "dung tích", "kích thước", "độ ồn", "bảo hành", "đổi trả", "review", "đánh giá")
        return GateCheck("category_specific.home_appliance", _has_any(lower, terms), 1.2, True, "home appliance needs spec/warranty/review context", "Rewrite with capacity/power/size/noise/warranty/review-photo checks.")
    if category in {"electronics", "phone", "smartphone", "laptop", "computer"}:
        terms = ("pin", "bộ nhớ", "cấu hình", "bảo hành", "camera", "dung lượng", "làm việc", "học tập")
        return GateCheck("category_specific.electronics", _has_any(lower, terms), 1.2, True, "electronics needs practical spec rationale", "Rewrite with battery/storage/camera/config/warranty/practical usage rationale.")
    return GateCheck("category_specific.generic", _has_any(lower, ("kích thước", "chất liệu", "cách dùng", "review", "đánh giá", "đổi trả")), 1.0, False, "generic products need concrete buying facts", "Add product-specific use case and buying checklist.")


def evaluate_content_gates(product: dict[str, Any], text: str) -> ContentGateResult:
    lower = text.lower()
    product_result = evaluate_product_content(product, text)
    market_result = evaluate_market_fit(product, text)

    gate_a = _layer("A", [
        GateCheck("text.min_length", len(text.strip()) >= 150, 1.0, True, f"length={len(text.strip())}", "Add use case, buying checklist, and CTA."),
        GateCheck("disclosure.present", "tiếp thị liên kết" in lower or "hoa hồng" in lower, 1.0, True, "affiliate disclosure required", "Add plain-language affiliate disclosure."),
        GateCheck("no.internal_hashtag", "#tiepthilienket" not in lower and "#shopeeaffiliate" not in lower and "#lazadaaffiliate" not in lower, 1.0, True, "internal hashtags must not be public", "Remove internal affiliate/network hashtags."),
        GateCheck("no.generic_template", not any(p in lower for p in ("đừng chỉ nhìn giá", "nhu cầu, ngân sách và bối cảnh", "sản phẩm này phù hợp hơn khi nhu cầu")), 1.2, True, "generic AI affiliate phrases are blocked", "Rewrite from product archetype, not generic template."),
    ], threshold=1.0)

    gate_b = _layer("B", [
        GateCheck("product_quality.pass", product_result.passed, 1.5, True, ",".join(product_result.reasons), "; ".join(product_result.recommendations)),
        _category_specific_check(product, text),
        GateCheck("market_fit.pass", market_result.passed, 1.0, False, ",".join(market_result.reasons), "Keep only products/copy fitting the target page audience."),
    ], threshold=0.82)

    gate_c = _layer("C", [
        GateCheck("ready.no_blockers", gate_a.passed and gate_b.passed, 2.0, True, "Gate A and B must pass", "Do not send to Telegram approval until Gate A/B pass."),
        GateCheck("ready.clear_cta", ("link" in lower and ("xem" in lower or "kiểm tra" in lower)) or "tiếp thị liên kết" in lower, 0.8, False, "CTA should be visible", "Add clear CTA to review photos, price, and product page."),
        GateCheck("ready.no_unsafe_claims", not any(term in lower for term in ("điều trị", "chữa", "tăng đề kháng", "giảm cân", "tăng chiều cao")), 1.2, True, "unsafe claims blocked", "Remove medical/body-change claims."),
    ], threshold=0.9)

    layers = [gate_a, gate_b, gate_c]
    reasons: list[str] = []
    recommendations: list[str] = []
    for layer in layers:
        for check in layer.checks:
            if not check.passed:
                reasons.append(f"gate_{layer.layer}:{check.id}")
                if check.recommendation:
                    recommendations.append(check.recommendation)
    score = round(min(layer.score for layer in layers), 3)
    return ContentGateResult(
        passed=all(layer.passed for layer in layers),
        score=score,
        layers=layers,
        reasons=reasons,
        recommendations=list(dict.fromkeys(recommendations)),
    )

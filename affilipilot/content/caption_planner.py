from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from affilipilot.models import ProductCandidate

HOUSEHOLD_POSITIONING = "Đồ dùng gia đình nhỏ, tiện, an toàn, đáng tiền."

@dataclass(frozen=True)
class CaptionPlan:
    audience: str
    why_buy: str
    proof_points: tuple[str, ...] = field(default_factory=tuple)
    risk_notes: tuple[str, ...] = field(default_factory=tuple)
    buying_checks: tuple[str, ...] = field(default_factory=tuple)
    angle: str = "practical_household_value"


def _text(product: ProductCandidate) -> str:
    return f"{product.title} {product.category} {product.notes} {product.url}".lower()


def _note_number(product: ProductCandidate, key: str) -> float | None:
    match = re.search(rf"(?:^|;){re.escape(key)}=([0-9]+(?:\.[0-9]+)?)", product.notes.lower())
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _format_count(value: float) -> str:
    if value >= 1000:
        return f"{int(value // 1000)}k+"
    return str(int(value))


def _price_proof(product: ProductCandidate) -> tuple[str, ...]:
    points: list[str] = []
    if product.price_vnd:
        points.append(f"giá tham khảo khoảng {product.price_vnd:,}đ".replace(",", "."))
    notes = product.notes.lower()
    if "discount_rate=" in notes:
        raw = notes.split("discount_rate=", 1)[1].split(";", 1)[0].split(" ", 1)[0]
        try:
            rate = float(raw)
            if rate <= 1:
                rate *= 100
            if rate >= 10:
                points.append(f"đang có giảm khoảng {rate:.0f}% theo data hiện tại")
        except ValueError:
            pass
    elif "discount_vnd=" in notes:
        points.append("đang có ưu đãi theo data hiện tại")
    return tuple(points)


def _social_proof(product: ProductCandidate) -> tuple[str, ...]:
    rating = _note_number(product, "rating")
    sold = _note_number(product, "sold") or _note_number(product, "historical_sold")
    reviews = _note_number(product, "review_count")
    points: list[str] = []
    if rating and rating >= 4.7:
        points.append(f"rating khoảng {rating:.1f}/5")
    if sold and sold >= 100:
        points.append(f"{_format_count(sold)} lượt bán")
    if reviews and reviews >= 30:
        points.append(f"{_format_count(reviews)} đánh giá")
    return tuple(points)


def _merchant_risk(product: ProductCandidate) -> str:
    text = _text(product)
    host = urlparse(product.tracking_url or product.affiliate_url or product.url).netloc.lower()
    if "shopee" in text or "shopee" in host:
        return "ưu tiên shop Mall/Shop yêu thích, lượt bán thật và đánh giá có ảnh"
    if "lazada" in text or "lazada" in host:
        return "kiểm tra đánh giá shop, bảo hành và chính sách đổi trả trên Lazada"
    if "tiki" in text or "tiki" in host:
        return "kiểm tra nhãn official/Tiki Trading và thời gian giao hàng"
    return "kiểm tra đánh giá shop, ảnh thật và chính sách đổi trả"


def _base_proof(product: ProductCandidate) -> tuple[str, ...]:
    points = list(_price_proof(product)) + list(_social_proof(product))
    if product.image_url or product.image_urls or product.image_path:
        points.append("có hình sản phẩm để đối chiếu trước khi mua")
    return tuple(points[:4])


def build_caption_plan(product: ProductCandidate) -> CaptionPlan:
    category = (product.category or "unknown").lower()
    text = _text(product)
    proof = list(_base_proof(product))
    merchant_risk = _merchant_risk(product)

    if category == "storage" or any(term in text for term in ("kệ", "hộp đựng", "giỏ", "sắp xếp", "lưu trữ")):
        return CaptionPlan(
            audience="nhà cần sắp xếp đồ nhỏ, góc bếp/phòng tắm/góc đồ bé cho gọn hơn",
            why_buy="giúp gom đồ vào một chỗ dễ lấy, giảm cảnh đồ nhỏ nằm rải rác quanh nhà",
            proof_points=tuple(proof),
            risk_notes=("đo kích thước góc định đặt trước khi mua", merchant_risk),
            buying_checks=("kích thước", "tải trọng", "chất liệu", "cách lắp/treo", "ảnh review trong không gian thật"),
            angle="tidy_household_storage",
        )
    if any(term in text for term in ("khăn giấy", "giấy ăn", "giấy rút", "tissue", "khăn ăn")):
        return CaptionPlan(
            audience="nhà dùng khăn giấy nhiều ở bàn ăn, bếp, xe hoặc túi đi chơi",
            why_buy="tiện lau tay, lau miệng và xử lý vết đổ nhỏ trong ngày mà không phải chạy đi tìm khăn",
            proof_points=tuple(proof),
            risk_notes=("xem review khi lau ướt nhẹ để tránh loại dễ rã hoặc bụi giấy nhiều", merchant_risk),
            buying_checks=("số tờ/lớp giấy", "độ mềm", "ít bụi giấy", "độ dai", "đóng gói dễ rút"),
            angle="household_tissue_daily_use",
        )
    if category in {"home_appliance", "home_living"} or any(term in text for term in ("máy hút bụi", "máy xay", "nồi chiên", "bình giữ nhiệt", "hộp cơm", "đèn", "ổ cắm")):
        return CaptionPlan(
            audience="nhà muốn một món hỗ trợ việc sinh hoạt lặp lại hằng ngày",
            why_buy="đáng cân nhắc khi nó tiết kiệm thời gian, giảm thao tác hoặc làm góc nhà tiện hơn thật",
            proof_points=tuple(proof),
            risk_notes=("đối chiếu thông số với nhu cầu thật, đừng mua chỉ vì đang sale", merchant_risk),
            buying_checks=("công suất/dung tích", "kích thước", "độ ồn nếu có", "bảo hành", "review sau vài tuần dùng"),
            angle="small_home_utility",
        )
    if category in {"electronics", "phone", "smartphone", "laptop", "computer", "phone_accessory", "office_productivity"}:
        return CaptionPlan(
            audience="người cần món công nghệ phục vụ làm việc, học tập hoặc thay thế đúng thông số",
            why_buy="chỉ đáng mua khi thông số khớp nhu cầu thật như điện áp, công suất, pin, dung lượng hoặc bảo hành",
            proof_points=tuple(proof),
            risk_notes=("kiểm tra đúng model/thông số trước khi chốt", merchant_risk),
            buying_checks=("thông số chính", "bảo hành", "độ tương thích", "ảnh/review thật", "so sánh giá 1-2 shop"),
            angle="practical_electronics_checklist",
        )
    if category in {"feeding", "baby_care", "mother_baby", "toy", "baby_play"}:
        return CaptionPlan(
            audience="gia đình có bé, cần món dùng thường xuyên nhưng vẫn phải dễ vệ sinh và an toàn khi dùng",
            why_buy="nên chọn theo tần suất dùng thật, chất liệu, độ dễ vệ sinh và review từ người mua trước",
            proof_points=tuple(proof),
            risk_notes=("không kỳ vọng công dụng sức khỏe/phát triển nếu thông tin không kiểm chứng rõ", merchant_risk),
            buying_checks=("chất liệu", "kích thước/dung tích", "dễ vệ sinh", "bo cạnh/độ mềm", "review ảnh thật"),
            angle="safe_daily_family_use",
        )
    return CaptionPlan(
        audience="người muốn mua có kiểm soát, ưu tiên món tiện dụng và thông tin rõ",
        why_buy="chỉ nên cân nhắc nếu công dụng, chất liệu/kích thước và review thật đủ rõ để so sánh",
        proof_points=tuple(proof),
        risk_notes=("bỏ qua nếu mô tả mơ hồ hoặc ảnh/review thật không đủ", merchant_risk),
        buying_checks=("công dụng", "kích thước", "chất liệu", "ảnh/review thật", "đổi trả"),
        angle="controlled_smart_shopping",
    )


def render_caption_body_v2(product: ProductCandidate, name: str, plan: CaptionPlan) -> str:
    proof = "; ".join(plan.proof_points) if plan.proof_points else "thông tin sản phẩm cần được kiểm tra lại trên trang bán"
    checks = ", ".join(plan.buying_checks)
    risks = "; ".join(plan.risk_notes)
    body = (
        f"Phù hợp với {plan.audience}. "
        f"Lý do đáng xem: {plan.why_buy}. "
        f"Điểm kiểm chứng hiện có: {proof}. "
        f"Trước khi chốt, nên kiểm tra: {checks}. "
        f"Lưu ý: {risks}."
    )
    return re.sub(r"\s+", " ", body).strip()


def render_hook_v2(product: ProductCandidate, name: str, plan: CaptionPlan) -> str:
    if plan.angle == "tidy_household_storage":
        return f"{name} đáng xem nếu bạn đang muốn góc nhà gọn hơn mà đồ vẫn dễ lấy."
    if plan.angle == "household_tissue_daily_use":
        return f"{name}: món nhỏ nhưng nhà dùng hằng ngày, nhất là ở bàn ăn, bếp hoặc khi ra ngoài."
    if plan.angle == "small_home_utility":
        return f"{name} chỉ đáng mua khi nó làm việc nhà nhẹ hơn thật, không chỉ vì đang sale."
    if plan.angle == "practical_electronics_checklist":
        return f"{name}: trước khi mua nên kiểm đúng thông số, bảo hành và độ tương thích."
    if plan.angle == "safe_daily_family_use":
        return f"{name} nên chọn theo chất liệu, cách vệ sinh và tần suất dùng thật trong nhà."
    return f"{name}: mua thông minh là nhìn công dụng thật, bằng chứng và rủi ro trước khi chốt."

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from affilipilot.content.compliance import default_affiliate_disclosure
from affilipilot.content.market_fit import evaluate_market_fit
from affilipilot.models import ProductCandidate

@dataclass
class ContentVariant:
    variant_id: str
    angle: str
    text: str
    score: int
    passed: bool
    reasons: list[str]

def _price(product: ProductCandidate) -> str:
    if product.price_vnd:
        return f"{product.price_vnd:,}".replace(",", ".") + "đ"
    return "xem giá hiện tại"

def generate_content_variants(product: ProductCandidate, *, audience: str = "smart_shopping") -> list[ContentVariant]:
    name = product.title or "sản phẩm này"
    disclosure = default_affiliate_disclosure()
    category = product.category.lower()
    variants: list[tuple[str, str]]
    if category in {"electronics", "phone", "smartphone"} or any(term in name.lower() for term in ("samsung", "galaxy", "iphone", "xiaomi", "điện thoại")):
        variants = [
            ("family_camera", f"📸 Mẹ hay chụp ảnh con mà ảnh mờ hoặc thiếu sáng?\n\n{name} đáng cân nhắc nếu mẹ cần camera tốt để lưu khoảnh khắc của con, quay video rõ hơn và có pin đủ cho một ngày dài. Giá tham khảo: {_price(product)}.\n\n👇 Xem chi tiết, màu và chính sách bảo hành ở link bên dưới.\n{disclosure}\n#samsung #reviewdienthoai #congnghe2025 #giadinh"),
            ("storage_memory", f"Ảnh và video của con lớn lên rất nhanh — máy đầy bộ nhớ cũng nhanh không kém.\n\n{name} phù hợp với người cần bộ nhớ rộng, pin khỏe và camera ổn định để lưu ảnh/video gia đình. Nên so sánh dung lượng, bảo hành và giá hiện tại trước khi mua.\n\nGiá tham khảo: {_price(product)}.\n{disclosure}\n#reviewdienthoai #giadinh #congnghe2025"),
            ("tech_review", f"Nếu đang tìm flagship Android để dùng lâu dài, {name} là mẫu nên đưa vào danh sách so sánh.\n\nĐiểm cần kiểm tra: camera, pin, màn hình, bộ nhớ, bảo hành và giá thực tế tại thời điểm mua. Giá tham khảo: {_price(product)}.\n\n👇 Xem chi tiết tại link bên dưới.\n{disclosure}\n#samsung #android #reviewdienthoai #smartphone"),
        ]
    else:
        variants = [
            ("pain_point", f"Một món nhỏ có thể làm sinh hoạt hằng ngày nhẹ hơn nếu đúng nhu cầu.\n\n{name} phù hợp để tham khảo khi nhà cần giải quyết đúng việc, không mua chỉ vì thấy rẻ. Giá tham khảo: {_price(product)}.\n\n👇 Xem chi tiết ở link bên dưới.\n{disclosure}\n#muasamthongminh #dogiadung #dealhot"),
            ("checklist", f"Trước khi mua {name}, mẹ nên kiểm tra 3 điểm: chất liệu/kích thước, đánh giá người mua, và chính sách đổi trả.\n\nNếu các điểm này ổn và đúng nhu cầu, sản phẩm có thể đáng cân nhắc. Giá tham khảo: {_price(product)}.\n{disclosure}\n#mebim #dodungchobe #muasamthongminh"),
            ("soft_review", f"Không phải món nào cũng cần mua ngay, nhưng {name} có thể đáng xem nếu nó giải quyết đúng việc trong nhà.\n\nƯu tiên đọc review thật, xem ảnh người mua và kiểm tra giá hiện tại trước khi quyết định.\n{disclosure}\n#review #muasamthongminh #dealhot"),
        ]
    output: list[ContentVariant] = []
    product_dict: dict[str, Any] = asdict(product)
    for idx, (angle, text) in enumerate(variants, 1):
        fit = evaluate_market_fit(product_dict, text, audience=audience)
        output.append(ContentVariant(variant_id=f"v{idx}", angle=angle, text=text, score=fit.score, passed=fit.passed, reasons=fit.reasons))
    return sorted(output, key=lambda item: item.score, reverse=True)

def best_variant(product: ProductCandidate, *, audience: str = "smart_shopping") -> ContentVariant:
    return generate_content_variants(product, audience=audience)[0]

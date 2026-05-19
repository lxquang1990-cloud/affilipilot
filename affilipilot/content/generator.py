from __future__ import annotations

from affilipilot.content.compliance import check_mom_baby_compliance, default_affiliate_disclosure
from urllib.parse import urlparse

from affilipilot.models import ContentDraft, ProductCandidate


def _product_name(product: ProductCandidate) -> str:
    title = product.title.strip()
    if not title:
        return "sản phẩm này"
    separators = [" - ", " | ", "("]
    short = title
    for sep in separators:
        if sep in short:
            short = short.split(sep, 1)[0].strip()
    words = short.split()
    if len(words) > 12:
        short = " ".join(words[:12]).strip()
    return short or title[:90].strip()


def _price_hint(product: ProductCandidate) -> str:
    if product.price_vnd:
        price = f"{product.price_vnd:,}".replace(",", ".")
        return f"Giá tham khảo khoảng {price}đ, có thể thay đổi theo thời điểm."
    return "Giá/ưu đãi có thể thay đổi theo thời điểm, nên kiểm tra lại trước khi mua."


def _discount_hint(product: ProductCandidate) -> str:
    text = product.notes.lower()
    if "discount_rate=" in text:
        raw = text.split("discount_rate=", 1)[1].split(";", 1)[0].split(" ", 1)[0]
        try:
            rate = float(raw)
            if rate <= 1:
                rate *= 100
            if rate >= 10:
                return f"Điểm đáng chú ý là sản phẩm đang có mức giảm khoảng {rate:.0f}% theo data hiện tại."
        except ValueError:
            pass
    if "discount_vnd=" in text:
        return "Sản phẩm đang có ưu đãi theo data hiện tại, nên kiểm tra lại giá trước khi chốt."
    return ""


def _merchant_hint(product: ProductCandidate) -> str:
    text = f"{product.notes} {product.url}".lower()
    if "lazada_kol" in text or "lazada" in text:
        return "Nên ưu tiên shop có đánh giá tốt, thông tin bảo hành rõ và chính sách đổi trả minh bạch trên Lazada."
    if "shopee" in text:
        return "Nên ưu tiên shop Mall/Shop yêu thích, lượt bán thật và đánh giá có ảnh trên Shopee."
    if "tiki" in text:
        return "Nên kiểm tra nhãn Tiki Trading/official store và thời gian giao hàng trước khi mua."
    return "Nên kiểm tra đánh giá shop, ảnh thật và chính sách đổi trả trước khi mua."


def _interest_hashtags(product: ProductCandidate) -> str:
    link = product.tracking_url or product.affiliate_url or product.url
    host = urlparse(link).netloc.lower()
    text = f"{link} {product.notes} {product.title} {product.category}".lower()
    category = product.category.lower()
    if "cellphones" in text or "cellphones" in host or category in {"electronics", "phone", "smartphone", "laptop", "computer"}:
        return "#congnghe #muasamthongminh #dealcongnghe #reviewdientu"
    if category in {"home_appliance", "home_living"}:
        return "#dogiadung #nhacuasachgon #muasamthongminh #dealgiadung"
    if "khăn sữa" in text or "khan sua" in text or category == "baby_care":
        return "#khansua #mevabe #dodungchobe #mebim"
    if "feeding" in text or category == "feeding":
        return "#andam #mevabe #dodungchobe #mebim"
    if "storage" in text or category == "storage":
        return "#sapxepnhacua #dodungchobe #mebim #nhacuasachgon"
    if category == "beauty":
        return "#lamdep #muasamthongminh #dealhot"
    return "#muasamthongminh #reviewsanpham #dealhot"


def _home_appliance_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    hook = "Đồ gia dụng đáng mua là món giúp việc trong nhà nhẹ hơn thật, không chỉ vì đang giảm giá."
    body = f"{name} đáng để xem nếu nhà đang cần một món hỗ trợ sinh hoạt hằng ngày rõ ràng. {_discount_hint(product)} {_price_hint(product)} {_merchant_hint(product)} Trước khi mua, nên đối chiếu kích thước/công suất, điều kiện bảo hành và review ảnh thật để tránh chọn nhầm mẫu không hợp nhu cầu."
    return hook, body


def _electronics_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    hook = "Đồ công nghệ nên mua khi nó giải quyết đúng nhu cầu: pin, bộ nhớ, bảo hành hoặc làm việc/học tập tiện hơn."
    body = f"{name} phù hợp để cân nhắc nếu thông số thật khớp nhu cầu sử dụng, không chỉ vì tiêu đề sale. {_discount_hint(product)} {_price_hint(product)} Nên kiểm tra bảo hành, cấu hình chính, ảnh/review thật và so sánh giá với 1-2 shop khác trước khi chốt."
    return hook, body


def _baby_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    title = name.lower()
    if "khăn" in title:
        hook = "Khăn sữa là món dùng liên tục mỗi ngày: lau mặt, lau sữa, lót vai, mang theo khi ra ngoài."
        body = f"{name} đáng để mẹ xem nếu cần khăn mềm, dễ giặt và đủ dùng xoay vòng. Nên ưu tiên chất liệu cotton/muslin/sợi tre, bề mặt mềm, ít bụi vải và kích thước hợp túi đồ của bé. {_price_hint(product)} {_merchant_hint(product)}"
    else:
        hook = "Đồ cho bé nên chọn theo tần suất dùng thật, chất liệu và độ dễ vệ sinh — không mua chỉ vì quảng cáo."
        body = f"{name} là nhóm đồ mẹ nên xem kỹ chất liệu, kích thước, cách vệ sinh và đánh giá thật trước khi mua. {_price_hint(product)} {_merchant_hint(product)} Không kỳ vọng công dụng sức khỏe/phát triển nếu nhà bán không có thông tin kiểm chứng rõ ràng."
    return hook, body


def _generic_profit_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    hook = f"{name} chỉ đáng mua nếu nó giải quyết đúng một việc cụ thể trong nhà hoặc công việc hằng ngày."
    body = f"Điểm nên kiểm tra trước là thông số chính, chất liệu/kích thước, review ảnh thật và chính sách đổi trả. {_discount_hint(product)} {_price_hint(product)} {_merchant_hint(product)} Nếu giá tốt nhưng thông tin sản phẩm mơ hồ thì nên bỏ qua."
    return hook, body


def generate_safe_facebook_draft(product: ProductCandidate) -> ContentDraft:
    name = _product_name(product)
    category = product.category.lower()

    if category in {"home_appliance", "home_living", "storage"}:
        hook, body = _home_appliance_copy(product, name)
    elif category in {"electronics", "phone", "smartphone", "laptop", "computer", "phone_accessory", "office_productivity"}:
        hook, body = _electronics_copy(product, name)
    elif category in {"baby_care", "mother_baby", "feeding", "toy"}:
        hook, body = _baby_copy(product, name)
    else:
        hook, body = _generic_profit_copy(product, name)

    cta = "Xem chi tiết sản phẩm, đánh giá shop và giá hiện tại ở link bên dưới nhé."
    disclosure = default_affiliate_disclosure() + "\n" + _interest_hashtags(product)
    compliance = check_mom_baby_compliance("\n\n".join([hook, body, cta, disclosure]), category=product.category)
    return ContentDraft(product=product, hook=hook, body=body, cta=cta, disclosure=disclosure, compliance=compliance)

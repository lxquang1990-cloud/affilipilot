from __future__ import annotations

import re
from dataclasses import dataclass
from affilipilot.content.compliance import check_mom_baby_compliance, default_affiliate_disclosure
from urllib.parse import urlparse

from affilipilot.models import ContentDraft, ProductCandidate

@dataclass(frozen=True)
class ProductArchetype:
    code: str
    hook: str
    use_case: str
    buying_checks: tuple[str, ...]
    safety_note: str = ""

ARCHETYPES: tuple[ProductArchetype, ...] = (
    ProductArchetype(
        code="baby_care_towel",
        hook="Khăn sữa là món dùng liên tục mỗi ngày: lau mặt, lau sữa, lót vai, mang theo khi ra ngoài.",
        use_case="hợp khi mẹ cần khăn mềm, dễ giặt, thấm ổn và đủ số lượng để xoay vòng trong ngày",
        buying_checks=("chất liệu cotton/muslin/sợi tre", "bề mặt mềm, ít bụi vải", "kích thước hợp túi đồ của bé", "review sau giặt"),
    ),
    ProductArchetype(
        code="feeding_bottle_cup",
        hook="Đồ ăn dặm nên ưu tiên dễ vệ sinh, chất liệu rõ ràng và bé cầm/nắm có thoải mái không.",
        use_case="phù hợp nếu nhà đang chuẩn bị đồ ăn dặm hoặc cần món dùng hằng ngày dễ rửa, dễ mang theo",
        buying_checks=("chất liệu an toàn thực phẩm", "có tháo rời để vệ sinh không", "dung tích/kích thước", "review ảnh thật"),
    ),
    ProductArchetype(
        code="home_storage",
        hook="Đồ sắp xếp đáng mua khi nó giúp góc nhà gọn hơn thật, không chỉ vì nhìn ảnh quảng cáo đẹp.",
        use_case="hợp nếu nhà cần gom đồ nhỏ, đồ của bé hoặc đồ bếp/phòng tắm vào một chỗ dễ lấy",
        buying_checks=("kích thước thực tế", "tải trọng", "chất liệu", "cách lắp/treo", "ảnh review trong không gian thật"),
    ),
    ProductArchetype(
        code="cleaning_appliance",
        hook="Đồ dọn dẹp tốt là món tiết kiệm sức mỗi ngày, nhất là với nhà có trẻ nhỏ hoặc nhiều bụi tóc.",
        use_case="đáng cân nhắc nếu nó giải quyết rõ một việc lặp lại như hút bụi, lau sàn, lọc không khí hoặc vệ sinh góc khó",
        buying_checks=("công suất/dung tích", "độ ồn", "phụ kiện thay thế", "bảo hành", "review sau vài tuần dùng"),
    ),
    ProductArchetype(
        code="kitchen_appliance",
        hook="Đồ bếp nên mua khi giúp nấu nhanh hơn, dọn dễ hơn hoặc dùng đều đặn trong tuần.",
        use_case="phù hợp nếu thói quen nấu nướng của nhà thật sự cần thêm một món hỗ trợ hằng ngày",
        buying_checks=("dung tích", "công suất", "kích thước để bàn", "dễ vệ sinh", "bảo hành/đổi trả"),
    ),
)


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
        rounded = int(value // 1000)
        return f"{rounded}k+"
    return str(int(value))

def _social_proof_hint(product: ProductCandidate) -> str:
    rating = _note_number(product, "rating")
    sold = _note_number(product, "sold") or _note_number(product, "historical_sold")
    reviews = _note_number(product, "review_count")
    pieces: list[str] = []
    if rating and rating >= 4.7:
        pieces.append(f"rating khoảng {rating:.1f}/5")
    if sold and sold >= 100:
        pieces.append(f"{_format_count(sold)} lượt bán")
    if reviews and reviews >= 30:
        pieces.append(f"{_format_count(reviews)} đánh giá")
    if not pieces:
        return ""
    return "⭐ Tín hiệu tham khảo: " + ", ".join(pieces) + ". Vẫn nên mở review ảnh thật để kiểm tra trước khi chốt."

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

def _product_text(product: ProductCandidate) -> str:
    return " ".join([product.title, product.category, product.notes, product.url]).lower()

def _pick_archetype(product: ProductCandidate) -> ProductArchetype | None:
    text = _product_text(product)
    category = product.category.lower()
    if any(term in text for term in ("khăn sữa", "khan sua", "khăn xô", "khăn muslin", "khăn mặt bé")):
        return next(a for a in ARCHETYPES if a.code == "baby_care_towel")
    if category == "feeding" or any(term in text for term in ("bình thìa", "bình sữa", "cốc tập uống", "yếm", "ăn dặm", "hop chia sua", "hộp chia sữa")):
        return next(a for a in ARCHETYPES if a.code == "feeding_bottle_cup")
    if category == "storage" or any(term in text for term in ("giỏ", "kệ", "hộp đựng", "túi treo", "sắp xếp", "organizer")):
        return next(a for a in ARCHETYPES if a.code == "home_storage")
    if any(term in text for term in ("máy hút bụi", "robot hút bụi", "máy lau", "máy lọc không khí", "lọc không khí", "cây lau", "máy rửa")):
        return next(a for a in ARCHETYPES if a.code == "cleaning_appliance")
    if any(term in text for term in ("nồi chiên", "máy xay", "máy ép", "ấm siêu tốc", "nồi cơm", "bếp", "lò nướng")):
        return next(a for a in ARCHETYPES if a.code == "kitchen_appliance")
    return None

def _check_hint(archetype: ProductArchetype) -> str:
    if archetype.code == "home_storage":
        return "Nên đối chiếu kích thước thực tế, chất liệu và cách lắp/treo với góc nhà định dùng."
    if archetype.code == "cleaning_appliance":
        return "Nên xem công suất/dung tích, độ ồn và bảo hành để tránh mua nhầm loại không hợp nhà."
    if archetype.code == "baby_care_towel":
        return "Nên xem chất liệu, kích thước và review sau giặt để tránh khăn bị thô hoặc nhiều bụi vải."
    if archetype.code == "feeding_bottle_cup":
        return "Nên xem chất liệu, dung tích và phần tháo rời có dễ vệ sinh không."
    if archetype.code == "kitchen_appliance":
        return "Nên đối chiếu dung tích/công suất với nhu cầu nấu thật của nhà."
    return ""

def _archetype_copy(product: ProductCandidate, name: str, archetype: ProductArchetype) -> tuple[str, str]:
    proof = _social_proof_hint(product)
    proof_text = (proof + " ") if proof else ""
    safety = (" " + archetype.safety_note) if archetype.safety_note else ""
    check_hint = (_check_hint(archetype) + " ") if _check_hint(archetype) else ""
    body = (
        f"{name} {archetype.use_case}. "
        f"{check_hint}{proof_text}{_discount_hint(product)} {_price_hint(product)} {_merchant_hint(product)}{safety}"
    )
    body = re.sub(r"\s+", " ", body).strip()
    return archetype.hook, body


def _interest_hashtags(product: ProductCandidate) -> str:
    link = product.tracking_url or product.affiliate_url or product.url
    host = urlparse(link).netloc.lower()
    text = f"{link} {product.notes} {product.title} {product.category}".lower()
    category = product.category.lower()
    if "cellphones" in text or "cellphones" in host or category in {"electronics", "phone", "smartphone", "laptop", "computer"}:
        return "#congnghe #dealcongnghe #reviewdientu"
    if category in {"home_appliance", "home_living"}:
        return "#dogiadung #nhacuasachgon #dealgiadung"
    if category == "baby_play" or any(term in text for term in ("bể bơi", "hồ bơi", "cầu trượt", "nhà nhún", "nhún nhảy", "xe tập đi", "xe chòi chân")):
        if "xe tập đi" in text or "xe chòi chân" in text:
            return "#xetapdi #xechoichan #mevabe #dodungchobe #shopee"
        if "nhà nhún" in text or "nhún nhảy" in text:
            return "#nhanhun #chobevui #mevabe #dodungchobe #shopee"
        return "#chobevui #mevabe #dodungchobe #shopee"
    if "khăn sữa" in text or "khan sua" in text or category == "baby_care":
        return "#khansua #mevabe #dodungchobe"
    if "feeding" in text or category == "feeding":
        return "#andam #mevabe #dodungchobe"
    if "storage" in text or category == "storage":
        return "#sapxepnhacua #mevabe #nhacuasachgon"
    if category == "beauty":
        return "#lamdep #dealhot"
    if category in {"sports", "football", "sport"} or "giày đá bóng" in text or "bóng đá" in text:
        return "#bongda #giaydabong #thethao"
    return "#muasamthongminh #reviewsanpham"


def _home_appliance_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    archetype = _pick_archetype(product)
    if archetype:
        return _archetype_copy(product, name, archetype)
    hook = "Đồ gia dụng đáng mua là món giúp việc trong nhà nhẹ hơn thật, không chỉ vì đang giảm giá."
    body = f"{name} đáng để xem nếu nhà đang cần một món hỗ trợ sinh hoạt hằng ngày rõ ràng. {_discount_hint(product)} {_price_hint(product)} {_merchant_hint(product)} Trước khi mua, nên đối chiếu kích thước/công suất, điều kiện bảo hành và review ảnh thật để tránh chọn nhầm mẫu không hợp nhu cầu."
    return hook, body


def _electronics_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    hook = "Đồ công nghệ nên mua khi nó giải quyết đúng nhu cầu: pin, bộ nhớ, bảo hành hoặc làm việc/học tập tiện hơn."
    body = f"{name} phù hợp để cân nhắc nếu thông số thật khớp nhu cầu sử dụng, không chỉ vì tiêu đề sale. {_discount_hint(product)} {_price_hint(product)} Nên kiểm tra bảo hành, cấu hình chính, ảnh/review thật và so sánh giá với 1-2 shop khác trước khi chốt."
    return hook, body


def _baby_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    archetype = _pick_archetype(product)
    if archetype:
        return _archetype_copy(product, name, archetype)
    hook = "Đồ cho bé nên chọn theo tần suất dùng thật, chất liệu và độ dễ vệ sinh — không mua chỉ vì quảng cáo."
    body = f"{name} là nhóm đồ mẹ nên xem kỹ chất liệu, kích thước, cách vệ sinh và đánh giá thật trước khi mua. {_price_hint(product)} {_merchant_hint(product)} Không kỳ vọng công dụng sức khỏe/phát triển nếu nhà bán không có thông tin kiểm chứng rõ ràng."
    return hook, body


def _sports_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    hook = "Giày đá bóng nên chọn theo mặt sân, độ ôm chân và cảm giác đệm — không chỉ nhìn mẫu mã."
    body = f"{name} phù hợp để cân nhắc nếu bạn thường đá sân cỏ nhân tạo và cần đôi giày ôm chân, upper mềm, đệm êm khi di chuyển nhiều. {_price_hint(product)} {_merchant_hint(product)} Trước khi chốt, nên kiểm tra đúng size, form chân bè/thon, loại đinh TF, ảnh thật và chính sách đổi trả nếu mang chưa vừa."
    return hook, body


def _baby_play_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    title = product.title.lower()
    if "bể bơi" in title or "hồ bơi" in title:
        hook = "Có những hôm nóng quá, cho bé nghịch nước ở nhà lại tiện hơn nhiều so với đưa ra bể công cộng."
        body = f"{name} phù hợp nếu nhà có sân nhỏ, ban công rộng hoặc một góc phòng tắm đủ thoáng. Điểm đáng xem là bể gấp gọn được nên cất đỡ vướng, chất liệu PVC dễ lau rửa, có nhiều kích thước để chọn theo diện tích nhà. Trước khi chốt nên xem kỹ ảnh thật/review, kích thước khi bơm/mở ra, đáy bể có đủ chắc không và van xả nước có tiện không. {_price_hint(product)} {_merchant_hint(product)} Lưu ý quan trọng: bé chơi nước lúc nào cũng cần người lớn ngồi gần quan sát, kể cả bể nông."
    elif "nhà nhún" in title or "nhún nhảy" in title:
        hook = "Bé nhiều năng lượng mà nhà chưa tiện ra khu vui chơi thì nhà nhún trong nhà là món đáng cân nhắc."
        body = f"{name} phù hợp cho bé vận động tại nhà, nhất là những lúc trời mưa/nắng gắt hoặc ba mẹ muốn bé chơi trong tầm mắt. Điểm cần xem kỹ là kích thước khi lắp, tải trọng phù hợp, độ chắc của khung, lưới bảo hộ quanh thành, bề mặt tiếp đất và mức ồn khi bé nhún. {_price_hint(product)} {_merchant_hint(product)} Lưu ý: nên đặt trên mặt phẳng, tránh cạnh bàn/tường cứng và luôn có người lớn quan sát khi bé chơi."
    elif "xe tập đi" in title or "xe chòi chân" in title:
        hook = "Bé tới tuổi vịn đứng, thích đẩy đồ đi quanh nhà là ba mẹ bắt đầu phải để mắt nhiều hơn 😄"
        proof = _social_proof_hint(product)
        proof_text = (proof + " ") if proof else ""
        body = f"{name} hợp nếu nhà muốn một món chơi được lâu hơn một chút: lúc đầu bé vịn/đẩy tập bước, lớn hơn có thể chuyển sang chòi chân, kèm bảng nhạc và đèn để bé đỡ nhanh chán. Mấy điểm nên check trước là bánh có chắc không, xe có dễ lật không, tay cầm có vừa tầm bé không, phần nhựa có bo cạnh ổn không và âm thanh có tắt được không. {proof_text}{_price_hint(product)} Lưu ý: xe tập đi không thay người lớn trông bé; nên dùng trên mặt phẳng, tránh cầu thang/bậc cửa và không để bé chơi một mình."
    elif "cầu trượt" in title:
        hook = "Một góc vận động nhỏ trong nhà giúp bé leo trèo, trượt và xả năng lượng mà không phải lúc nào cũng ra sân chơi."
        body = f"{name} đáng xem nếu nhà còn khoảng trống an toàn cho bé vận động mỗi ngày. Trước khi mua nên kiểm tra chiều cao trượt, độ bám của bậc leo, chất liệu nhựa, bo góc, tải trọng và review ảnh thật để tránh chọn mẫu quá nhỏ hoặc rung lắc. {_price_hint(product)} {_merchant_hint(product)} Vẫn nên đặt ở nơi thoáng, tránh vật cứng xung quanh và có người lớn quan sát."
    else:
        hook = "Đồ vận động cho bé nên chọn theo không gian nhà, độ chắc chắn và khả năng quan sát của người lớn."
        body = f"{name} phù hợp nếu gia đình muốn bé có thêm hoạt động vận động tại nhà. Trước khi chốt nên xem kỹ kích thước, tải trọng, chất liệu, bề mặt tiếp xúc, ảnh/review thật và cách cất gọn sau khi chơi. {_price_hint(product)} {_merchant_hint(product)} Đồ chơi vận động luôn cần đặt ở khu vực an toàn và có người lớn theo dõi."
    return hook, body

def _generic_profit_copy(product: ProductCandidate, name: str) -> tuple[str, str]:
    archetype = _pick_archetype(product)
    if archetype:
        return _archetype_copy(product, name, archetype)
    hook = f"{name} là món nên xem kỹ nhu cầu sử dụng thật trước khi chốt mua."
    body = f"Hãy ưu tiên thông tin cụ thể: kích thước, chất liệu, cách dùng, ảnh/review thật và chính sách đổi trả. {_discount_hint(product)} {_price_hint(product)} {_merchant_hint(product)} Nếu giá tốt nhưng mô tả sản phẩm mơ hồ thì nên bỏ qua."
    return hook, body


def _repair_copy(product: ProductCandidate, name: str, feedback: list[str]) -> tuple[str, str]:
    lower_feedback = " ".join(feedback).lower()
    category = product.category.lower()
    hook = f"{name} chỉ đáng mua khi thông tin sản phẩm đủ rõ và hợp đúng việc cần dùng."
    checks = ["kích thước", "chất liệu", "cách dùng thực tế", "ảnh/review thật", "đổi trả"]
    if "feeding" in lower_feedback or category == "feeding":
        hook = "Đồ ăn dặm nên dễ vệ sinh, chất liệu rõ ràng và hợp tay bé khi dùng hằng ngày."
        checks = ["chất liệu an toàn thực phẩm", "dung tích", "có tháo rời để vệ sinh không", "bé cầm/nắm có tiện không", "review ảnh thật"]
    elif "storage" in lower_feedback or category == "storage":
        hook = "Đồ sắp xếp nên giúp góc nhà gọn hơn thật, nhất là các món nhỏ dùng mỗi ngày."
        checks = ["kích thước thực tế", "tải trọng", "chất liệu", "cách lắp/treo", "ảnh review trong không gian thật"]
    elif "baby_care" in lower_feedback or category in {"baby_care", "mother_baby"}:
        hook = "Đồ cho bé nên ưu tiên chất liệu, độ mềm và cách vệ sinh trước khi nhìn giá."
        checks = ["chất liệu cotton/muslin/sợi tre", "độ mềm với da bé", "khả năng thấm", "ít bụi vải", "giặt có nhanh khô không"]
    elif "home_appliance" in lower_feedback or category in {"home_appliance", "home_living"}:
        hook = "Đồ gia dụng đáng mua khi nó giảm việc lặp lại trong nhà và thông số đủ rõ để so sánh."
        checks = ["công suất/dung tích", "kích thước", "độ ồn", "bảo hành", "review sau vài tuần dùng"]
    elif "electronics" in lower_feedback or category in {"electronics", "phone", "smartphone", "laptop", "computer"}:
        hook = "Đồ công nghệ nên chọn theo nhu cầu thật: pin, bộ nhớ, camera, bảo hành và độ ổn định khi dùng lâu."
        checks = ["pin", "bộ nhớ/dung lượng", "camera hoặc màn hình", "bảo hành", "review hiệu năng thực tế"]
    body = (
        f"{name} phù hợp để cân nhắc nếu các thông tin chính đều rõ ràng, không chỉ vì đang được gắn nhãn sale. "
        f"Trước khi chốt nên kiểm tra: {', '.join(checks)}. "
        f"{_price_hint(product)} {_merchant_hint(product)} Nếu mô tả hoặc ảnh thật chưa đủ rõ thì nên bỏ qua thay vì cố mua."
    )
    return hook, re.sub(r"\s+", " ", body).strip()

def generate_safe_facebook_draft(product: ProductCandidate, *, feedback: list[str] | None = None) -> ContentDraft:
    name = _product_name(product)
    category = product.category.lower()

    if feedback:
        hook, body = _repair_copy(product, name, feedback)
    elif category in {"home_appliance", "home_living", "storage"}:
        hook, body = _home_appliance_copy(product, name)
    elif category in {"electronics", "phone", "smartphone", "laptop", "computer", "phone_accessory", "office_productivity"}:
        hook, body = _electronics_copy(product, name)
    elif category == "baby_play" or any(term in product.title.lower() for term in ("bể bơi", "hồ bơi", "cầu trượt", "nhà nhún", "nhún nhảy", "xe tập đi", "xe chòi chân")):
        hook, body = _baby_play_copy(product, name)
    elif category in {"baby_care", "mother_baby", "feeding", "toy"}:
        hook, body = _baby_copy(product, name)
    elif category in {"sports", "football", "sport"} or "giày đá bóng" in product.title.lower() or "bóng đá" in product.title.lower():
        hook, body = _sports_copy(product, name)
    else:
        hook, body = _generic_profit_copy(product, name)

    cta = "Xem ảnh thật, review và giá hiện tại ở link bên dưới nhé 👇"
    disclosure = default_affiliate_disclosure() + "\n" + _interest_hashtags(product)
    compliance = check_mom_baby_compliance("\n\n".join([hook, body, cta, disclosure]), category=product.category)
    return ContentDraft(product=product, hook=hook, body=body, cta=cta, disclosure=disclosure, compliance=compliance)

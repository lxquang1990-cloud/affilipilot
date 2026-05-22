from affilipilot.content.generator import generate_safe_facebook_draft
from affilipilot.models import ProductCandidate
from affilipilot.publishing.requirements import check_media
from affilipilot.scanner.enrich import harvest_image_urls


def test_media_gate_rejects_lazada_ui_assets():
    post = {
        "product": {"image_url": "https://img.lazcdn.com/g/tps/images/ims-web/TB1.png"},
        "files": {},
        "media": {},
    }
    check = check_media(post)
    assert not check.passed
    assert "untrusted_product_media" in check.reasons


def test_harvest_image_urls_filters_lazada_ui_assets():
    html = '''
    <img src="https://img.lazcdn.com/g/tps/images/ims-web/TB1.png">
    <img src="https://img.lazcdn.com/media/catalog/product/a/b/binh-thia.jpg">
    '''
    images = harvest_image_urls(html, title="bình thìa")
    assert images == ["https://img.lazcdn.com/media/catalog/product/a/b/binh-thia.jpg"]


def test_generator_uses_interest_hashtags_not_internal_campaign_hashtags():
    draft = generate_safe_facebook_draft(ProductCandidate(url="https://www.lazada.vn/tag/x", title="Bình thìa", category="feeding", notes="lazada"))
    assert "#andam" in draft.full_text
    assert "#muasamthongminh" in draft.full_text
    assert "#LazadaAffiliate" not in draft.full_text
    assert "#ShopeeAffiliate" not in draft.full_text

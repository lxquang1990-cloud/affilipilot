from affilipilot.models import ProductCandidate
from affilipilot.workflows import auto_source_hunter


def test_candidate_line_preserves_gallery_and_video_urls():
    product = ProductCandidate(
        url="https://tiki.vn/p.html",
        title="Máy xay",
        image_url="https://cdn/main.jpg",
        image_urls=["https://cdn/main.jpg", "https://cdn/detail.jpg"],
        video_urls=["https://cdn/video.mp4"],
    )

    line = auto_source_hunter._candidate_line(product)

    assert "image_urls=https://cdn/main.jpg,https://cdn/detail.jpg" in line
    assert "video_urls=https://cdn/video.mp4" in line


def test_selected_media_enrichment_updates_product_gallery(monkeypatch):
    product = ProductCandidate(
        url="https://tiki.vn/p.html",
        title="Máy xay",
        category="home_appliance",
        original_url="https://tiki.vn/p.html",
    )

    monkeypatch.setattr(
        auto_source_hunter,
        "enrich_product_from_url",
        lambda *args, **kwargs: {
            "image_urls": ["https://cdn/1.jpg", "https://cdn/2.jpg", "https://cdn/3.jpg"],
            "video_urls": ["https://cdn/v.mp4"],
            "media_source": "tiki_pdp",
            "media_confidence": "official",
        },
    )

    selected = auto_source_hunter._enrich_selected_media([{"product": product, "score": 1}])
    enriched = selected[0]["product"]

    assert enriched.image_url == "https://cdn/1.jpg"
    assert enriched.image_urls == ["https://cdn/1.jpg", "https://cdn/2.jpg", "https://cdn/3.jpg"]
    assert enriched.video_url == "https://cdn/v.mp4"
    assert enriched.video_urls == ["https://cdn/v.mp4"]
    assert enriched.media_source == "tiki_pdp"
    assert "pdp_media_enriched" in enriched.notes

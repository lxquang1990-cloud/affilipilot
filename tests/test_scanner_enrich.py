import json
import sqlite3

from affilipilot.scanner.enrich import harvest_image_urls, harvest_lazada_product_urls, enrich_batch_media, extract_lazada_product_media


def test_harvest_image_urls_prefers_product_images():
    html = '''
    <img src="https://img.lazcdn.com/g/tps/logo.png">
    <script>{"image":"https://cdn2.cellphones.com.vn/media/catalog/product/a/b/abc-product.jpg"}</script>
    <img src="https://example.com/icon.png">
    '''
    images = harvest_image_urls(html, title="abc product")
    assert images[0].endswith("abc-product.jpg")

def test_enrich_product_from_url_keeps_harvested_gallery(monkeypatch):
    from affilipilot.scanner import enrich

    html = '''
    <html><head><title>Máy xay</title></head>
    <script>{"image":"https://salt.tikicdn.com/cache/750x750/media/catalog/producttmp/a/main.jpg"}</script>
    <script>{"image":"https://salt.tikicdn.com/cache/750x750/media/catalog/producttmp/a/detail.jpg"}</script>
    </html>
    '''
    monkeypatch.setattr(enrich, "fetch_html", lambda url, timeout=30: html)
    monkeypatch.setattr(enrich, "parse_products_from_html", lambda *args, **kwargs: [])

    product = enrich.enrich_product_from_url("https://tiki.vn/p.html", title="Máy xay", category="home_appliance")

    assert product["image_url"] == "https://salt.tikicdn.com/cache/750x750/media/catalog/producttmp/a/main.jpg"
    assert product["image_urls"] == [
        "https://salt.tikicdn.com/cache/750x750/media/catalog/producttmp/a/main.jpg",
        "https://salt.tikicdn.com/cache/750x750/media/catalog/producttmp/a/detail.jpg",
    ]


def test_extract_lazada_product_media_from_seo_gallery_and_sku_galleries():
    html = '''
    <noscript><div class="seo-gallery">
      <img src="https://img.lazcdn.com/g/p/a.jpg_720x720q80.jpg" itemprop="contentUrl" />
      <img src="https://img.lazcdn.com/g/p/b.png_720x720q80.png" itemprop="contentUrl" />
    </div></noscript>
    <script>{"skuGalleries":{"0":[
      {"poster":"https://filebroker-cdn.lazada.vn/kf/video-cover.jpg","type":"video","videoID":"1"},
      {"src":"//vn-test-11.slatic.net/p/c.jpg","type":"img"},
      {"src":"//img.lazcdn.com/g/tps/images/ims-web/logo.png","type":"img"}
    ]},"contentUrl":"https://cloud.video.lazada.com/play/u/1/p/1/e/6/t/1/d/sd/abc.mp4"}</script>
    '''
    media = extract_lazada_product_media(html)
    assert media["image_urls"][:3] == [
        "https://img.lazcdn.com/g/p/a.jpg_720x720q80.jpg",
        "https://img.lazcdn.com/g/p/b.png_720x720q80.png",
        "https://filebroker-cdn.lazada.vn/kf/video-cover.jpg",
    ]
    assert "https://vn-test-11.slatic.net/p/c.jpg" in media["image_urls"]
    assert all("ims-web" not in url for url in media["image_urls"])
    assert media["video_urls"] == ["https://cloud.video.lazada.com/play/u/1/p/1/e/6/t/1/d/sd/abc.mp4"]

def test_harvest_lazada_product_urls():
    html = '''
    <a href="https://www.lazada.vn/products/binh-thia-i123-s456.html?spm=a2o4n">x</a>
    <script>"https:\\/\\/www.lazada.vn\\/products\\/ghe-an-dam-i789-s111.html"</script>
    '''
    urls = harvest_lazada_product_urls(html)
    assert urls[0].startswith("https://www.lazada.vn/products/binh-thia")
    assert len(urls) >= 1


def test_enrich_batch_media_downloads_existing_image_url(tmp_path, monkeypatch):
    import affilipilot.scanner.enrich as enrich
    from affilipilot.media import MediaResult

    db = tmp_path / "db.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table batches (batch_key text primary key, manifest_json text not null)")
    manifest = {"posts": [{"post_id": "post_1", "product": {"title": "Yếm ăn dặm", "url": "https://go.isclix.com/x", "image_url": "https://img.example/yem.jpg"}, "files": {}, "media": {}}]}
    con.execute("insert into batches values (?,?)", ("batch", json.dumps(manifest)))
    con.commit(); con.close()

    monkeypatch.setattr(enrich, "fetch_image", lambda url, out_dir, name_hint="product": MediaResult(ok=True, local_path=str(tmp_path / "image.jpg"), media_type="jpeg", reasons=[]))
    summary = enrich_batch_media(db, batch_key="batch", out_dir=tmp_path / "out")
    assert summary["updated"] == 1
    con = sqlite3.connect(db)
    updated = json.loads(con.execute("select manifest_json from batches where batch_key='batch'").fetchone()[0])
    assert updated["posts"][0]["media"]["ok"] is True


def test_enrich_batch_media_probes_shopee_gallery_when_provider_has_only_thumbnail(tmp_path, monkeypatch):
    import affilipilot.scanner.enrich as enrich
    from affilipilot.media import MediaResult

    db = tmp_path / "db.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table batches (batch_key text primary key, manifest_json text not null)")
    manifest = {
        "posts": [
            {
                "post_id": "post_1",
                "product": {
                    "title": "Máy xay mini",
                    "url": "https://go.isclix.com/deep_link/x?url=https%3A%2F%2Fshopee.vn%2Fproduct%2F371008594%2F3988083571",
                    "original_url": "https://shopee.vn/product/371008594/3988083571",
                    "image_url": "https://down-vn.img.susercontent.com/file/thumb-only",
                    "image_urls": [],
                },
                "files": {},
                "media": {},
            }
        ]
    }
    con.execute("insert into batches values (?,?)", ("batch", json.dumps(manifest)))
    con.commit(); con.close()

    def fake_enrich_product_from_url(url, title="", category="unknown", source="MANUAL"):
        assert url == "https://shopee.vn/product/371008594/3988083571"
        return {
            "image_url": "https://down-vn.img.susercontent.com/file/gallery-1",
            "image_urls": [
                "https://down-vn.img.susercontent.com/file/gallery-1",
                "https://down-vn.img.susercontent.com/file/gallery-2",
                "https://down-vn.img.susercontent.com/file/gallery-3",
            ],
            "notes": "shopee_product_media",
            "media_source": "shopee_pdp",
            "media_confidence": "official",
        }

    def fake_prepare_product_media_gallery(product, media_dir):
        return [
            MediaResult(ok=True, local_path=str(tmp_path / "gallery-1.jpg"), media_type="jpeg", reasons=[]),
            MediaResult(ok=True, local_path=str(tmp_path / "gallery-2.jpg"), media_type="jpeg", reasons=[]),
            MediaResult(ok=True, local_path=str(tmp_path / "gallery-3.jpg"), media_type="jpeg", reasons=[]),
        ]

    monkeypatch.setattr(enrich, "enrich_product_from_url", fake_enrich_product_from_url)
    monkeypatch.setattr(enrich, "prepare_product_media_gallery", fake_prepare_product_media_gallery)

    summary = enrich_batch_media(db, batch_key="batch", out_dir=tmp_path / "out")

    assert summary["updated"] == 1
    con = sqlite3.connect(db)
    updated = json.loads(con.execute("select manifest_json from batches where batch_key='batch'").fetchone()[0])
    post = updated["posts"][0]
    assert post["product"]["image_urls"] == [
        "https://down-vn.img.susercontent.com/file/gallery-1",
        "https://down-vn.img.susercontent.com/file/gallery-2",
        "https://down-vn.img.susercontent.com/file/gallery-3",
    ]
    assert len(post["files"]["images"]) == 3
    assert post["media"]["gallery_count"] == 3

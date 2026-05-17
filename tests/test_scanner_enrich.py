import json
import sqlite3

from affilipilot.scanner.enrich import harvest_image_urls, harvest_lazada_product_urls, enrich_batch_media


def test_harvest_image_urls_prefers_product_images():
    html = '''
    <img src="https://img.lazcdn.com/g/tps/logo.png">
    <script>{"image":"https://cdn2.cellphones.com.vn/media/catalog/product/a/b/abc-product.jpg"}</script>
    <img src="https://example.com/icon.png">
    '''
    images = harvest_image_urls(html, title="abc product")
    assert images[0].endswith("abc-product.jpg")


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

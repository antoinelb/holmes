import base64

black_tile = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class TestPages:
    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<!doctype html>" in resp.text.lower()

    def test_version(self, client):
        resp = client.get("/version")
        assert resp.status_code == 200

    def test_static_files(self, client):
        resp = client.get("/static/index.html")
        assert resp.status_code == 200


class TestMapTiles:
    def test_cached_tile(self, client, tmp_data_dir):
        path = tmp_data_dir / "map" / "tile_3_1_2.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"cached png")
        resp = client.get("/map/3/1/2.png")
        assert resp.status_code == 200
        assert resp.content == b"cached png"

    def test_missing_tile_returns_black_pixel(self, client):
        resp = client.get("/map/3/1/2.png")
        assert resp.status_code == 200
        assert resp.content == black_tile

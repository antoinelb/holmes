from unittest.mock import MagicMock

import httpx
import pytest

import holmes.download.tiles as tiles

png = b"\x89PNG fake tile"


def make_sync_client(monkeypatch, responses: list) -> MagicMock:
    """Patch `tiles.httpx.Client` with a mock yielding `responses`."""
    client = MagicMock()
    client.get = MagicMock(side_effect=responses)
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(tiles.httpx, "Client", MagicMock(return_value=client))
    return client


@pytest.fixture
def small_pyramid(monkeypatch) -> list[tuple[int, int, int]]:
    # two tiles stand in for the 3400-tile pyramid; the real coordinates
    # are covered by TestTilePaths
    coords = [(9, 150, 176), (9, 150, 177)]
    monkeypatch.setattr(tiles, "_tile_coords", lambda: coords)
    return coords


@pytest.fixture
def carto_key(monkeypatch) -> str:
    # bypass the real Config so the developer's .env never leaks into the
    # tests
    monkeypatch.setattr(tiles, "config", lambda *args, **kwargs: "test-key")
    return "test-key"


class TestTilePaths:
    def test_covers_the_full_pyramid(self):
        paths = tiles.tile_paths()
        assert len(paths) == 3400
        assert len(set(paths)) == 3400
        assert all(not path.is_absolute() for path in paths)

        names = {path.as_posix() for path in paths}
        assert "map/tile_9_150_176.png" in names
        assert "map/tile_9_157_180.png" in names
        assert "map/tile_12_1200_1408.png" in names
        assert "map/tile_12_1263_1447.png" in names
        assert "map/tile_12_1264_1447.png" not in names
        assert "map/tile_12_1263_1448.png" not in names


class TestDownloadTiles:
    def test_skip_if_all_exist(self, tmp_data_dir, small_pyramid, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(tiles.httpx, "Client", client)
        for z, x, y in small_pyramid:
            path = tmp_data_dir / "map" / f"tile_{z}_{x}_{y}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)

        tiles.download_tiles()

        client.assert_not_called()

    def test_missing_key_raises(
        self, tmp_data_dir, small_pyramid, monkeypatch
    ):
        monkeypatch.setattr(tiles, "config", lambda *args, **kwargs: "")

        with pytest.raises(RuntimeError, match="CARTO_KEY"):
            tiles.download_tiles()

    def test_fetches_only_missing_tiles(
        self, tmp_data_dir, small_pyramid, monkeypatch, carto_key
    ):
        existing = tmp_data_dir / "map" / "tile_9_150_176.png"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"old")
        client = make_sync_client(
            monkeypatch, [MagicMock(status_code=200, content=png)]
        )

        tiles.download_tiles()

        assert existing.read_bytes() == b"old"
        fetched = tmp_data_dir / "map" / "tile_9_150_177.png"
        assert fetched.read_bytes() == png
        assert not fetched.with_suffix(".png.part").exists()
        (url,), kwargs = client.get.call_args
        assert url.endswith("/9/150/177.png")
        assert kwargs == {"params": {"key": carto_key}}

    def test_force_refetches_everything(
        self, tmp_data_dir, small_pyramid, monkeypatch, carto_key
    ):
        for z, x, y in small_pyramid:
            path = tmp_data_dir / "map" / f"tile_{z}_{x}_{y}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"old")
        make_sync_client(
            monkeypatch, [MagicMock(status_code=200, content=png)] * 2
        )

        tiles.download_tiles(force=True)

        for z, x, y in small_pyramid:
            path = tmp_data_dir / "map" / f"tile_{z}_{x}_{y}.png"
            assert path.read_bytes() == png

    def test_failed_tile_raises_and_keeps_the_fetched_ones(
        self, tmp_data_dir, small_pyramid, monkeypatch, carto_key
    ):
        make_sync_client(
            monkeypatch,
            [
                MagicMock(status_code=200, content=png),
                MagicMock(status_code=404, content=b""),
            ],
        )

        with pytest.raises(RuntimeError, match="1 of 2 map tiles"):
            tiles.download_tiles()

        written = list((tmp_data_dir / "map").glob("tile_*.png"))
        assert len(written) == 1
        assert written[0].read_bytes() == png

    def test_network_error_counts_as_failure(
        self, tmp_data_dir, monkeypatch, carto_key
    ):
        monkeypatch.setattr(tiles, "_tile_coords", lambda: [(9, 150, 176)])
        make_sync_client(monkeypatch, [httpx.ConnectError("no network")])

        with pytest.raises(RuntimeError, match="1 of 1 map tiles"):
            tiles.download_tiles()

    def test_non_png_body_counts_as_failure(
        self, tmp_data_dir, monkeypatch, carto_key
    ):
        monkeypatch.setattr(tiles, "_tile_coords", lambda: [(9, 150, 176)])
        make_sync_client(
            monkeypatch,
            [MagicMock(status_code=200, content=b'{"error": "bad key"}')],
        )

        with pytest.raises(RuntimeError, match="1 of 1 map tiles"):
            tiles.download_tiles()

        assert not (tmp_data_dir / "map" / "tile_9_150_176.png").exists()

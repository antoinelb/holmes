import pytest

import holmes.data.tiles as tiles


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


class TestInPyramid:
    @pytest.mark.parametrize(
        "coords",
        [(9, 150, 176), (9, 157, 180), (12, 1200, 1408), (12, 1263, 1447)],
    )
    def test_corners_are_inside(self, coords):
        assert tiles.in_pyramid(*coords)

    @pytest.mark.parametrize(
        "coords",
        [
            (8, 75, 88),
            (13, 2400, 2816),
            (9, 149, 176),
            (9, 158, 176),
            (9, 150, 175),
            (9, 150, 181),
            (3, 1, 2),
        ],
    )
    def test_outside_is_rejected(self, coords):
        assert not tiles.in_pyramid(*coords)

    def test_agrees_with_tile_paths(self):
        assert all(tiles.in_pyramid(*c) for c in tiles.tile_coords())

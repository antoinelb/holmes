"""The shape of the basemap tile pyramid shipped in the data archive.

Kept in the read layer so the tile route can tell a tile that should
exist (missing: a broken archive) from one outside the pyramid (expected:
black) without importing the heavy build layer.
"""

from pathlib import Path

#############
# constants #
#############

# the z9 rectangle covering every watershed with margin (lon -74.53 to
# -68.91, lat 46.56 to 48.92); deeper zooms cover the same ground with
# 2**(z - base_zoom) times the tiles per axis. stations.js clamps the map
# to the matching maxBounds so users can never pan onto missing tiles.
base_zoom = 9
max_zoom = 12
base_x = range(150, 158)
base_y = range(176, 181)

##########
# public #
##########


def tile_paths() -> list[Path]:
    """Every tile of the pyramid, relative to `data_dir`."""
    return [tile_path(z, x, y) for z, x, y in tile_coords()]


def in_pyramid(z: int, x: int, y: int) -> bool:
    return (
        base_zoom <= z <= max_zoom
        and x in _scaled(base_x, z)
        and y in _scaled(base_y, z)
    )


def tile_coords() -> list[tuple[int, int, int]]:
    return [
        (z, x, y)
        for z in range(base_zoom, max_zoom + 1)
        for x in _scaled(base_x, z)
        for y in _scaled(base_y, z)
    ]


def tile_path(z: int, x: int, y: int) -> Path:
    return Path("map") / f"tile_{z}_{x}_{y}.png"


###########
# private #
###########


def _scaled(base: range, zoom: int) -> range:
    factor = 2 ** (zoom - base_zoom)
    return range(base.start * factor, base.stop * factor)

"""Build layer step: the pre-rendered basemap tile pyramid.

Carto requires an API key for its basemap tiles, so the app cannot fetch
them lazily without distributing the key; instead the fixed Saguenay
pyramid is fetched here — where the key lives — and shipped in the
archive like every other product.
"""

import concurrent.futures
from pathlib import Path

import httpx

from holmes.config import config

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths
from holmes.utils.print import done_print, progress_task

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

tile_url = "https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png"

##########
# public #
##########


def tile_paths() -> list[Path]:
    """Every tile of the pyramid, relative to `data_dir`."""
    return [_tile_path(z, x, y) for z, x, y in _tile_coords()]


def download_tiles(*, force: bool = False) -> None:
    """Fetch the basemap tiles missing from the pyramid.

    The per-tile skip is the resume granularity: an interrupted run picks
    up where it left off. Any tile still missing after the pass raises —
    there is no older file to keep (the warn-or-fail rule's warn branch
    does not apply) and packaging would fail on the absentee anyway.
    """
    missing = [
        coords
        for coords in _tile_coords()
        if force or not (paths.data_dir / _tile_path(*coords)).exists()
    ]
    if not missing:
        done_print("Map tiles are up to date.")
        return

    # every missing tile would fail the same way deep inside the pool, so
    # the key is checked once, up front, with a message that says what to
    # do about it
    key = _check_carto_credentials()

    failed = 0
    with progress_task(
        "Fetching map tiles...",
        f"Fetched {len(missing)} map tiles.",
        total=len(missing),
    ) as current:
        with httpx.Client(timeout=30) as client:
            # bounded pool: thousands of small GETs against one CDN
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = [
                    pool.submit(_fetch_tile, client, coords, key)
                    for coords in missing
                ]
                for future in concurrent.futures.as_completed(futures):
                    if not future.result():
                        failed += 1
                    current.increment()
    if failed:
        raise RuntimeError(
            f"{failed} of {len(missing)} map tiles could not be fetched "
            "from Carto; re-run `holmes download` to retry the missing "
            "ones."
        )


###########
# private #
###########


def _tile_coords() -> list[tuple[int, int, int]]:
    return [
        (z, x, y)
        for z in range(base_zoom, max_zoom + 1)
        for x in _scaled(base_x, z)
        for y in _scaled(base_y, z)
    ]


def _scaled(base: range, zoom: int) -> range:
    factor = 2 ** (zoom - base_zoom)
    return range(base.start * factor, base.stop * factor)


def _tile_path(z: int, x: int, y: int) -> Path:
    return Path("map") / f"tile_{z}_{x}_{y}.png"


def _check_carto_credentials() -> str:
    key = config("CARTO_KEY", default="")
    if not key:
        raise RuntimeError(
            "Missing map tiles have to be fetched from Carto, which "
            "requires an API key: get one at "
            "https://carto.com/basemaps/apikey/ and set CARTO_KEY in the "
            "environment or the .env file."
        )
    return key


def _fetch_tile(
    client: httpx.Client, coords: tuple[int, int, int], key: str
) -> bool:
    """Staged write: a crash mid-write never leaves a partial tile."""
    z, x, y = coords
    path = paths.data_dir / _tile_path(z, x, y)
    try:
        resp = client.get(tile_url.format(z=z, x=x, y=y), params={"key": key})
    except httpx.HTTPError:
        return False
    if resp.status_code != 200 or not resp.content.startswith(b"\x89PNG"):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.parent / f"{path.name}.part"
    staged.write_bytes(resp.content)
    staged.replace(path)
    return True

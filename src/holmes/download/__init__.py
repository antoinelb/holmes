"""Build layer: dataset construction shared by `holmes download`."""

from holmes.download import hydro, joined, projection, tiles, weather

##########
# public #
##########


def run_download(*, force: bool = False) -> None:
    """Build every data product incrementally, in dependency order.

    Later steps consume earlier outputs: streamflow and the weather
    products need the station frame, the backfill needs the raster
    caches era5 and the ministry grid leave behind, the completed
    stations need the backfill, the nearest-station products need the
    completed stations, and the joined products need everything; the map
    tiles are independent and fetched last.
    """
    stations = hydro.build_station_data(force=force)
    hydro.fetch_streamflow(stations, force=force)
    weather.update_era5(stations, force=force)
    weather.update_ministry_grid(stations, force=force)
    weather.update_stations_backfill(force=force)
    weather.rebuild_completed_stations()
    weather.rebuild_nearest_stations(stations)
    weather.rebuild_grids(stations)
    projection.build_projection_data(stations, force=force)
    joined.build_joined_data(stations)
    tiles.download_tiles(force=force)

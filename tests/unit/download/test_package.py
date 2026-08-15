import zipfile
from datetime import date
from pathlib import Path

import pytest

import holmes.download.package as package
from holmes.data.archive import MissingDataError
from holmes.data.hydro import STATIONS


@pytest.fixture
def seeded_data_dir(tmp_data_dir: Path) -> Path:
    # tiny placeholder bytes: build_archive only checks existence and
    # streams bytes, it never parses the products
    for entry in package.archive_manifest():
        path = tmp_data_dir / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
    return tmp_data_dir


class TestArchiveManifest:
    def test_lists_every_product_relative_to_data_dir(self):
        manifest = package.archive_manifest()

        assert len(manifest) == 45
        assert len(set(manifest)) == 45
        assert all(not entry.is_absolute() for entry in manifest)

        names = {entry.as_posix() for entry in manifest}
        assert "raw/hydro/station_data.ipc" in names
        for id in STATIONS:
            assert f"raw/hydro/streamflow/{id}.ipc" in names
            assert f"raw/projection/{id}.ipc" in names
        assert "raw/weather/era5.ipc" in names
        assert "raw/weather/ministry_grid.ipc" in names
        for n in range(1, 6):
            assert f"raw/weather/nearest_stations_{n}.ipc" in names
            assert f"raw/data_nearest_stations_{n}.ipc" in names
        assert "raw/weather/grid_era5.ipc" in names
        assert "raw/weather/grid_ministry_grid.ipc" in names
        assert "raw/weather/grid_nearest_stations.ipc" in names
        assert "raw/weather/stations_backfill.ipc" in names
        assert "raw/weather/stations/7060225_pikauba.csv" in names
        assert "raw/weather/stations_completed/7060225.ipc" in names
        assert "raw/data_era5.ipc" in names
        assert "raw/data_ministry_grid.ipc" in names


class TestBuildArchive:
    def test_writes_the_dated_archive_in_cwd(
        self, seeded_data_dir, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        output = package.build_archive()

        assert output.name == f"data-{date.today():%Y-%m-%d}.zip"
        assert output.parent == Path.cwd()
        assert output.exists()
        assert not output.with_suffix(".part").exists()
        with zipfile.ZipFile(output) as archive:
            assert archive.namelist() == [
                entry.as_posix() for entry in package.archive_manifest()
            ]

    def test_honours_a_custom_output(self, seeded_data_dir, tmp_path):
        output = tmp_path / "custom" / "archive.zip"
        output.parent.mkdir()

        result = package.build_archive(output)

        assert result == output
        assert output.exists()
        assert not output.with_suffix(".part").exists()
        with zipfile.ZipFile(output) as archive:
            assert len(archive.namelist()) == 45

    def test_missing_products_are_all_reported(
        self, seeded_data_dir, tmp_path
    ):
        removed = [
            Path("raw/weather/era5.ipc"),
            Path("raw/data_ministry_grid.ipc"),
        ]
        for entry in removed:
            (seeded_data_dir / entry).unlink()
        output = tmp_path / "archive.zip"

        with pytest.raises(MissingDataError) as exc:
            package.build_archive(output)

        message = str(exc.value)
        for entry in removed:
            assert str(entry) in message
        assert not output.exists()
        assert not output.with_suffix(".part").exists()

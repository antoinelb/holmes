"""Unit tests for holmes.data module."""

from datetime import datetime, timedelta

import polars as pl
import pytest

from holmes import data
from holmes.utils.paths import data_dir


class TestReadData:
    """Tests for read_data function."""

    def test_read_data_basic(self):
        """Load data with date range."""
        result = data.read_data("Au Saumon", "2000-01-01", "2005-12-31")
        assert isinstance(result, pl.DataFrame)
        assert "date" in result.columns
        assert "precipitation" in result.columns
        assert "pet" in result.columns
        assert "streamflow" in result.columns
        assert "temperature" in result.columns

    def test_read_data_with_warmup(self):
        """Verify warmup period calculation (3 years by default)."""
        from datetime import date

        start = "2005-01-01"
        end = "2005-12-31"
        result = data.read_data("Au Saumon", start, end)
        expected_start = datetime.strptime(start, "%Y-%m-%d") - timedelta(
            days=365 * 3
        )
        min_date = result["date"].min()
        assert isinstance(min_date, date)
        assert min_date <= expected_start.date()

    def test_read_data_custom_warmup(self):
        """Verify custom warmup period is shorter than default."""
        start = "2005-01-01"
        end = "2005-12-31"
        result_default = data.read_data("Au Saumon", start, end)
        result_short = data.read_data("Au Saumon", start, end, warmup_length=1)
        # Shorter warmup should have fewer rows
        assert len(result_short) < len(result_default)

    def test_read_data_all_catchments(self):
        """Verify all catchments can be read."""
        for (
            catchment_name,
            _,
            (start_avail, end_avail),
        ) in data.get_available_catchments():
            # Use the available date range for each catchment
            result = data.read_data(catchment_name, start_avail, end_avail)
            assert isinstance(result, pl.DataFrame)
            assert len(result) > 0

    def test_read_data_missing_catchment(self):
        """Error handling for missing catchment."""
        with pytest.raises(Exception):
            data.read_data("NonExistent", "2000-01-01", "2005-12-31")


class TestGetAvailableCatchments:
    """Tests for get_available_catchments function."""

    def test_get_available_catchments(self):
        """List catchments returns correct structure."""
        result = data.get_available_catchments()
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 3
            name, has_snow, date_range = item
            assert isinstance(name, str)
            assert isinstance(has_snow, bool)
            assert isinstance(date_range, tuple)
            assert len(date_range) == 2

    def test_catchments_sorted_alphabetically(self):
        """Catchments are sorted alphabetically."""
        result = data.get_available_catchments()
        names = [c[0] for c in result]
        assert names == sorted(names)

    def test_snow_catchments_have_cemaneige_file(self):
        """Catchments marked as having snow have CemaNeige files."""
        for name, has_snow, _ in data.get_available_catchments():
            cemaneige_path = data_dir / f"{name}_CemaNeigeInfo.csv"
            assert has_snow == cemaneige_path.exists()


class TestReadCemaNeigeInfo:
    """Tests for read_cemaneige_info function."""

    def test_read_cemaneige_info(self):
        """CemaNeige config parsing returns expected keys."""
        result = data.read_cemaneige_info("Au Saumon")
        assert "qnbv" in result
        assert "altitude_layers" in result
        assert "median_altitude" in result
        assert "latitude" in result
        assert "n_altitude_layers" in result

    def test_cemaneige_values_are_numeric(self):
        """CemaNeige values are of expected types."""
        result = data.read_cemaneige_info("Au Saumon")
        assert isinstance(result["qnbv"], float)
        assert isinstance(result["median_altitude"], float)
        assert isinstance(result["latitude"], float)
        assert isinstance(result["n_altitude_layers"], int)
        assert hasattr(result["altitude_layers"], "__len__")

    def test_cemaneige_missing_catchment(self):
        """Error handling for missing CemaNeige file."""
        with pytest.raises(Exception):
            data.read_cemaneige_info("NonExistent")


class TestReadCatchmentData:
    """Tests for read_catchment_data function."""

    def test_read_catchment_data(self):
        """Read raw catchment data as LazyFrame."""
        result = data.read_catchment_data("Au Saumon")
        assert isinstance(result, pl.LazyFrame)
        collected = result.collect()
        assert "Date" in collected.columns

    def test_date_column_parsed(self):
        """Date column is parsed as Date type."""
        result = data.read_catchment_data("Au Saumon").collect()
        assert result["Date"].dtype == pl.Date


class TestReadProjectionData:
    """Tests for read_projection_data function."""

    def test_read_projection_data_if_exists(self):
        """Projection data loading (if file exists)."""
        projection_path = data_dir / "Au Saumon_Projections.csv"
        if projection_path.exists():
            result = data.read_projection_data("Au Saumon")
            assert isinstance(result, pl.LazyFrame)


class TestGetAvailablePeriod:
    """Tests for _get_available_period function."""

    def test_get_available_period(self):
        """Date range extraction returns valid strings."""
        min_date, max_date = data._get_available_period("Au Saumon")
        assert isinstance(min_date, str)
        assert isinstance(max_date, str)
        # Should be valid date strings
        datetime.strptime(min_date, "%Y-%m-%d")
        datetime.strptime(max_date, "%Y-%m-%d")

    def test_min_less_than_max(self):
        """Min date should be less than max date."""
        min_date, max_date = data._get_available_period("Au Saumon")
        assert min_date < max_date

    def test_missing_file_raises_error(self):
        """Error for non-existent catchment."""
        with pytest.raises(FileNotFoundError):
            data._get_available_period("NonExistent")

"""Unit tests for holmes.data module."""

import csv
from datetime import datetime, timedelta
from unittest.mock import mock_open, patch

import polars as pl
import pytest

from holmes import data
from holmes.exceptions import HolmesDataError
from holmes.utils.paths import data_dir


class TestReadData:
    """Tests for read_data function."""

    def test_read_data_basic(self):
        """Load data with date range."""
        result, warmup_steps = data.read_data(
            "Au Saumon", "2000-01-01", "2005-12-31"
        )
        assert isinstance(result, pl.DataFrame)
        assert isinstance(warmup_steps, int)
        assert warmup_steps >= 0
        assert "date" in result.columns
        assert "precipitation" in result.columns
        assert "pet" in result.columns
        assert "streamflow" in result.columns
        assert "temperature" in result.columns

    def test_read_data_with_warmup(self):
        """Verify warmup period calculation (3 years by default)."""
        from datetime import date

        # Use dates within the available data range (1975-03-01 to 2003-12-31)
        start = "2000-01-01"
        end = "2003-12-31"
        result, warmup_steps = data.read_data("Au Saumon", start, end)
        expected_start = datetime.strptime(start, "%Y-%m-%d") - timedelta(
            days=365 * 3
        )
        min_date = result["date"].min()
        assert isinstance(min_date, date)
        assert min_date <= expected_start.date()
        # Warmup steps should be approximately 3 years
        assert warmup_steps > 0

    def test_read_data_custom_warmup(self):
        """Verify custom warmup period is shorter than default."""
        # Use dates within the available data range (1975-03-01 to 2003-12-31)
        start = "2000-01-01"
        end = "2003-12-31"
        result_default, warmup_default = data.read_data(
            "Au Saumon", start, end
        )
        result_short, warmup_short = data.read_data(
            "Au Saumon", start, end, warmup_length=1
        )
        # Shorter warmup should have fewer rows
        assert len(result_short) < len(result_default)
        # Shorter warmup should have fewer warmup steps
        assert warmup_short < warmup_default

    def test_read_data_all_catchments(self):
        """Verify all catchments can be read."""
        for (
            catchment_name,
            _,
            (start_avail, end_avail),
        ) in data.get_available_catchments():
            # Use the available date range for each catchment
            result, warmup_steps = data.read_data(
                catchment_name, start_avail, end_avail
            )
            assert isinstance(result, pl.DataFrame)
            assert isinstance(warmup_steps, int)
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
        # Result is a tuple (for caching) of tuples
        assert isinstance(result, (list, tuple))
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
        with pytest.raises(HolmesDataError):
            data._get_available_period("NonExistent")


class TestAntiFragilityValidation:
    """Anti-fragility tests for input validation (P2-VAL)."""

    def test_invalid_date_format_validation(self):
        """P2-VAL-02: Invalid date formats should raise HolmesDataError."""
        with pytest.raises(HolmesDataError) as exc_info:
            data.read_data(
                "Au Saumon", "2000/01/01", "2005/12/31"
            )  # Wrong format
        assert "date format" in str(exc_info.value).lower()

    def test_date_range_validation(self):
        """P2-VAL-03: Start date must be before end date."""
        with pytest.raises(HolmesDataError) as exc_info:
            data.read_data(
                "Au Saumon", "2005-12-31", "2000-01-01"
            )  # End before start
        assert "start" in str(exc_info.value).lower()

    def test_catchment_existence_validation(self):
        """P2-VAL-04: Non-existent catchments should raise clear HolmesDataError."""
        with pytest.raises(HolmesDataError) as exc_info:
            data.read_data("NonExistentCatchment", "2000-01-01", "2005-12-31")
        assert "catchment" in str(exc_info.value).lower()

    def test_empty_date_filter_result(self):
        """P4-DATA-04: Empty result after date filtering should raise clear error."""
        with pytest.raises(HolmesDataError) as exc_info:
            # Date range with no data (before any data exists)
            data.read_data("Au Saumon", "1800-01-01", "1800-12-31")
        assert (
            "empty" in str(exc_info.value).lower()
            or "no data" in str(exc_info.value).lower()
        )


class TestDataErrorHandling:
    """Tests for error handling in data loading functions."""

    def test_read_catchment_data_file_not_found(self):
        """read_catchment_data with missing file raises HolmesDataError."""
        with pytest.raises(HolmesDataError) as exc_info:
            data.read_catchment_data("NonExistentCatchment")
        assert "not found" in str(exc_info.value).lower()

    def test_read_catchment_data_permission_error(self):
        """read_catchment_data with permission error raises HolmesDataError."""
        with patch(
            "polars.scan_csv", side_effect=PermissionError("Access denied")
        ):
            with pytest.raises(HolmesDataError) as exc_info:
                data.read_catchment_data("Au Saumon")
            assert "permission" in str(exc_info.value).lower()

    def test_read_catchment_data_compute_error(self):
        """read_catchment_data with CSV parse error raises HolmesDataError."""
        with patch(
            "polars.scan_csv",
            side_effect=pl.exceptions.ComputeError("Invalid CSV"),
        ):
            with pytest.raises(HolmesDataError) as exc_info:
                data.read_catchment_data("Au Saumon")
            assert "failed to parse" in str(exc_info.value).lower()

    def test_read_catchment_data_schema_error(self):
        """read_catchment_data with schema read error raises HolmesDataError."""
        mock_lf = pl.LazyFrame({"X": [1]})
        with patch("polars.scan_csv", return_value=mock_lf):
            with patch.object(
                mock_lf,
                "collect_schema",
                side_effect=pl.exceptions.ComputeError("Schema error"),
            ):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_catchment_data("Au Saumon")
                assert "schema" in str(exc_info.value).lower()

    def test_read_catchment_data_missing_required_columns(self):
        """read_catchment_data with missing columns raises HolmesDataError."""
        # Create a mock LazyFrame missing required columns
        mock_lf = pl.LazyFrame({"X": [1], "Y": [2]})
        with patch("polars.scan_csv", return_value=mock_lf):
            with pytest.raises(HolmesDataError) as exc_info:
                data.read_catchment_data("Au Saumon")
            assert "missing required columns" in str(exc_info.value).lower()

    def test_read_cemaneige_permission_error(self):
        """read_cemaneige_info with permission error raises HolmesDataError."""
        with patch(
            "builtins.open", side_effect=PermissionError("Access denied")
        ):
            with pytest.raises(HolmesDataError) as exc_info:
                data.read_cemaneige_info("Au Saumon")
            assert "permission" in str(exc_info.value).lower()

    def test_read_cemaneige_csv_error(self):
        """read_cemaneige_info with CSV parse error raises HolmesDataError."""
        m = mock_open(read_data="invalid,csv\ndata")
        with patch("builtins.open", m):
            with patch("csv.reader", side_effect=csv.Error("CSV parse error")):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_cemaneige_info("Au Saumon")
                assert "parse" in str(exc_info.value).lower()

    def test_read_cemaneige_missing_keys(self):
        """read_cemaneige_info with missing keys raises HolmesDataError."""

        def mock_csv_reader(*args, **kwargs):
            # Return a reader that yields only partial data
            return iter([("SomeKey", "SomeValue")])

        m = mock_open(read_data="SomeKey,SomeValue")
        with patch("builtins.open", m):
            with patch("csv.reader", mock_csv_reader):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_cemaneige_info("Au Saumon")
                assert "missing required keys" in str(exc_info.value).lower()

    def test_read_cemaneige_empty_altiband(self):
        """read_cemaneige_info with empty AltiBand raises HolmesDataError."""

        def mock_csv_reader(*args, **kwargs):
            return iter(
                [
                    ("AltiBand", ""),  # Empty altitude band
                    ("QNBV", "1.0"),
                    ("Z50", "500"),
                    ("Lat", "45.0"),
                ]
            )

        m = mock_open()
        with patch("builtins.open", m):
            with patch("csv.reader", mock_csv_reader):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_cemaneige_info("Au Saumon")
                assert "empty" in str(exc_info.value).lower()

    def test_read_cemaneige_no_altitude_layers(self):
        """read_cemaneige_info with only whitespace in AltiBand raises error."""

        def mock_csv_reader(*args, **kwargs):
            return iter(
                [
                    ("AltiBand", ";;;"),  # Only separators, no actual values
                    ("QNBV", "1.0"),
                    ("Z50", "500"),
                    ("Lat", "45.0"),
                ]
            )

        m = mock_open()
        with patch("builtins.open", m):
            with patch("csv.reader", mock_csv_reader):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_cemaneige_info("Au Saumon")
                assert "no altitude layers" in str(exc_info.value).lower()

    def test_read_cemaneige_invalid_altitude_value(self):
        """read_cemaneige_info with invalid altitude value raises HolmesDataError."""

        def mock_csv_reader(*args, **kwargs):
            return iter(
                [
                    ("AltiBand", "100;invalid;300"),  # Invalid number
                    ("QNBV", "1.0"),
                    ("Z50", "500"),
                    ("Lat", "45.0"),
                ]
            )

        m = mock_open()
        with patch("builtins.open", m):
            with patch("csv.reader", mock_csv_reader):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_cemaneige_info("Au Saumon")
                assert "invalid" in str(exc_info.value).lower()

    def test_read_cemaneige_invalid_numeric_value(self):
        """read_cemaneige_info with invalid QNBV/Z50/Lat raises HolmesDataError."""

        def mock_csv_reader(*args, **kwargs):
            return iter(
                [
                    ("AltiBand", "100;200;300"),
                    ("QNBV", "not_a_number"),  # Invalid
                    ("Z50", "500"),
                    ("Lat", "45.0"),
                ]
            )

        m = mock_open()
        with patch("builtins.open", m):
            with patch("csv.reader", mock_csv_reader):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_cemaneige_info("Au Saumon")
                assert "invalid numeric" in str(exc_info.value).lower()

    def test_read_projection_permission_error(self):
        """read_projection_data with permission error raises HolmesDataError."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "polars.scan_csv", side_effect=PermissionError("Access denied")
            ):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_projection_data("Au Saumon")
                assert "permission" in str(exc_info.value).lower()

    def test_read_projection_compute_error(self):
        """read_projection_data with CSV parse error raises HolmesDataError."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "polars.scan_csv",
                side_effect=pl.exceptions.ComputeError("Parse error"),
            ):
                with pytest.raises(HolmesDataError) as exc_info:
                    data.read_projection_data("Au Saumon")
                assert "failed to parse" in str(exc_info.value).lower()

    def test_get_available_period_compute_error(self):
        """_get_available_period with compute error raises HolmesDataError."""
        # Mock scan_csv to return a LazyFrame that errors on collect
        mock_lf = pl.LazyFrame({"Date": ["invalid"]})

        with patch("polars.scan_csv", return_value=mock_lf):
            with patch.object(
                pl.LazyFrame,
                "collect",
                side_effect=pl.exceptions.ComputeError("Compute error"),
            ):
                with pytest.raises(HolmesDataError) as exc_info:
                    data._get_available_period("Au Saumon")
                assert "failed to read" in str(exc_info.value).lower()

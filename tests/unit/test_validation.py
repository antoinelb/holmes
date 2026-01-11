"""Tests for HOLMES validation utilities."""

from datetime import datetime

import numpy as np
import pytest

from holmes.validation import (
    validate_array_length,
    validate_array_no_nan,
    validate_catchment_exists,
    validate_date_format,
    validate_date_range,
    validate_host,
    validate_parameter_bounds,
    validate_port,
    validate_ws_message_keys,
)


class TestValidateDateFormat:
    """Tests for validate_date_format function."""

    def test_valid_date_default_format(self):
        """Valid date with default format should return datetime."""
        result = validate_date_format("2023-06-15")
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 6
        assert result.day == 15

    def test_valid_date_custom_format(self):
        """Valid date with custom format should return datetime."""
        result = validate_date_format("15/06/2023", "%d/%m/%Y")
        assert result.year == 2023
        assert result.month == 6
        assert result.day == 15

    def test_invalid_date_format(self):
        """Invalid date format should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_date_format("2023/06/15")  # Wrong separator
        assert "Invalid date format" in str(exc_info.value)
        assert "2023/06/15" in str(exc_info.value)

    def test_invalid_date_value(self):
        """Invalid date value should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_date_format("2023-02-30")  # February 30 doesn't exist
        assert "Invalid date format" in str(exc_info.value)

    def test_empty_string(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            validate_date_format("")


class TestValidateDateRange:
    """Tests for validate_date_range function."""

    def test_valid_date_range(self):
        """Valid date range should return tuple of datetimes."""
        start, end = validate_date_range("2020-01-01", "2020-12-31")
        assert start < end
        assert start.year == 2020
        assert end.month == 12

    def test_same_dates(self):
        """Same start and end date should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_date_range("2020-06-15", "2020-06-15")
        assert "must be before" in str(exc_info.value)

    def test_end_before_start(self):
        """End date before start date should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_date_range("2020-12-31", "2020-01-01")
        assert "must be before" in str(exc_info.value)

    def test_invalid_start_format(self):
        """Invalid start date format should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_date_range("01-01-2020", "2020-12-31")
        assert "Invalid date format" in str(exc_info.value)

    def test_invalid_end_format(self):
        """Invalid end date format should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_date_range("2020-01-01", "31-12-2020")
        assert "Invalid date format" in str(exc_info.value)


class TestValidateCatchmentExists:
    """Tests for validate_catchment_exists function."""

    def test_existing_catchment(self):
        """Existing catchment should not raise."""
        # This test depends on actual data files
        # Using "Au Saumon" which is known to exist in test data
        validate_catchment_exists("Au Saumon")  # Should not raise

    def test_nonexistent_catchment(self):
        """Non-existent catchment should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_catchment_exists("NonExistentCatchment12345")
        assert "not found" in str(exc_info.value)
        assert "Available catchments" in str(exc_info.value)

    def test_empty_catchment_name(self):
        """Empty catchment name should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_catchment_exists("")
        assert "not found" in str(exc_info.value)


class TestValidatePort:
    """Tests for validate_port function."""

    def test_valid_port_min(self):
        """Minimum valid port (1) should return the port."""
        assert validate_port(1) == 1

    def test_valid_port_max(self):
        """Maximum valid port (65535) should return the port."""
        assert validate_port(65535) == 65535

    def test_valid_common_ports(self):
        """Common port numbers should be valid."""
        assert validate_port(80) == 80
        assert validate_port(443) == 443
        assert validate_port(8000) == 8000
        assert validate_port(8080) == 8080

    def test_port_zero(self):
        """Port 0 should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_port(0)
        assert "1-65535" in str(exc_info.value)

    def test_negative_port(self):
        """Negative port should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_port(-1)
        assert "invalid" in str(exc_info.value).lower()

    def test_port_too_high(self):
        """Port > 65535 should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_port(65536)
        assert "invalid" in str(exc_info.value).lower()


class TestValidateHost:
    """Tests for validate_host function."""

    def test_localhost_ip(self):
        """Localhost IP should be valid."""
        assert validate_host("127.0.0.1") == "127.0.0.1"

    def test_any_ip(self):
        """0.0.0.0 should be valid."""
        assert validate_host("0.0.0.0") == "0.0.0.0"

    def test_standard_ip(self):
        """Standard IPv4 should be valid."""
        assert validate_host("192.168.1.1") == "192.168.1.1"

    def test_ipv6_loopback(self):
        """IPv6 loopback should be valid."""
        assert validate_host("::1") == "::1"

    def test_localhost_hostname(self):
        """'localhost' hostname should be valid."""
        assert validate_host("localhost") == "localhost"

    def test_simple_hostname(self):
        """Simple hostname should be valid."""
        assert validate_host("myserver") == "myserver"

    def test_fqdn(self):
        """Fully qualified domain name should be valid."""
        assert validate_host("server.example.com") == "server.example.com"

    def test_invalid_ip(self):
        """Invalid IP should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_host("256.256.256.256")
        assert "Invalid host" in str(exc_info.value)

    def test_invalid_hostname_with_spaces(self):
        """Hostname with spaces should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_host("my server")
        assert "Invalid host" in str(exc_info.value)

    def test_empty_host(self):
        """Empty host should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_host("")
        assert "Invalid host" in str(exc_info.value)


class TestValidateArrayNoNan:
    """Tests for validate_array_no_nan function."""

    def test_valid_array(self):
        """Array without NaN/infinity should not raise."""
        arr = np.array([1.0, 2.0, 3.0, 4.0])
        validate_array_no_nan(arr, "test_array")  # Should not raise

    def test_array_with_nan(self):
        """Array with NaN should raise ValueError."""
        arr = np.array([1.0, np.nan, 3.0])
        with pytest.raises(ValueError) as exc_info:
            validate_array_no_nan(arr, "precipitation")
        assert "precipitation" in str(exc_info.value)
        assert "NaN or infinity" in str(exc_info.value)

    def test_array_with_positive_infinity(self):
        """Array with positive infinity should raise ValueError."""
        arr = np.array([1.0, np.inf, 3.0])
        with pytest.raises(ValueError) as exc_info:
            validate_array_no_nan(arr, "streamflow")
        assert "streamflow" in str(exc_info.value)

    def test_array_with_negative_infinity(self):
        """Array with negative infinity should raise ValueError."""
        arr = np.array([1.0, -np.inf, 3.0])
        with pytest.raises(ValueError) as exc_info:
            validate_array_no_nan(arr, "temperature")
        assert "temperature" in str(exc_info.value)

    def test_multiple_nan_indices(self):
        """Multiple NaN values should show indices."""
        arr = np.array([np.nan, 1.0, np.nan, 2.0, np.nan])
        with pytest.raises(ValueError) as exc_info:
            validate_array_no_nan(arr, "data")
        error_msg = str(exc_info.value)
        assert "indices" in error_msg

    def test_empty_array(self):
        """Empty array should be valid (no NaN to find)."""
        arr = np.array([])
        validate_array_no_nan(arr, "empty")  # Should not raise


class TestValidateArrayLength:
    """Tests for validate_array_length function."""

    def test_correct_length(self):
        """Array with correct length should not raise."""
        arr = np.array([1, 2, 3, 4, 5])
        validate_array_length(arr, 5, "params")  # Should not raise

    def test_incorrect_length_too_short(self):
        """Array too short should raise ValueError."""
        arr = np.array([1, 2, 3])
        with pytest.raises(ValueError) as exc_info:
            validate_array_length(arr, 5, "params")
        assert "params" in str(exc_info.value)
        assert "length 3" in str(exc_info.value)
        assert "expected 5" in str(exc_info.value)

    def test_incorrect_length_too_long(self):
        """Array too long should raise ValueError."""
        arr = np.array([1, 2, 3, 4, 5, 6, 7])
        with pytest.raises(ValueError) as exc_info:
            validate_array_length(arr, 5, "params")
        assert "length 7" in str(exc_info.value)

    def test_empty_array_expected_zero(self):
        """Empty array when expecting 0 should not raise."""
        arr = np.array([])
        validate_array_length(arr, 0, "empty")  # Should not raise

    def test_empty_array_expected_nonzero(self):
        """Empty array when expecting non-zero should raise."""
        arr = np.array([])
        with pytest.raises(ValueError):
            validate_array_length(arr, 5, "data")


class TestValidateParameterBounds:
    """Tests for validate_parameter_bounds function."""

    def test_all_params_in_bounds(self):
        """All parameters in bounds should not raise."""
        params = np.array([0.5, 100.0, 0.01])
        bounds = [(0.0, 1.0), (0.0, 200.0), (0.0, 1.0)]
        names = ["x1", "x2", "x3"]
        validate_parameter_bounds(params, bounds, names)  # Should not raise

    def test_param_at_lower_bound(self):
        """Parameter exactly at lower bound should be valid."""
        params = np.array([0.0])
        bounds = [(0.0, 1.0)]
        names = ["x1"]
        validate_parameter_bounds(params, bounds, names)  # Should not raise

    def test_param_at_upper_bound(self):
        """Parameter exactly at upper bound should be valid."""
        params = np.array([1.0])
        bounds = [(0.0, 1.0)]
        names = ["x1"]
        validate_parameter_bounds(params, bounds, names)  # Should not raise

    def test_param_below_lower_bound(self):
        """Parameter below lower bound should raise ValueError."""
        params = np.array([-0.1])
        bounds = [(0.0, 1.0)]
        names = ["x1"]
        with pytest.raises(ValueError) as exc_info:
            validate_parameter_bounds(params, bounds, names)
        assert "x1" in str(exc_info.value)
        assert "outside bounds" in str(exc_info.value)

    def test_param_above_upper_bound(self):
        """Parameter above upper bound should raise ValueError."""
        params = np.array([1.5])
        bounds = [(0.0, 1.0)]
        names = ["x1"]
        with pytest.raises(ValueError) as exc_info:
            validate_parameter_bounds(params, bounds, names)
        assert "x1" in str(exc_info.value)
        assert "[0.0, 1.0]" in str(exc_info.value)

    def test_multiple_params_one_invalid(self):
        """Multiple parameters with one invalid should report the invalid one."""
        params = np.array([0.5, 300.0, 0.5])  # Second param out of bounds
        bounds = [(0.0, 1.0), (0.0, 200.0), (0.0, 1.0)]
        names = ["x1", "x2", "x3"]
        with pytest.raises(ValueError) as exc_info:
            validate_parameter_bounds(params, bounds, names)
        assert "x2" in str(exc_info.value)
        assert "300.0" in str(exc_info.value)


class TestValidateWsMessageKeys:
    """Tests for validate_ws_message_keys function."""

    def test_all_keys_present(self):
        """Message with all required keys should not raise."""
        msg = {"type": "config", "data": {"start": "2020-01-01"}}
        validate_ws_message_keys(msg, ["type", "data"])  # Should not raise

    def test_extra_keys_ok(self):
        """Extra keys beyond required should be allowed."""
        msg = {"type": "config", "data": {}, "extra": "ignored"}
        validate_ws_message_keys(msg, ["type", "data"])  # Should not raise

    def test_missing_single_key(self):
        """Missing single required key should raise ValueError."""
        msg = {"type": "config"}
        with pytest.raises(ValueError) as exc_info:
            validate_ws_message_keys(msg, ["type", "data"])
        assert "data" in str(exc_info.value)
        assert "Missing" in str(exc_info.value)

    def test_missing_multiple_keys(self):
        """Missing multiple required keys should list all missing."""
        msg = {"extra": "value"}
        with pytest.raises(ValueError) as exc_info:
            validate_ws_message_keys(msg, ["type", "data", "config"])
        error_msg = str(exc_info.value)
        assert "type" in error_msg
        assert "data" in error_msg
        assert "config" in error_msg

    def test_empty_message(self):
        """Empty message should raise if any keys required."""
        with pytest.raises(ValueError):
            validate_ws_message_keys({}, ["type"])

    def test_no_required_keys(self):
        """No required keys should not raise for any message."""
        validate_ws_message_keys({}, [])  # Should not raise
        validate_ws_message_keys({"any": "thing"}, [])  # Should not raise

    def test_custom_context(self):
        """Custom context should appear in error message."""
        msg = {}
        with pytest.raises(ValueError) as exc_info:
            validate_ws_message_keys(
                msg, ["type"], context="calibration config"
            )
        assert "calibration config" in str(exc_info.value)

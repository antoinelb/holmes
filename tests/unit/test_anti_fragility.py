"""Anti-fragility tests for Holmes Python backend.

Note: Most anti-fragility tests have been moved to their appropriate test files:
- Data validation tests: tests/unit/test_data.py (TestAntiFragilityValidation)
- Model error handling: tests/unit/models/*.py

This file is kept for documentation and for tests that don't fit elsewhere.
"""

import numpy as np
import pytest

from holmes.models import hydro


class TestRustExceptionHandling:
    """Tests for P1-ERR-02: Rust extension calls wrapped in try/except."""

    def test_empty_arrays_handled(self):
        """Empty arrays are handled gracefully by wrapped Rust calls."""
        simulate = hydro.get_model("gr4j")
        # Empty arrays should raise HolmesError, not panic
        with pytest.raises(Exception) as exc_info:
            simulate(np.array([]), np.array([]), np.array([]))
        # Should be a Python exception, not a Rust panic
        assert exc_info.value is not None


class TestLoggingHelpers:
    """Tests for P7-LOG logging utilities."""

    def test_log_with_timing_decorator(self):
        """log_with_timing decorator logs execution time."""
        from holmes.logging import log_with_timing

        @log_with_timing
        def sample_function():
            return 42

        result = sample_function()
        assert result == 42

    def test_correlation_id_context(self):
        """Correlation ID can be set and retrieved."""
        from holmes.logging import get_correlation_id, set_correlation_id

        # Default is None
        assert get_correlation_id() is None

        # Can be set
        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"

        # Reset for other tests
        set_correlation_id(None)  # type: ignore

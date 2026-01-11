"""
Tests for PET module PyO3 bindings.

These tests verify that Oudin PET calculation works correctly from Python.
"""

import numpy as np
import pytest

from holmes_rs import HolmesValidationError
from holmes_rs.pet import oudin


class TestOudinSimulate:
    """Tests for oudin.simulate function."""

    def test_output_length(self, sample_temperature, sample_doy):
        """Output should have same length as input."""
        latitude = 45.0

        pet = oudin.simulate(sample_temperature, sample_doy, latitude)

        assert len(pet) == len(sample_temperature)

    def test_nonnegative_pet(self, sample_temperature, sample_doy):
        """All PET values should be non-negative."""
        latitude = 45.0

        pet = oudin.simulate(sample_temperature, sample_doy, latitude)

        assert np.all(pet >= 0)

    def test_finite_output(self, sample_temperature, sample_doy):
        """All output values should be finite."""
        latitude = 45.0

        pet = oudin.simulate(sample_temperature, sample_doy, latitude)

        assert np.all(np.isfinite(pet))

    def test_equator(self):
        """Should work at equator (latitude = 0)."""
        n = 30
        temp = np.full(n, 25.0)
        doy = np.arange(1, n + 1, dtype=np.uint64)

        pet = oudin.simulate(temp, doy, 0.0)

        assert len(pet) == n
        assert np.all(pet >= 0)
        assert np.all(np.isfinite(pet))

    def test_northern_hemisphere(self):
        """Should work in northern hemisphere."""
        n = 30
        temp = np.full(n, 20.0)
        doy = np.arange(1, n + 1, dtype=np.uint64)

        pet = oudin.simulate(temp, doy, 45.0)

        assert len(pet) == n
        assert np.all(np.isfinite(pet))

    def test_southern_hemisphere(self):
        """Should work in southern hemisphere."""
        n = 30
        temp = np.full(n, 20.0)
        doy = np.arange(1, n + 1, dtype=np.uint64)

        pet = oudin.simulate(temp, doy, -35.0)

        assert len(pet) == n
        assert np.all(np.isfinite(pet))

    def test_higher_temp_more_pet(self):
        """Higher temperature should generally produce more PET."""
        n = 30
        doy = np.arange(1, n + 1, dtype=np.uint64)
        latitude = 45.0

        cold_temp = np.full(n, 5.0)
        warm_temp = np.full(n, 25.0)

        cold_pet = oudin.simulate(cold_temp, doy, latitude)
        warm_pet = oudin.simulate(warm_temp, doy, latitude)

        assert np.sum(warm_pet) > np.sum(cold_pet)

    def test_summer_vs_winter(self):
        """Summer should have higher PET than winter at mid-latitudes."""
        latitude = 45.0
        temp = np.full(30, 15.0)  # Same temperature

        # Winter (January)
        winter_doy = np.arange(1, 31, dtype=np.uint64)
        winter_pet = oudin.simulate(temp, winter_doy, latitude)

        # Summer (July)
        summer_doy = np.arange(180, 210, dtype=np.uint64)
        summer_pet = oudin.simulate(temp, summer_doy, latitude)

        assert np.mean(summer_pet) > np.mean(winter_pet)

    def test_full_year(self):
        """Should handle full year of data."""
        n = 365
        temp = 15.0 + 10.0 * np.sin(2 * np.pi * np.arange(n) / 365)
        doy = np.arange(1, n + 1, dtype=np.uint64)
        latitude = 45.0

        pet = oudin.simulate(temp, doy, latitude)

        assert len(pet) == 365
        assert np.all(np.isfinite(pet))
        assert np.all(pet >= 0)

    def test_length_mismatch_error(self):
        """Should raise error for mismatched input lengths."""
        temp = np.array([15.0, 16.0, 17.0])
        doy = np.array([1, 2], dtype=np.uint64)

        with pytest.raises(HolmesValidationError, match="length"):
            oudin.simulate(temp, doy, 45.0)

    def test_cold_temperature(self):
        """Should handle cold temperatures (PET should be low or zero)."""
        n = 30
        temp = np.full(n, -10.0)  # Very cold
        doy = np.arange(1, n + 1, dtype=np.uint64)

        pet = oudin.simulate(temp, doy, 45.0)

        assert np.all(pet >= 0)  # Still non-negative
        assert np.all(np.isfinite(pet))

    def test_various_latitudes(self):
        """Should work at various latitudes."""
        n = 30
        temp = np.full(n, 20.0)
        doy = np.arange(1, n + 1, dtype=np.uint64)

        for lat in [-60, -30, 0, 30, 60]:
            pet = oudin.simulate(temp, doy, float(lat))
            assert len(pet) == n
            assert np.all(np.isfinite(pet))


class TestPetModuleIntegration:
    """Integration tests for PET module."""

    def test_module_structure(self):
        """PET module should have correct submodules."""
        from holmes_rs import pet

        assert hasattr(pet, "oudin")

    def test_oudin_has_simulate(self):
        """Oudin module should have simulate function."""
        assert hasattr(oudin, "simulate")
        assert callable(oudin.simulate)

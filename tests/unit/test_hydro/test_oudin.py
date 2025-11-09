"""Comprehensive tests for src/hydro/oudin.py - Oudin PET model."""

import numpy as np
import pytest
from src.hydro import oudin


class TestRunOudin:
    """Tests for run_oudin function."""

    def test_run_oudin_basic(self):
        """Should calculate PET for basic inputs."""
        n_days = 10
        temperature = np.random.uniform(10, 25, n_days)
        latitude = 45.5
        day_of_year = np.arange(1, n_days + 1)

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        assert isinstance(pet, np.ndarray)
        assert len(pet) == n_days
        assert np.all(pet >= 0)

    def test_run_oudin_cold_temperature(self):
        """Should handle cold temperatures (below threshold)."""
        n_days = 10
        temperature = np.full(n_days, -5.0)  # Cold temperatures
        latitude = 45.5
        day_of_year = np.arange(1, n_days + 1)

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        # PET should be 0 or very low for cold temps
        assert isinstance(pet, np.ndarray)
        assert len(pet) == n_days
        # When T < -5, PET should be 0
        assert np.all(pet == 0)

    def test_run_oudin_warm_temperature(self):
        """Should calculate higher PET for warm temperatures."""
        n_days = 10
        temperature = np.full(n_days, 25.0)  # Warm temperatures
        latitude = 45.5
        day_of_year = np.arange(1, n_days + 1)

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        assert isinstance(pet, np.ndarray)
        assert len(pet) == n_days
        assert np.all(pet > 0)
        # Warm temps should give reasonable PET values
        assert np.all(pet < 20)  # Reasonable upper bound

    def test_run_oudin_different_latitudes(self):
        """Should handle different latitudes."""
        n_days = 10
        temperature = np.random.uniform(15, 25, n_days)
        day_of_year = np.arange(1, n_days + 1)

        # Test northern latitude
        pet_north = oudin.run_oudin(temperature, day_of_year, 60.0)
        # Test southern latitude
        pet_south = oudin.run_oudin(temperature, day_of_year, 30.0)

        assert isinstance(pet_north, np.ndarray)
        assert isinstance(pet_south, np.ndarray)
        # Both should be positive
        assert np.all(pet_north >= 0)
        assert np.all(pet_south >= 0)

    def test_run_oudin_year_long(self):
        """Should handle a full year of data."""
        n_days = 365
        temperature = 10 + 15 * np.sin(2 * np.pi * np.arange(n_days) / 365)
        latitude = 45.5
        day_of_year = np.arange(1, n_days + 1)

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        assert isinstance(pet, np.ndarray)
        assert len(pet) == n_days
        assert np.all(pet >= 0)
        # Should have variation throughout the year
        assert np.std(pet) > 0

    def test_run_oudin_leap_year(self):
        """Should handle leap year (366 days)."""
        n_days = 366
        temperature = 10 + 15 * np.sin(2 * np.pi * np.arange(n_days) / 366)
        latitude = 45.5
        day_of_year = np.arange(1, n_days + 1)

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        assert isinstance(pet, np.ndarray)
        assert len(pet) == n_days
        assert np.all(pet >= 0)

    def test_run_oudin_single_day(self):
        """Should handle single day calculation."""
        temperature = np.array([20.0])
        latitude = 45.5
        day_of_year = np.array([1])

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        assert isinstance(pet, np.ndarray)
        assert len(pet) == 1
        assert pet[0] >= 0

    def test_run_oudin_zero_temperature(self):
        """Should handle zero temperature."""
        n_days = 5
        temperature = np.zeros(n_days)
        latitude = 45.5
        day_of_year = np.arange(1, n_days + 1)

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        assert isinstance(pet, np.ndarray)
        assert len(pet) == n_days
        # At 0°C, PET should be small but positive
        assert np.all(pet >= 0)

    def test_run_oudin_mixed_temperatures(self):
        """Should handle mix of warm and cold temperatures."""
        temperature = np.array([-10, -5, 0, 5, 10, 15, 20, 25])
        latitude = 45.5
        day_of_year = np.arange(1, len(temperature) + 1)

        pet = oudin.run_oudin(temperature, day_of_year, latitude)

        assert isinstance(pet, np.ndarray)
        assert len(pet) == len(temperature)
        # All PET values should be non-negative
        assert np.all(pet >= 0)
        # Warm temps should give higher PET than cold temps
        assert pet[-1] > pet[0]

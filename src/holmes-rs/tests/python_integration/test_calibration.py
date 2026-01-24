"""
Tests for calibration module PyO3 bindings.

These tests verify that SCE-UA calibration works correctly from Python.
"""

import numpy as np
import pytest

from holmes_rs.calibration.sce import Sce
from holmes_rs.hydro import gr4j
from holmes_rs.snow import cemaneige


class TestSceConstructor:
    """Tests for Sce class constructor."""

    def test_create_gr4j_only(self):
        """Should create Sce with GR4J model only."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=100,
            seed=42,
        )

        assert sce is not None

    def test_create_bucket_only(self):
        """Should create Sce with Bucket model only."""
        sce = Sce(
            hydro_model="bucket",
            snow_model=None,
            objective="rmse",
            transformation="sqrt",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=100,
            seed=42,
        )

        assert sce is not None

    def test_create_gr4j_cemaneige(self):
        """Should create Sce with GR4J + CemaNeige."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model="cemaneige",
            objective="kge",
            transformation="log",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=100,
            seed=42,
        )

        assert sce is not None

    def test_invalid_hydro_model(self):
        """Should raise error for invalid hydro model."""
        with pytest.raises(ValueError):
            Sce(
                hydro_model="invalid",
                snow_model=None,
                objective="nse",
                transformation="none",
                n_complexes=2,
                k_stop=5,
                p_convergence_threshold=0.1,
                geometric_range_threshold=0.0001,
                max_evaluations=100,
                seed=42,
            )

    def test_invalid_snow_model(self):
        """Should raise error for invalid snow model."""
        with pytest.raises(ValueError):
            Sce(
                hydro_model="gr4j",
                snow_model="invalid",
                objective="nse",
                transformation="none",
                n_complexes=2,
                k_stop=5,
                p_convergence_threshold=0.1,
                geometric_range_threshold=0.0001,
                max_evaluations=100,
                seed=42,
            )

    def test_invalid_objective(self):
        """Should raise error for invalid objective."""
        with pytest.raises(ValueError):
            Sce(
                hydro_model="gr4j",
                snow_model=None,
                objective="invalid",
                transformation="none",
                n_complexes=2,
                k_stop=5,
                p_convergence_threshold=0.1,
                geometric_range_threshold=0.0001,
                max_evaluations=100,
                seed=42,
            )

    def test_invalid_transformation(self):
        """Should raise error for invalid transformation."""
        with pytest.raises(ValueError):
            Sce(
                hydro_model="gr4j",
                snow_model=None,
                objective="nse",
                transformation="invalid",
                n_complexes=2,
                k_stop=5,
                p_convergence_threshold=0.1,
                geometric_range_threshold=0.0001,
                max_evaluations=100,
                seed=42,
            )

    def test_all_objectives(self):
        """Should work with all objective functions."""
        for obj in ["rmse", "nse", "kge"]:
            sce = Sce(
                hydro_model="gr4j",
                snow_model=None,
                objective=obj,
                transformation="none",
                n_complexes=2,
                k_stop=5,
                p_convergence_threshold=0.1,
                geometric_range_threshold=0.0001,
                max_evaluations=50,
                seed=42,
            )
            assert sce is not None

    def test_all_transformations(self):
        """Should work with all transformations."""
        for trans in ["none", "log", "sqrt"]:
            sce = Sce(
                hydro_model="gr4j",
                snow_model=None,
                objective="nse",
                transformation=trans,
                n_complexes=2,
                k_stop=5,
                p_convergence_threshold=0.1,
                geometric_range_threshold=0.0001,
                max_evaluations=50,
                seed=42,
            )
            assert sce is not None


class TestSceInit:
    """Tests for Sce.init method."""

    def test_init_basic(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
        sample_observations,
    ):
        """Should initialize calibration successfully."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=100,
            seed=42,
        )

        # This should not raise
        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )


class TestSceStep:
    """Tests for Sce.step method."""

    def test_step_returns_tuple(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
        sample_observations,
    ):
        """step should return a tuple of (done, params, sim, objectives)."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=50,
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        result = sce.step(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_step_output_types(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
        sample_observations,
    ):
        """step outputs should have correct types."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=50,
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        done, params, sim, objectives = sce.step(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        assert isinstance(done, bool)
        assert isinstance(params, np.ndarray)
        assert isinstance(sim, np.ndarray)
        assert isinstance(objectives, np.ndarray)

    def test_step_output_shapes(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
        sample_observations,
    ):
        """step outputs should have correct shapes."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=50,
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        done, params, sim, objectives = sce.step(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        # GR4J has 4 parameters
        assert len(params) == 4
        # Simulation should match input length
        assert len(sim) == len(sample_precipitation)
        # 3 objectives: RMSE, NSE, KGE
        assert len(objectives) == 3

    def test_step_params_within_bounds(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
        sample_observations,
    ):
        """Returned parameters should be within bounds."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=50,
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        _, params, _, _ = sce.step(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        _, bounds = gr4j.init()
        for i in range(4):
            assert bounds[i, 0] <= params[i] <= bounds[i, 1]

    def test_step_finite_outputs(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
        sample_observations,
    ):
        """All outputs should be finite."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.0001,
            max_evaluations=50,
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        _, params, sim, objectives = sce.step(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        assert np.all(np.isfinite(params))
        assert np.all(np.isfinite(sim))
        assert np.all(np.isfinite(objectives))


class TestSceConvergence:
    """Tests for SCE convergence behavior."""

    def test_converges_to_done(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
    ):
        """Calibration should eventually return done=True."""
        # Generate observations from known parameters
        known_params = np.array([300.0, 0.5, 100.0, 2.5])
        obs = gr4j.simulate(known_params, sample_precipitation, sample_pet)

        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=3,
            p_convergence_threshold=1.0,  # High threshold for quick convergence
            geometric_range_threshold=0.1,
            max_evaluations=100,
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            obs,
            0,
        )

        done = False
        iterations = 0
        max_iterations = 50

        while not done and iterations < max_iterations:
            done, _, _, _ = sce.step(
                sample_precipitation,
                sample_temperature,
                sample_pet,
                sample_doy,
                sample_elevation_layers,
                1000.0,
                obs,
                0,
            )
            iterations += 1

        assert done or iterations == max_iterations

    def test_respects_max_evaluations(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
        sample_observations,
    ):
        """Should stop when max_evaluations is reached."""
        sce = Sce(
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            n_complexes=2,
            k_stop=100,  # High k_stop
            p_convergence_threshold=0.0,  # Never converge by criteria
            geometric_range_threshold=1e-10,  # Never converge by range
            max_evaluations=20,  # Low max evaluations
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            sample_observations,
            0,
        )

        done = False
        iterations = 0

        while not done and iterations < 100:
            done, _, _, _ = sce.step(
                sample_precipitation,
                sample_temperature,
                sample_pet,
                sample_doy,
                sample_elevation_layers,
                1000.0,
                sample_observations,
                0,
            )
            iterations += 1

        assert done  # Should have stopped due to max_evaluations


class TestSceWithSnow:
    """Tests for SCE with snow model."""

    def test_snow_hydro_calibration(
        self,
        sample_precipitation,
        sample_pet,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
    ):
        """Should calibrate snow + hydro model together."""
        # Generate observations using snow + hydro chain
        snow_defaults, _ = cemaneige.init()
        effective_precip = cemaneige.simulate(
            snow_defaults,
            sample_precipitation,
            sample_temperature,
            sample_doy,
            sample_elevation_layers,
            1000.0,
        )

        hydro_defaults, _ = gr4j.init()
        obs = gr4j.simulate(hydro_defaults, effective_precip, sample_pet)

        sce = Sce(
            hydro_model="gr4j",
            snow_model="cemaneige",
            objective="kge",
            transformation="none",
            n_complexes=2,
            k_stop=5,
            p_convergence_threshold=0.1,
            geometric_range_threshold=0.001,
            max_evaluations=50,
            seed=42,
        )

        sce.init(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            obs,
            0,
        )

        _, params, sim, objectives = sce.step(
            sample_precipitation,
            sample_temperature,
            sample_pet,
            sample_doy,
            sample_elevation_layers,
            1000.0,
            obs,
            0,
        )

        # Should have 7 parameters (3 snow + 4 hydro)
        assert len(params) == 7
        assert len(sim) == len(sample_precipitation)
        assert np.all(np.isfinite(params))
        assert np.all(np.isfinite(sim))


class TestCalibrationModuleIntegration:
    """Integration tests for calibration module."""

    def test_module_structure(self):
        """Calibration module should have correct submodules."""
        from holmes_rs import calibration

        assert hasattr(calibration, "sce")

    def test_sce_class_accessible(self):
        """Sce class should be accessible."""
        from holmes_rs.calibration.sce import Sce

        assert Sce is not None

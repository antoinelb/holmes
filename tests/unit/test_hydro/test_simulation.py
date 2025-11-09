"""Comprehensive tests for src/hydro/simulation.py."""

import numpy as np
import polars as pl
import pytest
from src.hydro import simulation


class TestPlotSimulation:
    """Tests for plot_simulation function."""

    def test_plot_simulation_single_simulation(self):
        """Should create plot for single simulation."""
        # Create sample data
        n = 100
        dates = pl.date_range(
            pl.date(2020, 1, 1),
            pl.date(2020, 4, 9),
            interval="1d",
            eager=True,
        )
        df = pl.DataFrame({
            "date": dates,
            "flow": np.random.uniform(0, 10, n),
            "simulation_1": np.random.uniform(0, 10, n),
        })

        fig = simulation.plot_simulation(df)

        # Should return a plotly figure
        assert fig is not None
        assert hasattr(fig, "data")
        assert len(fig.data) > 0

    def test_plot_simulation_multiple_simulations(self):
        """Should create plot for multiple simulations."""
        n = 100
        dates = pl.date_range(
            pl.date(2020, 1, 1),
            pl.date(2020, 4, 9),
            interval="1d",
            eager=True,
        )
        df = pl.DataFrame({
            "date": dates,
            "flow": np.random.uniform(0, 10, n),
            "simulation_1": np.random.uniform(0, 10, n),
            "simulation_2": np.random.uniform(0, 10, n),
            "simulation_3": np.random.uniform(0, 10, n),
        })

        fig = simulation.plot_simulation(df)

        # Should have multiple traces
        assert fig is not None
        assert len(fig.data) >= 3  # At least flow + 2 simulations

    def test_plot_simulation_with_multimodel(self):
        """Should create plot with multimodel mean."""
        n = 100
        dates = pl.date_range(
            pl.date(2020, 1, 1),
            pl.date(2020, 4, 9),
            interval="1d",
            eager=True,
        )
        df = pl.DataFrame({
            "date": dates,
            "flow": np.random.uniform(0, 10, n),
            "simulation_1": np.random.uniform(0, 10, n),
            "simulation_2": np.random.uniform(0, 10, n),
            "multimodel": np.random.uniform(0, 10, n),
        })

        fig = simulation.plot_simulation(df)

        # Should include multimodel trace
        assert fig is not None
        assert len(fig.data) > 0

    def test_plot_simulation_with_template(self):
        """Should apply template to plot."""
        n = 50
        dates = pl.date_range(
            pl.date(2020, 1, 1),
            pl.date(2020, 2, 19),
            interval="1d",
            eager=True,
        )
        df = pl.DataFrame({
            "date": dates,
            "flow": np.random.uniform(0, 10, n),
            "simulation_1": np.random.uniform(0, 10, n),
        })

        fig = simulation.plot_simulation(df, template="simple_white")

        assert fig is not None
        assert fig.layout.template is not None

    def test_plot_simulation_empty_simulations(self):
        """Should handle dataframe with only flow column."""
        n = 50
        dates = pl.date_range(
            pl.date(2020, 1, 1),
            pl.date(2020, 2, 19),
            interval="1d",
            eager=True,
        )
        df = pl.DataFrame({
            "date": dates,
            "flow": np.random.uniform(0, 10, n),
        })

        fig = simulation.plot_simulation(df)

        # Should still create a plot with just the flow
        assert fig is not None
        assert len(fig.data) >= 1

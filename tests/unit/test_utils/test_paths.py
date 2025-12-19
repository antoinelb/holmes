"""Tests for holmes/utils/paths.py - path utilities."""

from pathlib import Path

from holmes.utils import paths


def test_root_dir_exists():
    """Root directory should exist."""
    assert paths.root_dir.exists()


def test_data_dir_exists():
    """Data directory should exist."""
    assert paths.data_dir.exists()


def test_data_dir_contains_observation_files():
    """Data directory should contain observation CSV files."""
    observation_files = list(paths.data_dir.glob("*_Observations.csv"))
    assert len(observation_files) > 0


def test_static_dir_exists():
    """Static directory should exist."""
    assert paths.static_dir.exists()


def test_static_dir_contains_index():
    """Static directory should contain index.html."""
    assert (paths.static_dir / "index.html").exists()


def test_root_dir_is_path_object():
    """root_dir should be a Path object."""
    assert isinstance(paths.root_dir, Path)


def test_data_dir_is_path_object():
    """data_dir should be a Path object."""
    assert isinstance(paths.data_dir, Path)


def test_static_dir_is_path_object():
    """static_dir should be a Path object."""
    assert isinstance(paths.static_dir, Path)

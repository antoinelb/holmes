"""Unit tests for holmes.utils.paths module."""

from pathlib import Path

from holmes.utils.paths import data_dir, root_dir, static_dir


class TestPaths:
    """Tests for path utilities."""

    def test_root_dir(self):
        """Root directory resolution."""
        assert isinstance(root_dir, Path)
        assert root_dir.exists()

    def test_data_dir(self):
        """Data directory exists."""
        assert isinstance(data_dir, Path)
        assert data_dir.exists()

    def test_static_dir(self):
        """Static directory exists."""
        assert isinstance(static_dir, Path)
        assert static_dir.exists()

    def test_data_dir_is_subdirectory_of_root(self):
        """Data directory is a subdirectory of root."""
        assert data_dir.parent.resolve() == root_dir.resolve()

    def test_static_dir_is_subdirectory_of_root(self):
        """Static directory is a subdirectory of root."""
        assert static_dir.parent.resolve() == root_dir.resolve()

    def test_data_dir_contains_csv_files(self):
        """Data directory contains CSV files."""
        csv_files = list(data_dir.glob("*.csv"))
        assert len(csv_files) > 0

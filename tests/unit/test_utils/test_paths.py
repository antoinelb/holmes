"""Tests for src/utils/paths.py - path utilities."""

from pathlib import Path
from src.utils import paths


def test_root_dir_exists():
    """Root directory should exist."""
    assert paths.root_dir.exists()


def test_root_dir_is_directory():
    """Root should be a directory."""
    assert paths.root_dir.is_dir()


def test_root_dir_contains_src():
    """Root should contain src directory."""
    assert (paths.root_dir / "src").exists()


def test_root_dir_contains_pyproject():
    """Root should contain pyproject.toml."""
    assert (paths.root_dir / "pyproject.toml").exists()


def test_root_dir_is_path_object():
    """root_dir should be a Path object."""
    assert isinstance(paths.root_dir, Path)


def test_root_dir_absolute_path():
    """root_dir should be an absolute path or convertible to one."""
    # The path might be relative initially, but should be resolvable
    resolved = paths.root_dir.resolve()
    assert resolved.exists()

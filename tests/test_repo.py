"""Checks on what the repository keeps out of git: the raw cache never goes in, the derived tables do."""

import subprocess

import pytest

from soudai import paths


def ignored(path):
    """Whether git would ignore `path`, judged by the ignore rules alone (--no-index)."""
    relative = path.relative_to(paths.ROOT).as_posix()
    result = subprocess.run(["git", "check-ignore", "-q", "--no-index", relative], cwd=paths.ROOT)
    assert result.returncode in (0, 1), f"git check-ignore failed for {relative}"
    return result.returncode == 0


@pytest.mark.parametrize("path", [paths.CACHE, paths.LOGS / "intake.log"])
def test_the_raw_cache_and_logs_are_ignored(path):
    assert ignored(path)


@pytest.mark.parametrize(
    "path",
    [paths.DERIVED / "intake.csv", paths.REFERENCE / "courts.csv", paths.EXPORT],
)
def test_the_derived_tables_reference_and_export_are_tracked(path):
    assert not ignored(path)

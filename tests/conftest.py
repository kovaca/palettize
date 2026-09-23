"""Shared fixtures and the golden-file comparison helper."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from palettize.core import Colormap, ColorStop
from palettize.scaling import get_linear_scaler

GOLDEN_DIR = Path(__file__).parent / "golden"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite golden files from current exporter output instead of comparing.",
    )


@pytest.fixture(scope="session")
def update_golden(pytestconfig: pytest.Config) -> bool:
    """Whether golden files should be rewritten rather than asserted against."""
    return bool(pytestconfig.getoption("--update-golden")) or bool(
        os.environ.get("PALETTIZE_UPDATE_GOLDEN")
    )


@pytest.fixture
def assert_golden(update_golden: bool):
    """Compare text against a stored golden file, or rewrite it when updating.

    Usage::

        assert_golden(output, "gdal/viridis_linear.txt")
    """

    def _assert(content: str, relative_path: str) -> None:
        path = GOLDEN_DIR / relative_path
        if update_golden:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return

        if not path.exists():
            raise AssertionError(
                f"Golden file '{relative_path}' does not exist. "
                f"Run 'pytest --update-golden' to create it."
            )

        expected = path.read_text(encoding="utf-8")
        if content != expected:
            raise AssertionError(
                f"Output does not match golden file '{relative_path}'.\n"
                f"Run 'pytest --update-golden' to accept the new output if the "
                f"change is intentional.\n"
                f"--- expected ---\n{expected[:800]}\n"
                f"--- actual ---\n{content[:800]}"
            )

    return _assert


# ----------------------------------------------------------------------
# Colormap fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def simple_colormap() -> Colormap:
    """A two-stop red-to-blue colormap."""
    return Colormap([ColorStop("red", 0.0), ColorStop("blue", 1.0)], name="TestMap")


@pytest.fixture
def three_stop_colormap() -> Colormap:
    """A blue-yellow-red colormap with a stop at the midpoint."""
    return Colormap(
        [ColorStop("blue", 0.0), ColorStop("yellow", 0.5), ColorStop("red", 1.0)],
        name="BlueYellowRed",
    )


@pytest.fixture
def alpha_colormap() -> Colormap:
    """A colormap whose final stop is semi-transparent."""
    return Colormap([ColorStop("red", 0.0), ColorStop((0, 0, 255, 128), 1.0)], name="AlphaMap")


@pytest.fixture
def viridis() -> Colormap:
    """The viridis preset, the reference well-behaved sequential colormap."""
    return Colormap.from_preset("viridis")


@pytest.fixture
def linear_scaler():
    """A linear scaler over the domain 0-100."""
    return get_linear_scaler(0, 100)

"""Tests for the top-level `palettize` package surface."""

from __future__ import annotations

import pytest

import palettize
from palettize import create_colormap
from palettize.core import Colormap


class TestVersion:
    def test_version_is_a_non_placeholder_string(self):
        assert isinstance(palettize.__version__, str)
        assert palettize.__version__

    def test_version_comes_from_package_metadata(self):
        from importlib.metadata import version

        assert palettize.__version__ == version("palettize")


class TestPublicSurface:
    def test_everything_in_all_is_importable(self):
        for name in palettize.__all__:
            assert hasattr(palettize, name), f"__all__ advertises missing '{name}'"

    def test_all_has_no_duplicates(self):
        # Ordering is enforced by ruff's RUF022, which groups constants, classes,
        # and functions rather than sorting by raw ASCII.
        assert len(palettize.__all__) == len(set(palettize.__all__))

    def test_all_covers_the_public_names_the_package_defines(self):
        undeclared = {
            name
            for name in vars(palettize)
            if not name.startswith("_")
            and name not in palettize.__all__
            # `annotations` is the __future__ import; submodules are reachable
            # but are not part of the flat API surface.
            and name != "annotations"
            and not isinstance(getattr(palettize, name), type(palettize))
        }
        assert undeclared == set()

    @pytest.mark.parametrize(
        "name",
        [
            "Colormap",
            "ColorStop",
            "create_colormap",
            "get_exporter",
            "get_scaler_by_name",
            "list_available_presets",
            "register_exporter",
        ],
    )
    def test_key_names_are_exported(self, name):
        assert name in palettize.__all__


class TestCreateColormap:
    def test_from_a_preset(self):
        cmap = create_colormap(preset="viridis")
        assert isinstance(cmap, Colormap)
        assert cmap.name == "viridis"

    def test_from_a_color_list(self):
        cmap = create_colormap(colors=["red", "blue"])
        assert len(cmap) == 2

    def test_name_overrides_the_preset_name(self):
        assert create_colormap(preset="viridis", name="Custom").name == "Custom"

    def test_interpolation_space_is_applied(self):
        cmap = create_colormap(colors=["red", "blue"], interpolation_space="srgb")
        assert cmap.interpolation_space == "srgb"
        # Straight sRGB interpolation passes through a dark purple midpoint,
        # unlike the perceptual path oklch takes.
        assert cmap.get_color(0.5).lower() == "#800080"

    def test_cut_is_applied(self):
        cut = create_colormap(preset="viridis", cut_start=0.25, cut_end=0.75)
        assert cut.get_color(0.0) == Colormap.from_preset("viridis").get_color(0.25)

    def test_neither_preset_nor_colors_is_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            create_colormap()

    def test_both_preset_and_colors_is_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            create_colormap(preset="viridis", colors=["red"])

    def test_empty_color_list_is_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            create_colormap(colors=[])

    def test_is_keyword_only(self):
        with pytest.raises(TypeError):
            create_colormap("viridis")  # type: ignore[misc]

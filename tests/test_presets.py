"""Tests for preset discovery, metadata, and search."""

from __future__ import annotations

import pytest

from palettize import presets
from palettize.core import Colormap
from palettize.exceptions import PresetNotFoundError


class TestLoadPresetData:
    def test_builtin_preset_loads(self):
        assert presets.load_preset_data("custom/grayscale") == ["#000000", "#FFFFFF"]

    def test_positioned_builtin_preset_loads(self):
        data = presets.load_preset_data("custom/custom_stops")
        assert data[1] == ("#FFFF00", 0.5)

    def test_cmap_preset_loads(self):
        assert len(presets.load_preset_data("viridis")) > 1

    def test_namespaced_cmap_preset_loads(self):
        assert len(presets.load_preset_data("matplotlib:magma")) > 1

    def test_unknown_preset_raises_with_a_hint(self):
        with pytest.raises(PresetNotFoundError, match="palettize list presets"):
            presets.load_preset_data("no_such_preset_xyz")

    def test_results_are_cached(self):
        first = presets.load_preset_data("cividis")
        assert presets.load_preset_data("cividis") is first


class TestListAvailablePresets:
    def test_includes_builtin_and_catalog_presets(self):
        names = presets.list_available_presets()
        assert "custom/grayscale" in names
        # The catalog is listed under fully qualified names; short aliases such
        # as plain "viridis" still resolve via load_preset_data.
        assert "bids:viridis" in names

    def test_short_aliases_resolve_even_though_only_full_names_are_listed(self):
        assert "viridis" not in presets.list_available_presets()
        assert presets.load_preset_data("viridis")

    def test_is_sorted_and_deduplicated(self):
        names = presets.list_available_presets()
        assert names == sorted(names)
        assert len(names) == len(set(names))

    def test_returns_a_substantial_catalog(self):
        assert len(presets.list_available_presets()) > 100


class TestPresetInfo:
    def test_builtin_presets_use_the_native_namespace(self):
        info = presets.get_preset_info("custom/grayscale")
        assert info.namespace == presets.NATIVE_NAMESPACE

    def test_catalog_metadata_is_surfaced(self):
        info = presets.get_preset_info("bids:viridis")
        assert info.category == "sequential"
        assert info.namespace == "bids"
        assert info.license

    def test_unknown_preset_has_no_info(self):
        assert presets.get_preset_info("no_such_preset_xyz") is None

    def test_short_name_strips_the_namespace(self):
        assert presets.get_preset_info("bids:viridis").short_name == "viridis"

    def test_short_name_of_an_unnamespaced_preset_is_unchanged(self):
        assert presets.get_preset_info("viridis").short_name == "viridis"


class TestSearch:
    def test_no_filters_returns_everything(self):
        assert len(presets.search_presets()) == len(presets.list_available_presets())

    def test_query_matches_a_substring_case_insensitively(self):
        assert all("viridis" in i.name.lower() for i in presets.search_presets("VIRIDIS"))

    def test_category_filter_is_exact(self):
        results = presets.search_presets(category="diverging")
        assert results and all(i.category == "diverging" for i in results)

    def test_namespace_filter_is_exact(self):
        results = presets.search_presets(namespace="colorbrewer")
        assert results and all(i.namespace == "colorbrewer" for i in results)

    def test_filters_combine(self):
        results = presets.search_presets(query="bu", category="sequential", namespace="colorbrewer")
        assert results
        for info in results:
            assert "bu" in info.name.lower()
            assert info.category == "sequential"
            assert info.namespace == "colorbrewer"

    def test_no_matches_returns_an_empty_list(self):
        assert presets.search_presets("definitely_not_a_preset_xyz") == []

    def test_results_are_sorted_by_name(self):
        names = [i.name for i in presets.search_presets(category="cyclic")]
        assert names == sorted(names)

    def test_every_result_can_actually_be_loaded(self):
        # Guards against the catalog advertising names that fail to resolve.
        for info in presets.search_presets(namespace="colorbrewer")[:10]:
            assert len(Colormap.from_preset(info.name)) >= 1


class TestCategories:
    def test_expected_categories_are_present(self):
        assert {"sequential", "diverging", "cyclic"} <= set(presets.list_categories())

    def test_every_category_has_members(self):
        for category in presets.list_categories():
            assert presets.search_presets(category=category)

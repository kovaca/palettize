"""Tests for exporter registration, lazy loading, and the plugin mechanism."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from palettize import exporters
from palettize.core import Colormap, ScalingFunction
from palettize.exporters import (
    BaseExporter,
    exporter_file_extension,
    get_exporter,
    list_available_exporters,
    load_plugin_exporters,
    register_exporter,
)
from palettize.exporters._options import Opt, OptionSpec


class DummyExporter(BaseExporter):
    """A minimal well-behaved exporter used to exercise the registry."""

    options = OptionSpec(Opt("greeting", str, "hello", "Text to emit."))

    @property
    def identifier(self) -> str:
        return "dummy_test_exporter"

    @property
    def name(self) -> str:
        return "Dummy Test Exporter"

    @property
    def default_file_extension(self) -> str:
        return "dummy"

    def export(self, colormap, scaler, domain_min, domain_max, options=None) -> str:
        return f"{self.resolve_options(options)['greeting']} {colormap.get_color(0.0)}"


class BrokenExporter(BaseExporter):
    """An exporter that explodes on construction."""

    def __init__(self) -> None:
        raise RuntimeError("this plugin is broken")

    @property
    def identifier(self) -> str:  # pragma: no cover - never constructed
        return "broken"

    @property
    def name(self) -> str:  # pragma: no cover - never constructed
        return "Broken"

    def export(self, colormap, scaler, domain_min, domain_max, options=None) -> str:
        return ""  # pragma: no cover - never constructed


class NotAnExporter:
    """A class that has nothing to do with BaseExporter."""


@pytest.fixture
def clean_registry():
    """Snapshot and restore the module-level registry around a test."""
    saved = dict(exporters._EXPORTER_REGISTRY)
    saved_loaded = exporters._PLUGINS_LOADED
    yield
    exporters._EXPORTER_REGISTRY.clear()
    exporters._EXPORTER_REGISTRY.update(saved)
    exporters._PLUGINS_LOADED = saved_loaded


class TestRegistration:
    def test_register_and_retrieve(self, clean_registry):
        register_exporter(DummyExporter())
        assert get_exporter("dummy_test_exporter").name == "Dummy Test Exporter"

    def test_duplicate_registration_is_refused(self, clean_registry):
        register_exporter(DummyExporter())
        with pytest.raises(ValueError, match="already registered"):
            register_exporter(DummyExporter())

    def test_overwrite_allows_replacement(self, clean_registry):
        register_exporter(DummyExporter())
        register_exporter(DummyExporter(), overwrite=True)

    def test_non_exporters_are_refused(self, clean_registry):
        with pytest.raises(TypeError, match="must be an instance of BaseExporter"):
            register_exporter(NotAnExporter())  # type: ignore[arg-type]

    def test_registered_exporter_appears_in_the_listing(self, clean_registry):
        register_exporter(DummyExporter())
        assert "dummy_test_exporter" in list_available_exporters()

    def test_repr_names_the_exporter(self):
        assert "dummy_test_exporter" in repr(DummyExporter())


class TestLazyLoading:
    def test_all_builtins_are_listed(self):
        listing = list_available_exporters()
        assert {"gdal", "qgis", "sld", "titiler", "mapgl", "observable", "gee"} <= set(listing)
        assert {"hex", "rgba", "hsl", "json", "css", "gimp", "svg"} <= set(listing)

    def test_listing_does_not_import_exporter_modules(self):
        """Names and extensions come from the registry table, so a bare listing
        must not pull in every exporter module."""
        for module in [m for m in sys.modules if m.startswith("palettize.exporters.")]:
            if module.rsplit(".", 1)[1] not in ("_base", "_options"):
                sys.modules.pop(module, None)
        exporters._EXPORTER_REGISTRY.clear()

        list_available_exporters()
        exporter_file_extension("gdal")

        assert "palettize.exporters.gdal" not in sys.modules

    def test_requesting_an_exporter_imports_and_caches_it(self):
        exporter = get_exporter("gdal")
        assert exporter is not None
        assert get_exporter("gdal") is exporter

    def test_extension_lookup_matches_the_instance(self):
        for identifier in list_available_exporters():
            assert (
                exporter_file_extension(identifier)
                == get_exporter(identifier).default_file_extension
            )

    def test_unknown_identifier_returns_none(self):
        assert get_exporter("no_such_exporter_xyz") is None

    def test_extension_of_an_unknown_identifier_is_none(self):
        assert exporter_file_extension("no_such_exporter_xyz") is None


class TestPluginLoading:
    def _entry_point(self, name: str, value: object):
        return SimpleNamespace(
            name=name,
            value=f"test:{name}",
            load=lambda: value,
        )

    def test_valid_plugin_is_registered(self, clean_registry, monkeypatch):
        monkeypatch.setattr(
            exporters.importlib.metadata,
            "entry_points",
            lambda group: [self._entry_point("dummy", DummyExporter)],
        )
        load_plugin_exporters(force_reload=True)
        assert get_exporter("dummy_test_exporter") is not None

    def test_non_exporter_plugin_is_skipped_with_a_warning(self, clean_registry, monkeypatch):
        monkeypatch.setattr(
            exporters.importlib.metadata,
            "entry_points",
            lambda group: [self._entry_point("bogus", NotAnExporter)],
        )
        with pytest.warns(RuntimeWarning, match="does not inherit from BaseExporter"):
            load_plugin_exporters(force_reload=True)

    def test_broken_plugin_is_skipped_with_a_warning(self, clean_registry, monkeypatch):
        monkeypatch.setattr(
            exporters.importlib.metadata,
            "entry_points",
            lambda group: [self._entry_point("broken", BrokenExporter)],
        )
        with pytest.warns(RuntimeWarning, match="Failed to load exporter plugin"):
            load_plugin_exporters(force_reload=True)

    def test_a_broken_plugin_does_not_block_a_good_one(self, clean_registry, monkeypatch):
        monkeypatch.setattr(
            exporters.importlib.metadata,
            "entry_points",
            lambda group: [
                self._entry_point("broken", BrokenExporter),
                self._entry_point("dummy", DummyExporter),
            ],
        )
        with pytest.warns(RuntimeWarning):
            load_plugin_exporters(force_reload=True)
        assert get_exporter("dummy_test_exporter") is not None

    def test_discovery_failure_is_survivable(self, clean_registry, monkeypatch):
        def explode(group):
            raise RuntimeError("entry point machinery is broken")

        monkeypatch.setattr(exporters.importlib.metadata, "entry_points", explode)
        with pytest.warns(RuntimeWarning, match="Could not discover exporter plugins"):
            load_plugin_exporters(force_reload=True)

    def test_plugins_load_only_once_without_force(self, clean_registry, monkeypatch):
        calls = []

        def counting(group):
            calls.append(group)
            return []

        monkeypatch.setattr(exporters.importlib.metadata, "entry_points", counting)
        load_plugin_exporters(force_reload=True)
        load_plugin_exporters()
        load_plugin_exporters()
        assert len(calls) == 1

    def test_a_plugin_may_override_a_builtin(self, clean_registry, monkeypatch):
        class OverridingExporter(DummyExporter):
            @property
            def identifier(self) -> str:
                return "hex"

            @property
            def name(self) -> str:
                return "Overridden Hex"

        monkeypatch.setattr(
            exporters.importlib.metadata,
            "entry_points",
            lambda group: [self._entry_point("hex", OverridingExporter)],
        )
        load_plugin_exporters(force_reload=True)
        assert get_exporter("hex").name == "Overridden Hex"


class TestBaseHelpers:
    def test_domain_validation_rejects_an_empty_interval(self):
        with pytest.raises(ValueError, match="domain_min must be less than domain_max"):
            BaseExporter.validate_domain(10, 10)

    def test_domain_validation_rejects_an_inverted_interval(self):
        with pytest.raises(ValueError, match="domain_min must be less than domain_max"):
            BaseExporter.validate_domain(10, 1)

    def test_sample_data_values_spans_the_domain(self):
        assert BaseExporter.sample_data_values(5, 0, 100) == [0, 25, 50, 75, 100]

    def test_sample_positions_matches_core(self):
        assert BaseExporter.sample_positions(3) == [0.0, 0.5, 1.0]

    def test_sample_scaled_pairs_values_with_colors(self, simple_colormap, linear_scaler):
        pairs = BaseExporter.sample_scaled(
            simple_colormap, linear_scaler, 3, 0, 100, output_format="hex"
        )
        assert [value for value, _ in pairs] == [0, 50, 100]
        assert pairs[0][1].lower() == "#ff0000"

    def test_dummy_exporter_round_trips_options(self, simple_colormap, linear_scaler):
        output = DummyExporter().export(
            simple_colormap, linear_scaler, 0, 100, options={"greeting": "hi"}
        )
        assert output.startswith("hi #")

    def test_scaling_function_type_is_exported(self):
        assert ScalingFunction is not None
        assert isinstance(Colormap.from_list(["red", "blue"]), Colormap)

"""Golden-file tests: byte-for-byte comparison of every exporter's output.

These catch unintended drift in export formats that substring assertions miss.
When a format change is deliberate, run ``pytest --update-golden`` and review
the resulting diff before committing it.
"""

from __future__ import annotations

import pytest

from palettize.core import Colormap
from palettize.exporters import (
    exporter_file_extension,
    get_exporter,
    list_available_exporters,
)
from palettize.scaling import get_linear_scaler, get_log_scaler

ALL_FORMATS = sorted(list_available_exporters())


def reference_colormap() -> Colormap:
    """A fixed three-stop colormap; deliberately not a preset, so golden files
    do not churn when the ``cmap`` dependency updates its palettes."""
    return Colormap.from_list(
        ["#0000ff", "#ffff00", "#ff0000"], name="RefMap", interpolation_space="oklch"
    )


class TestGoldenDefaults:
    """Every exporter at its defaults, over a fixed colormap and domain."""

    @pytest.mark.parametrize("identifier", ALL_FORMATS)
    def test_default_output_matches_golden(self, identifier, assert_golden):
        exporter = get_exporter(identifier)
        output = exporter.export(
            reference_colormap(),
            get_linear_scaler(0, 100),
            0,
            100,
            options={"num_colors": 5},
        )
        extension = exporter_file_extension(identifier) or "txt"
        assert_golden(output, f"{identifier}/default.{extension}")


class TestGoldenVariants:
    """Option combinations that exercise a materially different code path."""

    CASES = [
        ("hex", {"num_colors": 4, "output_format": "json"}, "hex_json"),
        ("hex", {"num_colors": 4, "output_format": "csv"}, "hex_csv"),
        ("rgba", {"num_colors": 3, "alpha_format": "float"}, "rgba_alpha_float"),
        ("hsl", {"num_colors": 3, "output_format": "tuple"}, "hsl_tuple"),
        ("json", {"num_colors": 3, "structure": "full"}, "json_full"),
        ("json", {"num_colors": 3, "structure": "array_objects"}, "json_objects"),
        ("json", {"num_colors": 3, "structure": "object", "indent": 0}, "json_compact"),
        ("css", {"num_colors": 2, "include_rgb": True, "include_hsl": True}, "css_all"),
        ("css", {"num_colors": 2, "selector": "", "color_format": "hsl"}, "css_bare"),
        ("gimp", {"num_colors": 3, "color_names": False, "columns": 4}, "gimp_plain"),
        ("svg", {"num_colors": 3, "full_svg": True}, "svg_full"),
        ("svg", {"num_colors": 3, "gradient_type": "radial"}, "svg_radial"),
        ("gdal", {"num_colors": 4, "nodata": False}, "gdal_no_nodata"),
        ("gdal", {"num_colors": 3, "verbose": True, "scale_type": "linear"}, "gdal_verbose"),
        ("gdal", {"num_colors": 3, "precision": 2}, "gdal_precision"),
        ("qgis", {"num_colors": 4, "ramp_type": "exact"}, "qgis_exact"),
        ("qgis", {"num_colors": 4, "opacity": 0.5, "tags": ["a", "b"]}, "qgis_opacity"),
        ("sld", {"num_colors": 3, "output_type": "values"}, "sld_values"),
        ("sld", {"num_colors": 3, "sld_version": "1.1.0", "band": 2}, "sld_11"),
        ("gee", {"num_colors": 3, "type": "sld"}, "gee_sld"),
        ("mapgl", {"num_colors": 3, "precision": 1}, "mapgl_precision"),
        ("observable", {"num_colors": 4, "type": "diverging", "pivot": 50}, "obs_diverging"),
        ("titiler", {"num_colors": 3}, "titiler_3"),
    ]

    @pytest.mark.parametrize("identifier,options,case", CASES, ids=[c[2] for c in CASES])
    def test_variant_matches_golden(self, identifier, options, case, assert_golden):
        exporter = get_exporter(identifier)
        output = exporter.export(
            reference_colormap(), get_linear_scaler(0, 100), 0, 100, options=options
        )
        extension = exporter_file_extension(identifier) or "txt"
        assert_golden(output, f"{identifier}/{case}.{extension}")


class TestGoldenScaling:
    """Domain- and scaler-aware exporters must actually use what they declare."""

    DOMAIN_AWARE = [f for f in ALL_FORMATS if get_exporter(f).uses_domain]
    SCALER_AWARE = [f for f in ALL_FORMATS if get_exporter(f).uses_scaler]

    @pytest.mark.parametrize("identifier", DOMAIN_AWARE)
    def test_log_scaled_output_matches_golden(self, identifier, assert_golden):
        exporter = get_exporter(identifier)
        output = exporter.export(
            reference_colormap(),
            get_log_scaler(1, 1000),
            1,
            1000,
            options={"num_colors": 5, "scale_type": "log"},
        )
        extension = exporter_file_extension(identifier) or "txt"
        assert_golden(output, f"{identifier}/log_scaled.{extension}")

    @pytest.mark.parametrize("identifier", SCALER_AWARE)
    def test_scaling_actually_changes_the_output(self, identifier):
        exporter = get_exporter(identifier)
        colormap = reference_colormap()
        linear = exporter.export(
            colormap, get_linear_scaler(1, 1000), 1, 1000, options={"num_colors": 5}
        )
        logarithmic = exporter.export(
            colormap, get_log_scaler(1, 1000), 1, 1000, options={"num_colors": 5}
        )
        assert linear != logarithmic, (
            f"'{identifier}' declares uses_scaler=True but ignores the scaler."
        )

    #: Options needed to make a format's domain visible. A few only write data
    #: values in their richer modes: `json` needs a structure that carries
    #: metadata, and `qgis` writes values only for discrete ramps (its gradient
    #: mode carries the domain through the scaler instead).
    DOMAIN_VISIBLE_OPTIONS = {
        "json": {"structure": "full"},
        "qgis": {"ramp_type": "exact"},
    }

    @pytest.mark.parametrize("identifier", DOMAIN_AWARE)
    def test_domain_reaches_the_output(self, identifier):
        """A domain-aware exporter must write its bounds into the output."""
        options: dict = {"num_colors": 4}
        options.update(self.DOMAIN_VISIBLE_OPTIONS.get(identifier, {}))
        output = get_exporter(identifier).export(
            reference_colormap(), get_linear_scaler(0, 512), 0, 512, options=options
        )
        assert "512" in output

    @pytest.mark.parametrize(
        "identifier", [f for f in ALL_FORMATS if not get_exporter(f).uses_domain]
    )
    def test_domain_free_exporters_ignore_the_domain(self, identifier):
        """Formats that declare no data axis must produce identical output
        regardless of domain, rather than quietly depending on it."""
        exporter = get_exporter(identifier)
        colormap = reference_colormap()
        narrow = exporter.export(colormap, get_linear_scaler(0, 1), 0, 1, options={"num_colors": 5})
        wide = exporter.export(
            colormap, get_linear_scaler(0, 999), 0, 999, options={"num_colors": 5}
        )
        assert narrow == wide, f"'{identifier}' declares uses_domain=False but its output changed."


class TestExporterContract:
    """Invariants every exporter must satisfy, checked across the whole registry."""

    @pytest.mark.parametrize("identifier", ALL_FORMATS)
    def test_output_is_deterministic(self, identifier):
        exporter = get_exporter(identifier)
        args = (reference_colormap(), get_linear_scaler(0, 100), 0, 100)
        first = exporter.export(*args, options={"num_colors": 5})
        second = exporter.export(*args, options={"num_colors": 5})
        assert first == second

    @pytest.mark.parametrize("identifier", ALL_FORMATS)
    def test_output_is_non_empty_text(self, identifier):
        output = get_exporter(identifier).export(
            reference_colormap(), get_linear_scaler(0, 100), 0, 100
        )
        assert isinstance(output, str) and output.strip()

    @pytest.mark.parametrize("identifier", ALL_FORMATS)
    def test_metadata_is_consistent_with_the_registry(self, identifier):
        exporter = get_exporter(identifier)
        assert exporter.identifier == identifier
        assert exporter.name == list_available_exporters()[identifier]
        assert exporter.default_file_extension == exporter_file_extension(identifier)

    @pytest.mark.parametrize("identifier", ALL_FORMATS)
    def test_handles_a_single_stop_colormap(self, identifier):
        flat = Colormap.from_list(["green"], name="Flat")
        assert get_exporter(identifier).export(
            flat, get_linear_scaler(0, 100), 0, 100, options={"num_colors": 3}
        )

    @pytest.mark.parametrize("identifier", ALL_FORMATS)
    def test_handles_alpha(self, identifier):
        translucent = Colormap.from_list(["red", "rgba(0,0,255,0.5)"], name="Alpha")
        assert get_exporter(identifier).export(
            translucent, get_linear_scaler(0, 100), 0, 100, options={"num_colors": 3}
        )

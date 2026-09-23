"""Exporter for Google Earth Engine (GEE) JavaScript snippets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar
from xml.sax.saxutils import quoteattr

from palettize.core import Colormap, ScalingFunction

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec


class GEEExporter(BaseExporter):
    """Google Earth Engine visualization palettes and SLD ramps."""

    uses_domain: ClassVar[bool] = True

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "type",
            str,
            "default",
            "Emit a visualization palette or a GEE-flavored SLD ramp.",
            choices=("default", "sld"),
        ),
    )

    @property
    def identifier(self) -> str:
        return "gee"

    @property
    def name(self) -> str:
        return "Google Earth Engine Snippet"

    @property
    def default_file_extension(self) -> str:
        return "js"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        self.validate_domain(domain_min, domain_max)
        num_colors = opts["num_colors"]

        if opts["type"] == "default":
            return self._export_palette(colormap, domain_min, domain_max, num_colors)
        return self._export_sld(colormap, scaler, domain_min, domain_max, num_colors)

    def _export_palette(
        self, colormap: Colormap, domain_min: float, domain_max: float, num_colors: int
    ) -> str:
        """A ``{min, max, palette}`` visualization dictionary."""
        # GEE palette entries are hex strings without the leading '#'.
        palette = ", ".join(f"'{color.lstrip('#')}'" for color in colormap.hex_colors(num_colors))
        return (
            f"var palettize_viz = {{min: {domain_min}, max: {domain_max}, palette: [{palette}]}};"
        )

    def _export_sld(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        num_colors: int,
    ) -> str:
        """An SLD ``RasterSymbolizer`` built as a concatenated JS string."""
        entries = []
        for data_value, color in self.sample_scaled(
            colormap, scaler, num_colors, domain_min, domain_max, output_format="hex"
        ):
            value = self._tidy(data_value)
            # The XML sits inside a single-quoted JS literal, so attribute values
            # need XML escaping and must not contain a bare apostrophe.
            attrs = (
                f"color={quoteattr(str(color))} "
                f"quantity={quoteattr(str(value))} "
                f"label={quoteattr(str(value))}"
            ).replace("'", "&apos;")
            entries.append(f"      '<ColorMapEntry {attrs} />' +")

        if entries:
            entries[-1] = entries[-1].rstrip(" +")

        body = "\n".join(entries)
        return (
            "var palettize_sld =\n"
            "  '<RasterSymbolizer>' +\n"
            '    \'<ColorMap type="ramp" extended="false" >\' +\n'
            f"{body}\n"
            "    '</ColorMap>' +\n"
            "  '</RasterSymbolizer>';"
        )

    @staticmethod
    def _tidy(value: float) -> float | int:
        """Round a data value, preferring an int when it is one."""
        if abs(value - round(value)) < 1e-9:
            return round(value)
        return round(value, 4)

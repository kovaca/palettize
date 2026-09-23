"""Exporter for GIMP Palette (.gpl) format."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction
from palettize.exceptions import ExporterOptionError

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec


def _parse_palette_name(value: Any) -> str:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise ExporterOptionError(
            f"Option 'palette_name' must not contain newlines. Got: {value!r}"
        )
    return text


class GIMPExporter(BaseExporter):
    """GIMP Palette (``.gpl``) files, also read by Inkscape and Krita."""

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "palette_name",
            str,
            None,
            "Palette name. Defaults to the colormap name, or 'Untitled'.",
            parser=_parse_palette_name,
        ),
        Opt("columns", int, 16, "Swatch columns to display in GIMP.", minimum=0),
        Opt("color_names", bool, True, "Append a 'color-{index}' name to each entry."),
    )

    @property
    def identifier(self) -> str:
        return "gimp"

    @property
    def name(self) -> str:
        return "GIMP Palette"

    @property
    def default_file_extension(self) -> str:
        return "gpl"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        """Export as a GIMP palette.

        The format is a short header followed by one ``R G B<tab>name`` line
        per color::

            GIMP Palette
            Name: Viridis
            Columns: 16
            #
             68  1  84	color-0
        """
        opts = self.resolve_options(options)
        palette_name = opts["palette_name"] or colormap.name or "Untitled"
        if "\n" in palette_name or "\r" in palette_name:
            raise ExporterOptionError("Option 'palette_name' must not contain newlines.")

        lines = [
            "GIMP Palette",
            f"Name: {palette_name}",
            f"Columns: {opts['columns']}",
            "#",
        ]
        for i, (r, g, b) in enumerate(colormap.rgb_colors(opts["num_colors"])):
            entry = f"{r:3d} {g:3d} {b:3d}"
            lines.append(f"{entry}\tcolor-{i}" if opts["color_names"] else entry)

        return "\n".join(lines)

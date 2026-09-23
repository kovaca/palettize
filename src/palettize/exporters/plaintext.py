"""Plain-text exporters: newline-delimited representations of color."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec


class HexExporter(BaseExporter):
    """Plain-text hash-prefixed hexadecimal colors."""

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "output_format",
            str,
            "lines",
            "How to lay out the hex values.",
            choices=("lines", "json", "json_nohash", "csv"),
        ),
    )

    @property
    def identifier(self) -> str:
        return "hex"

    @property
    def name(self) -> str:
        return "Plaintext Hashed Hexadecimal"

    @property
    def default_file_extension(self) -> str:
        return "txt"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        colors = colormap.hex_colors(opts["num_colors"])

        output_format = opts["output_format"]
        if output_format == "json":
            return json.dumps(colors, indent=2)
        if output_format == "json_nohash":
            return json.dumps([c.lstrip("#") for c in colors], indent=2)
        if output_format == "csv":
            return ", ".join(colors)
        return "\n".join(colors)


class RGBAExporter(BaseExporter):
    """Plain-text RGBA colors, suitable for CSS or direct parsing."""

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "output_format",
            str,
            "css",
            "How to lay out each color.",
            choices=("css", "tuple", "json"),
        ),
        Opt(
            "alpha_format",
            str,
            "int",
            "Alpha as a 0-255 integer or a 0.0-1.0 float.",
            choices=("int", "float"),
        ),
    )

    @property
    def identifier(self) -> str:
        return "rgba"

    @property
    def name(self) -> str:
        return "Plaintext RGBA"

    @property
    def default_file_extension(self) -> str:
        return "txt"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        output_format = opts["output_format"]
        as_float = opts["alpha_format"] == "float"

        rows: list[tuple[int, int, int, float | int]] = []
        for r, g, b, a in colormap.rgba_colors(opts["num_colors"]):
            rows.append((r, g, b, round(a / 255.0, 3) if as_float else a))

        if output_format == "json":
            return json.dumps([list(row) for row in rows], indent=2)
        if output_format == "tuple":
            return "\n".join(f"({r}, {g}, {b}, {a})" for r, g, b, a in rows)
        return "\n".join(f"rgba({r}, {g}, {b}, {a})" for r, g, b, a in rows)


class HSLExporter(BaseExporter):
    """Plain-text HSL colors."""

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "output_format",
            str,
            "css",
            "How to lay out each color.",
            choices=("css", "tuple", "json"),
        ),
    )

    @property
    def identifier(self) -> str:
        return "hsl"

    @property
    def name(self) -> str:
        return "Plaintext HSL"

    @property
    def default_file_extension(self) -> str:
        return "txt"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        output_format = opts["output_format"]
        samples = colormap.hsl_colors(opts["num_colors"])

        if output_format == "json":
            return json.dumps(
                [[round(h, 1), round(s, 1), round(v, 1)] for h, s, v in samples],
                indent=2,
            )
        if output_format == "tuple":
            return "\n".join(f"({h:.1f}, {s:.1f}, {v:.1f})" for h, s, v in samples)
        return "\n".join(f"hsl({h:.0f}, {s:.0f}%, {v:.0f}%)" for h, s, v in samples)

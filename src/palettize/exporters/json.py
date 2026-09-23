"""Exporter for JSON format colormaps."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec

_COLOR_FORMATS = {
    "hex": "hex",
    "rgb": "rgb_tuple",
    "rgba": "rgba_tuple",
    "hsl": "hsl_tuple",
}


class JSONExporter(BaseExporter):
    """Flexible JSON output with several structure and color-format options."""

    uses_domain: ClassVar[bool] = True

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "structure",
            str,
            "array",
            "Shape of the emitted JSON document.",
            choices=("array", "array_objects", "object", "full"),
        ),
        Opt(
            "color_format",
            str,
            "hex",
            "How each color is represented.",
            choices=tuple(_COLOR_FORMATS),
        ),
        Opt("indent", int, 2, "Indentation width; 0 emits compact JSON.", minimum=0),
    )

    @property
    def identifier(self) -> str:
        return "json"

    @property
    def name(self) -> str:
        return "JSON"

    @property
    def default_file_extension(self) -> str:
        return "json"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        num_colors = opts["num_colors"]
        structure = opts["structure"]

        colors = [
            self._as_json(color)
            for color in colormap.colors(
                num_colors, output_format=_COLOR_FORMATS[opts["color_format"]]
            )
        ]
        positions = self.sample_positions(num_colors)

        output: Any
        if structure == "array_objects":
            output = [
                {
                    "position": round(position, 4),
                    "value": round(domain_min + position * (domain_max - domain_min), 4),
                    "color": color,
                }
                for position, color in zip(positions, colors, strict=True)
            ]
        elif structure == "object":
            # 0-255 keys are the convention for raster colormaps.
            output = {
                str(round(position * 255)): color
                for position, color in zip(positions, colors, strict=True)
            }
        elif structure == "full":
            output = {
                "name": colormap.name or "unnamed",
                "num_colors": num_colors,
                "domain": [domain_min, domain_max],
                "interpolation_space": colormap.interpolation_space,
                "colors": colors,
            }
        else:
            output = colors

        return json.dumps(output, indent=opts["indent"] or None)

    @staticmethod
    def _as_json(color: Any) -> Any:
        """Convert a formatted color into a JSON-native value."""
        if isinstance(color, tuple):
            return [round(c, 1) if isinstance(c, float) else c for c in color]
        return color

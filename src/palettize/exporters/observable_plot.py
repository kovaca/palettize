"""Exporter for Observable Plot color scale definitions."""

from __future__ import annotations

import json
import warnings
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction

from ._base import BaseExporter
from ._options import Opt, OptionSpec

_D3_INTERPOLATORS = {
    "srgb": "d3.interpolateRgb",
    "lab": "d3.interpolateLab",
    "hcl": "d3.interpolateHcl",
    "oklch": "d3.interpolateHcl",
}


class ObservablePlotExporter(BaseExporter):
    """An Observable Plot color scale object.

    See https://observablehq.com/plot/features/scales
    """

    uses_domain: ClassVar[bool] = True

    options: ClassVar[OptionSpec] = OptionSpec(
        Opt("num_colors", int, None, "Number of colors in the range.", minimum=2),
        Opt(
            "type",
            str,
            None,
            "Plot scale type. Defaults to the scale used to build the colormap.",
        ),
        Opt("pivot", float, None, "Pivot value for diverging scales."),
        Opt("symmetric", bool, None, "Whether a diverging scale is symmetric."),
    )

    @property
    def identifier(self) -> str:
        return "observable"

    @property
    def name(self) -> str:
        return "Observable Plot Scale"

    @property
    def default_file_extension(self) -> str:
        return "json"

    def _interpolate_method(self, space: str) -> str:
        """Map a ColorAide space onto the closest d3-interpolate method."""
        space = space.lower()
        if space == "oklch":
            warnings.warn(
                "`oklch` space is approximated by `d3.interpolateHcl`.",
                UserWarning,
                stacklevel=2,
            )
        elif space not in _D3_INTERPOLATORS:
            warnings.warn(
                f"Unsupported interpolation space '{space}'. Defaulting to 'd3.interpolateRgb'.",
                UserWarning,
                stacklevel=2,
            )
        return _D3_INTERPOLATORS.get(space, "d3.interpolateRgb")

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        raw = options or {}

        scale_name = raw.get("scale_type", "linear")
        scale_type = {"power": "pow"}.get(scale_name, scale_name)
        if scale_name == "symlog":
            scale_type = "linear"
            warnings.warn(
                "`symlog` scale is not supported by Observable Plot. Defaulting to `linear` scale.",
                UserWarning,
                stacklevel=2,
            )

        result: dict[str, Any] = {
            "type": opts["type"] or scale_type,
            "domain": [domain_min, domain_max],
            "interpolate": self._interpolate_method(colormap.interpolation_space),
            "clamp": True,
        }

        num_colors = opts["num_colors"]
        if num_colors:
            result["range"] = colormap.hex_colors(num_colors)
        else:
            # Without an explicit count, fall back to the colormap's own stops.
            result["range"] = [stop.to_hex() for stop in colormap.stops]

        if result["type"] == "diverging":
            if opts["pivot"] is not None:
                result["pivot"] = opts["pivot"]
            if opts["symmetric"] is not None:
                result["symmetric"] = opts["symmetric"]

        return json.dumps(result, indent=2)

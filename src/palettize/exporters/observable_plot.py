from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter
from typing import Any, Dict, Optional
import json
import warnings


class ObservablePlotExporter(BaseExporter):
    """
    Exports a colormap to an Observable Plot color scale definition object.
    See: https://observablehq.com/plot/features/scales
    """

    @property
    def identifier(self) -> str:
        return "observable"

    @property
    def name(self) -> str:
        return "Observable Plot Scale"

    @property
    def default_file_extension(self) -> Optional[str]:
        return "json"

    def _get_interpolate_method(self, space: str) -> str:
        """Maps a coloraide space to a d3-interpolate method name."""
        space = space.lower()
        if space == "srgb":
            return "d3.interpolateRgb"
        if space == "lab":
            return "d3.interpolateLab"
        if space in ["hcl", "oklch"]:
            if space == "oklch":
                warnings.warn(
                    "`oklch` space is approximated by `d3.interpolateHcl`.", UserWarning
                )
            return "d3.interpolateHcl"

        warnings.warn(
            f"Unsupported interpolation space '{space}'. Defaulting to 'd3.interpolateRgb'.",
            UserWarning,
        )
        return "d3.interpolateRgb"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        opts = options or {}

        # Get scale type from options
        scaler_name = opts.get("scale_type", "linear")

        # Determine Observable Plot scale type
        scale_type_map = {"power": "pow"}
        scale_type = scale_type_map.get(scaler_name, scaler_name)
        if scaler_name == "symlog":
            scale_type = "linear"
            warnings.warn(
                "`symlog` scale is not supported by Observable Plot. Defaulting to `linear` scale.",
                UserWarning,
            )

        result: Dict[str, Any] = {
            "type": opts.get("type", scale_type),
            "domain": [domain_min, domain_max],
            "interpolate": self._get_interpolate_method(colormap.interpolation_space),
            "clamp": True,
        }

        # Generate the color range based on --steps if provided
        num_steps = opts.get("num_colors")
        if num_steps:
            color_range = []
            for i in range(num_steps):
                position = i / (num_steps - 1) if num_steps > 1 else 0.0
                color_range.append(colormap.get_color(position, output_format="hex"))
            result["range"] = color_range
        else:
            # Fallback to using the original stops
            result["range"] = [
                stop.parsed_color.convert("srgb").to_string(hex=True)
                for stop in colormap.stops
            ]

        # Handle diverging scales
        if result["type"] == "diverging":
            if "pivot" in opts:
                result["pivot"] = float(opts["pivot"])
            if "symmetric" in opts:
                result["symmetric"] = str(opts["symmetric"]).lower() in [
                    "true",
                    "1",
                    "yes",
                ]

        return json.dumps(result, indent=2)

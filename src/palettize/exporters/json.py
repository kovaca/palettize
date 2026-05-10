"""Exporter for JSON format colormaps."""

import json
from typing import Any, Dict, List, Optional, Union

from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter


class JSONExporter(BaseExporter):
    """
    Flexible JSON exporter with multiple structure and color format options.
    """

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
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to JSON format.

        Accepted options:
            num_colors (int): Number of color steps to generate. Default 256.
            structure (str): JSON structure. Options:
                - "array" (default): Simple array of colors ["#ff0000", ...]
                - "array_objects": Array of objects [{"position": 0, "color": "#ff0000"}, ...]
                - "object": Object with position keys {"0": "#ff0000", "128": "#00ff00", ...}
                - "full": Full metadata {"name": "...", "colors": [...], "domain": [...]}
            color_format (str): Color format. Options:
                - "hex" (default): Hex strings "#ff0000"
                - "rgb": RGB arrays [255, 0, 0]
                - "rgba": RGBA arrays [255, 0, 0, 255]
                - "hsl": HSL arrays [0, 100, 50]
            indent (int): JSON indentation. Default 2. Use 0 for compact output.
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        structure = options.get("structure", "array")
        color_format = options.get("color_format", "hex")
        indent = options.get("indent", 2)

        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        if structure not in ("array", "array_objects", "object", "full"):
            raise ValueError(
                f"Invalid structure '{structure}'. "
                "Supported: array, array_objects, object, full"
            )
        if color_format not in ("hex", "rgb", "rgba", "hsl"):
            raise ValueError(
                f"Invalid color_format '{color_format}'. "
                "Supported: hex, rgb, rgba, hsl"
            )

        # Generate colors
        colors_data: List[Union[str, List[Union[int, float]]]] = []
        for i in range(num_colors):
            position = i / (num_colors - 1)
            color = self._get_color_in_format(colormap, position, color_format)
            colors_data.append(color)

        # Build output structure
        if structure == "array":
            output = colors_data
        elif structure == "array_objects":
            output = []
            for i, color in enumerate(colors_data):
                position = i / (num_colors - 1)
                # Map position to domain value
                domain_value = domain_min + position * (domain_max - domain_min)
                output.append({
                    "position": round(position, 4),
                    "value": round(domain_value, 4),
                    "color": color,
                })
        elif structure == "object":
            output = {}
            for i, color in enumerate(colors_data):
                # Use 0-255 scale for keys (common for raster colormaps)
                key = str(int(round(i / (num_colors - 1) * 255)))
                output[key] = color
        elif structure == "full":
            output = {
                "name": colormap.name or "unnamed",
                "num_colors": num_colors,
                "domain": [domain_min, domain_max],
                "interpolation_space": colormap.interpolation_space,
                "colors": colors_data,
            }
        else:
            output = colors_data

        indent_val = indent if indent > 0 else None
        return json.dumps(output, indent=indent_val)

    def _get_color_in_format(
        self, colormap: Colormap, position: float, color_format: str
    ) -> Union[str, List[Union[int, float]]]:
        """Get color in the specified format."""
        if color_format == "hex":
            return colormap.get_color(position, output_format="hex")
        elif color_format == "rgb":
            r, g, b = colormap.get_color(position, output_format="rgb_tuple")
            return [r, g, b]
        elif color_format == "rgba":
            r, g, b, a = colormap.get_color(position, output_format="rgba_tuple")
            return [r, g, b, a]
        elif color_format == "hsl":
            h, s, l = colormap.get_color(position, output_format="hsl_tuple")
            return [round(h, 1), round(s, 1), round(l, 1)]
        else:
            return colormap.get_color(position, output_format="hex")

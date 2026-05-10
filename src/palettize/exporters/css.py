"""Exporter for CSS custom properties (CSS variables)."""

from typing import Any, Dict, Optional

from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter


class CSSExporter(BaseExporter):
    """
    Exporter for CSS custom properties format.
    """

    @property
    def identifier(self) -> str:
        return "css"

    @property
    def name(self) -> str:
        return "CSS Custom Properties"

    @property
    def default_file_extension(self) -> str:
        return "css"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to CSS custom properties format.

        Accepted options:
            num_colors (int): Number of color steps to generate. Default 256.
            prefix (str): Variable name prefix. Default "color".
                Variables will be named --{prefix}-0, --{prefix}-1, etc.
            selector (str): CSS selector to wrap variables. Default ":root".
                Use empty string for no selector wrapper.
            include_hsl (bool): Include HSL versions of colors. Default False.
                Adds --{prefix}-{n}-hsl variables.
            include_rgb (bool): Include RGB component variables. Default False.
                Adds --{prefix}-{n}-r, --{prefix}-{n}-g, --{prefix}-{n}-b.
            color_format (str): Primary color format. Default "hex".
                Options: "hex", "hsl", "rgb".
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        prefix = options.get("prefix", "color")
        selector = options.get("selector", ":root")
        include_hsl = options.get("include_hsl", False)
        include_rgb = options.get("include_rgb", False)
        color_format = options.get("color_format", "hex")

        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        if color_format not in ("hex", "hsl", "rgb"):
            raise ValueError(
                f"Invalid color_format '{color_format}'. Supported: hex, hsl, rgb"
            )

        lines = []
        for i in range(num_colors):
            position = i / (num_colors - 1)

            # Get hex color
            hex_color = colormap.get_color(position, output_format="hex")

            # Get HSL for optional HSL output
            h, s, l = colormap.get_color(position, output_format="hsl_tuple")

            # Get RGB for optional RGB component output
            r, g, b = colormap.get_color(position, output_format="rgb_tuple")

            # Primary color variable
            var_name = f"--{prefix}-{i}"
            if color_format == "hex":
                lines.append(f"  {var_name}: {hex_color};")
            elif color_format == "hsl":
                lines.append(f"  {var_name}: hsl({h:.0f}, {s:.0f}%, {l:.0f}%);")
            elif color_format == "rgb":
                lines.append(f"  {var_name}: rgb({r}, {g}, {b});")

            # Optional HSL version
            if include_hsl and color_format != "hsl":
                lines.append(
                    f"  {var_name}-hsl: hsl({h:.0f}, {s:.0f}%, {l:.0f}%);"
                )

            # Optional RGB components
            if include_rgb:
                lines.append(f"  {var_name}-r: {r};")
                lines.append(f"  {var_name}-g: {g};")
                lines.append(f"  {var_name}-b: {b};")

        # Wrap in selector if provided
        if selector:
            content = f"{selector} {{\n" + "\n".join(lines) + "\n}"
        else:
            content = "\n".join(lines)

        return content

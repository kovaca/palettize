"""Exporter for SVG gradient elements."""

from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter


class SVGExporter(BaseExporter):
    """
    Exporter for SVG gradient elements.
    """

    @property
    def identifier(self) -> str:
        return "svg"

    @property
    def name(self) -> str:
        return "SVG Gradient"

    @property
    def default_file_extension(self) -> str:
        return "svg"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to an SVG gradient element.

        Accepted options:
            num_colors (int): Number of color stops to generate. Default 256.
            gradient_type (str): Type of gradient. Options:
                - "linear" (default): linearGradient element
                - "radial": radialGradient element
            gradient_id (str): ID for the gradient element. Default "palette".
            include_defs (bool): Wrap in <defs> element. Default True.
            full_svg (bool): Output complete SVG with preview rectangle. Default False.
            x1, y1, x2, y2 (str): Gradient coordinates for linear gradients.
                Defaults: x1="0%", y1="0%", x2="100%", y2="0%" (horizontal)
            cx, cy, r (str): Gradient coordinates for radial gradients.
                Defaults: cx="50%", cy="50%", r="50%"
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        gradient_type = options.get("gradient_type", "linear")
        gradient_id = options.get("gradient_id", "palette")
        include_defs = options.get("include_defs", True)
        full_svg = options.get("full_svg", False)

        # Linear gradient coordinates
        x1 = options.get("x1", "0%")
        y1 = options.get("y1", "0%")
        x2 = options.get("x2", "100%")
        y2 = options.get("y2", "0%")

        # Radial gradient coordinates
        cx = options.get("cx", "50%")
        cy = options.get("cy", "50%")
        r = options.get("r", "50%")

        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        if gradient_type not in ("linear", "radial"):
            raise ValueError(
                f"Invalid gradient_type '{gradient_type}'. Supported: linear, radial"
            )

        # Generate color stops
        stops = []
        for i in range(num_colors):
            position = i / (num_colors - 1)
            hex_color = colormap.get_color(position, output_format="hex")
            offset_pct = f"{position * 100:.2f}%"
            stops.append(f'    <stop offset="{offset_pct}" stop-color="{hex_color}"/>')

        stops_str = "\n".join(stops)

        # Build gradient element
        safe_id = escape(gradient_id)
        if gradient_type == "linear":
            gradient = (
                f'  <linearGradient id="{safe_id}" '
                f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">\n'
                f'{stops_str}\n'
                f'  </linearGradient>'
            )
        else:  # radial
            gradient = (
                f'  <radialGradient id="{safe_id}" '
                f'cx="{cx}" cy="{cy}" r="{r}">\n'
                f'{stops_str}\n'
                f'  </radialGradient>'
            )

        # Wrap in defs if requested
        if include_defs:
            content = f"<defs>\n{gradient}\n</defs>"
        else:
            content = gradient

        # Full SVG with preview
        if full_svg:
            palette_name = colormap.name or "palette"
            if gradient_type == "linear":
                preview_rect = f'<rect x="0" y="0" width="400" height="50" fill="url(#{safe_id})"/>'
            else:
                preview_rect = f'<circle cx="200" cy="100" r="100" fill="url(#{safe_id})"/>'

            content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
  <title>{escape(palette_name)}</title>
{content}
  {preview_rect}
</svg>'''

        return content

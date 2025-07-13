"""Exporter for Google Earth Engine (GEE)."""

from typing import Any, Dict, Optional

from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter


class GEEExporter(BaseExporter):
    """
    Exporter for Google Earth Engine JavaScript code snippets.
    """

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
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to a GEE JavaScript snippet.

        Accepted options:
            type (str): 'default' or 'sld'. Default is 'default'.
            num_colors (int): Number of color steps to generate. Default 256.
        """
        options = options or {}
        export_type = options.get("type", "default")
        num_colors = options.get("num_colors", 256)
        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")

        if export_type == "default":
            return self._export_default(colormap, domain_min, domain_max, num_colors)
        elif export_type == "sld":
            return self._export_sld(colormap, domain_min, domain_max, num_colors)
        else:
            raise ValueError(f"Unsupported GEE export type: {export_type}")

    def _export_default(self, colormap: Colormap, domain_min: float, domain_max: float, num_colors: int) -> str:
        """Exports a GEE visualization palette."""
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        
        # GEE palette colors are hex strings without the '#'
        colors = []
        for i in range(num_colors):
            position = i / (num_colors - 1)
            color_hex = colormap.get_color(position, output_format="hex")
            if isinstance(color_hex, str):
                colors.append(color_hex[1:])

        palette_str = ", ".join([f"'{c}'" for c in colors])
        return f"var palettize_viz = {{min: {domain_min}, max: {domain_max}, palette: [{palette_str}]}};"

    def _export_sld(self, colormap: Colormap, domain_min: float, domain_max: float, num_colors: int) -> str:
        """Exports a GEE SLD-style palette."""
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2 for SLD ramp.")

        entries = []
        for i in range(num_colors):
            position = i / (num_colors - 1)
            
            value = domain_min + position * (domain_max - domain_min)
            # a bit of rounding to avoid long float strings
            if abs(value - round(value)) < 1e-9:
                value = int(round(value))
            else:
                value = round(value, 4)

            color_hex_any = colormap.get_color(position, output_format="hex")
            if isinstance(color_hex_any, str):
                color_hex = color_hex_any
            else:
                color_hex = "#000000" # Fallback, should not be reached with hex format
            # Each entry is a JS string literal concatenated with '+'
            entry = f'      \'<ColorMapEntry color="{color_hex}" quantity="{value}" label="{value}" />\' +'
            entries.append(entry)

        # remove the last ' +' from the last entry
        if entries:
            entries[-1] = entries[-1].rstrip(" +")

        entries_str = "\n".join(entries)

        # Using a multiline f-string for better readability and correctness
        final_string = f"""var palettize_sld =
  '<RasterSymbolizer>' +
    '<ColorMap type="ramp" extended="false" >' +
{entries_str}
    '</ColorMap>' +
  '</RasterSymbolizer>';"""
        
        return final_string 
"""Exporter for GIMP Palette (.gpl) format."""

from typing import Any, Dict, Optional

from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter


class GIMPExporter(BaseExporter):
    """
    Exporter for GIMP Palette (.gpl) format.
    """

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
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to GIMP Palette (.gpl) format.

        The GIMP Palette format is a simple text format:
        ```
        GIMP Palette
        Name: Palette Name
        Columns: 16
        #
        R G B    color-name
        ```

        Accepted options:
            num_colors (int): Number of color steps to generate. Default 256.
            palette_name (str): Name of the palette. Default uses colormap name or "Untitled".
            columns (int): Number of columns for display in GIMP. Default 16.
            color_names (bool): Include color names. Default True.
                Names are formatted as "color-{index}".
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        palette_name = options.get("palette_name", colormap.name or "Untitled")
        columns = options.get("columns", 16)
        color_names = options.get("color_names", True)

        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")

        lines = [
            "GIMP Palette",
            f"Name: {palette_name}",
            f"Columns: {columns}",
            "#",
        ]

        for i in range(num_colors):
            position = i / (num_colors - 1)
            r, g, b = colormap.get_color(position, output_format="rgb_tuple")

            # GIMP format: "R G B\tcolor-name" with spaces for alignment
            if color_names:
                lines.append(f"{r:3d} {g:3d} {b:3d}\tcolor-{i}")
            else:
                lines.append(f"{r:3d} {g:3d} {b:3d}")

        return "\n".join(lines)

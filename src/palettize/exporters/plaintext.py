"""Exporter for plain text files - newline delimited representations of color."""

from typing import Any, Dict, Optional

from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter


class HexExporter(BaseExporter):
    """
    Exporter for plain text hashed hex values for rgb.
    """

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
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to a plain text hash-prefixed hexadecimal format.

        Accepted options:
            num_colors (int): Number of color steps to generate. Default 256.
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        
        # palette colors are hex strings with the '#' prefix
        colors = []
        for i in range(num_colors):
            position = i / (num_colors - 1)
            color_hex = colormap.get_color(position, output_format="hex")
            colors.append(color_hex)

        palette_str = "\n".join(colors)
        return palette_str


class RGBAExporter(BaseExporter):
    """
    Exporter for plain text RGBA values suitable for CSS, for instance.
    """

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
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to a plain text rgba(intR, intG, intB, intA) format.

        Accepted options:
            num_colors (int): Number of color steps to generate. Default 256.
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        
        colors = []
        for i in range(num_colors):
            position = i / (num_colors - 1)
            r, g, b, a = colormap.get_color(position, output_format="rgba_tuple")
            color_string = f"rgba({r}, {g}, {b}, {a})"
            colors.append(color_string)

        palette_str = "\n".join(colors)
        return palette_str


"""Exporter for plain text files - newline delimited representations of color."""

import json
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
            output_format (str): Output format. Options:
                - "lines" (default): Newline-separated hex values
                - "json": JSON array of hex strings ["#ff0000", ...]
                - "json_nohash": JSON array without hash ["ff0000", ...]
                - "csv": Comma-separated hex values
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        output_format = options.get("output_format", "lines")

        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        if output_format not in ("lines", "json", "json_nohash", "csv"):
            raise ValueError(
                f"Invalid output_format '{output_format}'. "
                "Supported: lines, json, json_nohash, csv"
            )

        # Generate palette colors as hex strings with the '#' prefix
        colors = []
        for i in range(num_colors):
            position = i / (num_colors - 1)
            color_hex = colormap.get_color(position, output_format="hex")
            colors.append(color_hex)

        if output_format == "lines":
            return "\n".join(colors)
        elif output_format == "json":
            return json.dumps(colors, indent=2)
        elif output_format == "json_nohash":
            # Remove the '#' prefix from each color
            colors_nohash = [c.lstrip("#") for c in colors]
            return json.dumps(colors_nohash, indent=2)
        elif output_format == "csv":
            return ", ".join(colors)
        else:
            return "\n".join(colors)


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
        Exports the colormap to a plain text rgba format.

        Accepted options:
            num_colors (int): Number of color steps to generate. Default 256.
            output_format (str): Output format. Options:
                - "css" (default): CSS rgba() format - rgba(R, G, B, A)
                - "tuple": Python tuple format - (R, G, B, A)
                - "json": JSON array of [R, G, B, A] arrays
            alpha_format (str): Alpha value format. Options:
                - "int" (default): Alpha as 0-255 integer
                - "float": Alpha as 0.0-1.0 float
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        output_format = options.get("output_format", "css")
        alpha_format = options.get("alpha_format", "int")

        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        if output_format not in ("css", "tuple", "json"):
            raise ValueError(
                f"Invalid output_format '{output_format}'. Supported: css, tuple, json"
            )
        if alpha_format not in ("int", "float"):
            raise ValueError(
                f"Invalid alpha_format '{alpha_format}'. Supported: int, float"
            )

        colors = []
        color_arrays = []  # For JSON format
        for i in range(num_colors):
            position = i / (num_colors - 1)
            r, g, b, a = colormap.get_color(position, output_format="rgba_tuple")

            if alpha_format == "float":
                a_val = round(a / 255.0, 3)
            else:
                a_val = a

            if output_format == "css":
                if alpha_format == "float":
                    color_string = f"rgba({r}, {g}, {b}, {a_val})"
                else:
                    color_string = f"rgba({r}, {g}, {b}, {a_val})"
                colors.append(color_string)
            elif output_format == "tuple":
                color_string = f"({r}, {g}, {b}, {a_val})"
                colors.append(color_string)
            elif output_format == "json":
                color_arrays.append([r, g, b, a_val])

        if output_format == "json":
            return json.dumps(color_arrays, indent=2)
        else:
            return "\n".join(colors)


class HSLExporter(BaseExporter):
    """
    Exporter for plain text HSL values.
    """

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
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to a plain text HSL format.

        Accepted options:
            num_colors (int): Number of color steps to generate. Default 256.
            output_format (str): Output format. Options:
                - "css" (default): CSS hsl() format - hsl(H, S%, L%)
                - "tuple": Python tuple format - (H, S, L)
                - "json": JSON array of [H, S, L] arrays
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        output_format = options.get("output_format", "css")

        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if num_colors < 2:
            raise ValueError("Number of colors must be at least 2.")
        if output_format not in ("css", "tuple", "json"):
            raise ValueError(
                f"Invalid output_format '{output_format}'. Supported: css, tuple, json"
            )

        colors = []
        color_arrays = []  # For JSON format
        for i in range(num_colors):
            position = i / (num_colors - 1)
            h, s, l = colormap.get_color(position, output_format="hsl_tuple")

            if output_format == "css":
                color_string = f"hsl({h:.0f}, {s:.0f}%, {l:.0f}%)"
                colors.append(color_string)
            elif output_format == "tuple":
                color_string = f"({h:.1f}, {s:.1f}, {l:.1f})"
                colors.append(color_string)
            elif output_format == "json":
                color_arrays.append([round(h, 1), round(s, 1), round(l, 1)])

        if output_format == "json":
            return json.dumps(color_arrays, indent=2)
        else:
            return "\n".join(colors)


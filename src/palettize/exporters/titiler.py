"""TiTiler Colormap Exporter for Palettize."""

import json
import urllib.parse
from palettize.core import Colormap, ScalingFunction, ColorStop
from typing import Dict, Optional, Any
from ._base import BaseExporter


class TitilerExporter(BaseExporter):
    """
    Exporter for TiTiler compatible colormap URL parameter.
    """

    @property
    def identifier(self) -> str:
        return "titiler"

    @property
    def name(self) -> str:
        return "TiTiler Colormap URL Parameter"

    @property
    def default_file_extension(self) -> str:
        # The output is a URL parameter string, not typically a file.
        # Using 'txt' as a reasonable default if saved.
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
        Exports the colormap to a TiTiler compatible URL-encoded colormap parameter.

        The colormap is sampled at a number of discrete steps and represented as a
        mapping of integer values from 0-255 to hex colors.

        The 'scaler', 'domain_min', and 'domain_max' parameters are not directly
        used in the output format itself, which assumes a 0-255 data range for
        color mapping. These are part of the standard exporter interface.

        Accepted options:
            num_colors (int): The number of discrete color steps to sample from the
                              colormap. Defaults to 11 if not provided, matching
                              the CLI's `export` command default.
        """
        options = options or {}
        # Get num_colors from options. Default to 11 as per `export` CLI command.
        num_colors = options.get("num_colors")
        if num_colors is None:
            num_colors = 11

        if not isinstance(num_colors, int) or num_colors < 2:
            raise ValueError("Option 'num_colors' must be an integer >= 2.")

        color_map_dict: Dict[str, str] = {}

        # Loop to sample the colormap at `num_colors` points
        for i in range(num_colors):
            # Normalized position for this step
            t = i / (num_colors - 1) if num_colors > 1 else 0.0

            # Scale position to 0-255 and convert to integer string for the key
            key = str(int(round(t * 255)))

            # Get the interpolated color at this normalized position.
            hex_color = colormap.get_color(t, output_format="hex")

            # TiTiler's colormap parameter often uses #RRGGBB.
            # We will strip the alpha channel if it exists for simplicity,
            # matching the user-provided example.
            if len(hex_color) == 9:  # #RRGGBBAA
                hex_color = hex_color[:7]

            color_map_dict[key] = hex_color

        # The required structure is a dictionary with a "colormap" key,
        # where the value is the JSON-dumped string of our color map.
        payload = {"colormap": json.dumps(color_map_dict, indent=None, separators=(",", ":"))}

        # Finally, URL-encode the entire payload.
        return urllib.parse.urlencode(payload, quote_via=urllib.parse.quote)

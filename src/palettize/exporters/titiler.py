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
        payload = {"colormap": json.dumps(color_map_dict)}

        # Finally, URL-encode the entire payload.
        return urllib.parse.urlencode(payload)


# Example Usage:
if __name__ == "__main__":
    from palettize.scaling import get_linear_scaler

    # --- Test Case 1: Default behavior (should be 11 steps) ---
    stops1 = [
        ColorStop("blue", 0.0),
        ColorStop("yellow", 0.5),
        ColorStop("red", 1.0),
    ]
    cmap1 = Colormap(stops1, name="BlueYellowRed")
    scaler = get_linear_scaler(0, 100)
    exporter = TitilerExporter()

    output1 = exporter.export(cmap1, scaler, 0, 100)
    print("--- Default (11 steps) Test ---")
    print("Output:", output1)
    # Check if there are 11 entries in the decoded JSON
    decoded_payload1 = urllib.parse.parse_qs(output1)
    colormap_json1 = json.loads(decoded_payload1["colormap"][0])
    print(f"Number of steps: {len(colormap_json1)}")
    assert len(colormap_json1) == 11
    # Check first, middle, and last colors
    assert colormap_json1["0"].lower() == "#0000ff"
    assert colormap_json1["128"].lower() == "#ffff00"
    assert colormap_json1["255"].lower() == "#ff0000"
    print("Test PASSED")
    print("\n")

    # --- Test Case 2: With user-provided num_colors ---
    options2 = {"num_colors": 5}
    output2 = exporter.export(cmap1, scaler, 0, 100, options=options2)
    print("--- Custom num_colors=5 Test ---")
    print("Output:", output2)
    decoded_payload2 = urllib.parse.parse_qs(output2)
    colormap_json2 = json.loads(decoded_payload2["colormap"][0])
    print(f"Number of steps: {len(colormap_json2)}")
    assert len(colormap_json2) == 5
    # Check keys: 0, 64, 128, 191, 255
    # 1/(5-1) * 255 = 63.75 -> 64
    # 2/(5-1) * 255 = 127.5 -> 128
    # 3/(5-1) * 255 = 191.25 -> 191
    assert "64" in colormap_json2
    assert "191" in colormap_json2
    print("Test PASSED")
    print("\n")

    # --- Test Case 3: Single color colormap ---
    single_stop_cmap = Colormap([ColorStop("green", 0.5)])
    options3 = {"num_colors": 3}
    output3 = exporter.export(single_stop_cmap, scaler, 0, 100, options=options3)
    print("--- Single Color Colormap Test ---")
    print("Output:", output3)
    decoded_payload3 = urllib.parse.parse_qs(output3)
    colormap_json3 = json.loads(decoded_payload3["colormap"][0])
    print(f"Number of steps: {len(colormap_json3)}")
    assert len(colormap_json3) == 3
    # All colors should be green
    assert colormap_json3["0"].lower() == "#008000"
    assert colormap_json3["128"].lower() == "#008000"
    assert colormap_json3["255"].lower() == "#008000"
    print("Test PASSED")
    print("\n")

    # --- Test Case 4: Edge case num_colors < 2 ---
    options4 = {"num_colors": 1}
    try:
        exporter.export(cmap1, scaler, 0, 100, options=options4)
    except ValueError as e:
        print("--- num_colors < 2 Test ---")
        print(f"Caught expected error: {e}")
        assert "must be an integer >= 2" in str(e)
        print("Test PASSED")

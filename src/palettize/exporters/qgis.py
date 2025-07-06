"""QGIS Color Ramp Exporter for Palettize."""

import xml.etree.ElementTree as ET
from palettize.core import Colormap, ScalingFunction
from typing import Optional, List, Dict, Any
from ._base import BaseExporter


class QgisExporter(BaseExporter):
    """
    Exporter for QGIS Color Ramp XML files.
    """

    @property
    def identifier(self) -> str:
        return "qgis"

    @property
    def name(self) -> str:
        return "QGIS Color Ramp XML"

    @property
    def default_file_extension(self) -> str:
        return "xml"  # QGIS color ramp files often use .xml or .qml (if part of full style)

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to a QGIS color ramp XML format.

        Accepted options:
            num_colors (int): Number of color steps for gradient ramps. Default 256.
            ramp_type (str): "gradient", "exact", "approximate". Default "gradient".
            name (str): Optional name for the ramp.
            tags (List[str]): Optional list of tags.
            discrete (bool): For "exact"/"approximate", if stops are discrete. Default False.
            color_space (str): QGIS specific color space hint.
            opacity (float): Overall opacity (0.0-1.0). Default 1.0.
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        ramp_type = options.get("ramp_type", "gradient")
        exporter_name = options.get(
            "name"
        )  # `name` is a property of BaseExporter, use a different var name
        tags = options.get("tags")
        discrete = options.get("discrete", False)
        color_space = options.get("color_space")
        opacity = options.get("opacity", 1.0)

        # Basic validation for option types
        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an integer.")
        if not isinstance(ramp_type, str):
            raise ValueError("Option 'ramp_type' must be a string.")
        if exporter_name is not None and not isinstance(exporter_name, str):
            raise ValueError("Option 'name' must be a string.")
        if tags is not None and not (
            isinstance(tags, list) and all(isinstance(t, str) for t in tags)
        ):
            raise ValueError("Option 'tags' must be a list of strings.")
        if not isinstance(discrete, bool):
            raise ValueError("Option 'discrete' must be a boolean.")
        if color_space is not None and not isinstance(color_space, str):
            raise ValueError("Option 'color_space' must be a string.")
        if not isinstance(opacity, (float, int)) or not (0.0 <= opacity <= 1.0):
            raise ValueError("Option 'opacity' must be a float between 0.0 and 1.0.")

        return _export_qgis_color_ramp_impl(
            colormap=colormap,
            scaler=scaler,
            domain_min=domain_min,
            domain_max=domain_max,
            num_colors=num_colors,
            ramp_type=ramp_type,
            name=exporter_name,  # Pass the renamed variable
            tags=tags,
            discrete=discrete,
            color_space=color_space,
            opacity=opacity,
        )


def _export_qgis_color_ramp_impl(  # Renamed original function
    colormap: Colormap,
    scaler: ScalingFunction,
    domain_min: float,
    domain_max: float,
    num_colors: int = 256,
    ramp_type: str = "gradient",  # "gradient", "exact", "approximate"
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    discrete: bool = False,  # For "exact" or "approximate", controls if stops are discrete or interpolated
    color_space: Optional[
        str
    ] = None,  # For QGIS specific color space hints, if applicable
    opacity: float = 1.0,  # Overall opacity for the ramp
) -> str:
    """
    Internal implementation for exporting the colormap to a QGIS color ramp XML format.
    """
    if domain_min >= domain_max:
        raise ValueError("domain_min must be less than domain_max.")
    if ramp_type == "gradient" and num_colors < 2:
        raise ValueError("num_colors must be at least 2 for gradient ramps.")

    # qgis_opacity = int(opacity * 255)

    # Root element
    color_ramp_attribs = {
        "name": name or colormap.name or "Palettize Ramp",
        "type": ramp_type,
    }
    if tags:
        color_ramp_attribs["tags"] = ";".join(tags)

    # QGIS specific attributes like colorSpace
    # Note: QGIS 3.x color ramp XML structure is somewhat simple.
    # For advanced color spaces, QGIS might rely on its internal handling or specific properties.
    # This 'colorSpace' attribute is a guess and might need verification for modern QGIS versions.
    if color_space:
        color_ramp_attribs["colorSpace"] = color_space  # e.g., "RGB", "HSV"

    root = ET.Element(
        "colorramps"
    )  # QGIS style files often have <colorramps> as a wrapper
    color_ramp_element = ET.SubElement(root, "colorramp", color_ramp_attribs)

    if ramp_type == "gradient":
        # Generate stops for a gradient ramp
        # QGIS gradient ramps are typically defined by a list of <item> elements
        # with position (0-1), color, and alpha.
        for i in range(num_colors):
            # t_sample is the position in the [0,1] range for sampling the domain
            t_sample = i / (num_colors - 1) if num_colors > 1 else 0.0
            data_val = domain_min + t_sample * (domain_max - domain_min)

            # apply_scaler should return (R,G,B,A) tuple
            color_components = colormap.apply_scaler(
                data_val, scaler, output_format="rgba_tuple"
            )
            if not (isinstance(color_components, tuple) and len(color_components) == 4):
                # This should ideally not happen if Colormap.apply_scaler is robust
                raise ValueError(
                    f"Color for data_val {data_val} not in expected RGBA tuple format. Got: {color_components}"
                )
            r, g, b, a = color_components  # type: ignore

            # QGIS uses 'alpha' for opacity in its item tags, but also sometimes has an overall opacity.
            # We'll set individual item alpha, and the overall opacity is on the ramp level (less common).
            # The apply_scaler gives A from 0-255, QGIS opacity here is 0-255.
            # We also have an overall 'opacity' parameter for the ramp.
            # Let's assume apply_scaler's alpha is the primary one, and then modulate by overall opacity
            final_alpha = int(
                a * opacity
            )  # apply_scaler's alpha is 0-255, opacity is 0-1
            final_alpha = max(0, min(255, final_alpha))  # Ensure it's in 0-255 range

            item_attrs = {
                "alpha": str(final_alpha),  # QGIS wants 0-255 for alpha
                "color": f"#{r:02x}{g:02x}{b:02x}",
                # The 'position' in QGIS gradient ramp items is typically 0 to 1
                # It represents the relative position along the ramp.
                "position": f"{t_sample:.4f}",
            }
            ET.SubElement(color_ramp_element, "item", item_attrs)

    elif ramp_type in ["exact", "approximate"]:
        # For 'exact' or 'approximate', we typically use the defined color stops from the colormap
        # The 'discrete' parameter influences how these are interpreted by QGIS.
        # QGIS <colorramp type="[exact|approximate]"> often takes <item value="..." color="..." label="..." />
        # The 'value' here is the actual data value.

        # Ensure stops are normalized and sorted by their original position
        # This is important if the original colormap might not have stops at 0 and 1
        # or if they are not perfectly ordered by their `pos` attribute.
        # We need to map these `pos` values (0-1 from Colormap) to actual data domain values.

        # If colormap.stops is None or empty, handle appropriately
        if not colormap.stops:
            # Or raise error, or return empty ramp, depending on desired behavior
            warnings.warn(
                "Colormap has no stops; generating an empty 'exact' QGIS ramp."
            )
            # Fall through to return empty ramp XML, or handle as error
        else:
            sorted_stops = sorted(colormap.stops, key=lambda s: s.pos)

            for stop in sorted_stops:
                data_val = domain_min + stop.pos * (domain_max - domain_min)
                # For exact stops, we get the color directly from the stop's parsed color object
                # We need to ensure it's in sRGB and get its components.
                # The Colormap's parse_input_color ensures _parsed_color_obj is a ColorAide Color object.
                srgb_color = stop._parsed_color_obj.convert(
                    "srgb"
                )  # Ensure sRGB for output

                # Get R,G,B as 0-255 integers
                r_float, g_float, b_float = srgb_color.coords(nans=False)[:3]
                r, g, b = [int(round(c * 255)) for c in [r_float, g_float, b_float]]
                # Get alpha as 0-255 integer. If color has no alpha, assume opaque.
                # coloraide.Color.alpha() returns NaN if no alpha, or 0-1.
                alpha_val = srgb_color.alpha()
                a = (
                    int(round(alpha_val * 255))
                    if not srgb_color.is_nan("alpha")
                    else 255
                )

                final_alpha = int(a * opacity)  # Modulate by overall opacity
                final_alpha = max(0, min(255, final_alpha))  # Ensure 0-255 range

                item_attrs = {
                    "value": f"{data_val:.4f}",  # Actual data value
                    "color": f"#{r:02x}{g:02x}{b:02x}",
                    "alpha": str(final_alpha),  # QGIS also uses alpha here
                    "label": f"{data_val:.2f}",  # Optional label, can be the value itself
                }
                # For discrete ramps, QGIS might also use a slightly different interpretation or tag.
                # The 'discrete' boolean parameter passed to this function can guide this.
                # However, the primary control is usually ramp_type="exact" vs "gradient".
                # If `discrete` is True, we might add a specific property if QGIS supports it,
                # but often it's implied by 'exact'.
                # For now, the `discrete` flag is noted but not directly changing XML structure beyond type.

                ET.SubElement(color_ramp_element, "item", item_attrs)

    else:
        raise ValueError(
            f"Unsupported QGIS ramp_type: {ramp_type}. Supported types are 'gradient', 'exact', 'approximate'."
        )

    # Add overall opacity to the colorramp element itself if QGIS supports it.
    # Some QGIS ramp styles might use a global <prop k="opacity" v="..."/>
    # For simplicity, we'll rely on item alpha for now, plus the function's opacity parameter
    # which modulates item alpha. If a global opacity is needed, it would be:
    # ET.SubElement(color_ramp_element, "prop", {"k": "opacity", "v": str(opacity)})
    # However, the primary mechanism in QGIS seems to be the alpha on each <item>.

    # Convert the XML tree to a string
    # ET.indent is available in Python 3.9+ for pretty printing
    try:
        ET.indent(root, space="  ")
    except AttributeError:
        # Fallback for older Python versions if ET.indent is not available
        pass

    xml_string = ET.tostring(root, encoding="unicode", xml_declaration=True)

    # QGIS style files (.qml) often embed this within a <symbols> or <rasterrenderer> context.
    # This function returns the <colorramps> block, which can be part of a larger style.
    # For a standalone *.qcr (QGIS Color Ramp) file, it might just be the <colorramp> element itself
    # or <colorramps> with a single <colorramp>. We'll return <colorramps> for broader use.
    return xml_string


# Example usage (for testing, not part of the library's public API for direct call)
if __name__ == "__main__":
    from palettize.core import Colormap, ColorStop, parse_input_color
    from palettize.scaling import get_linear_scaler
    import warnings  # Added for the warning in exact ramp type

    # Create a simple colormap
    stops = [
        ColorStop(0.0, "red"),
        ColorStop(
            0.5, parse_input_color("lime")
        ),  # Using direct coloraide object via parse
        ColorStop(1.0, (0, 0, 255, 128)),  # Blue with alpha
    ]
    cmap = Colormap(stops, name="TestQGIS", interpolation_space="oklch")

    lin_scaler = get_linear_scaler(0, 100)

    # Test gradient ramp
    qgis_xml_gradient = _export_qgis_color_ramp_impl(
        cmap,
        lin_scaler,
        domain_min=0,
        domain_max=100,
        num_colors=10,
        name="My Gradient Test",
        tags=["test", "gradient"],
        opacity=0.8,
    )
    print("--- QGIS Gradient Ramp ---")
    print(qgis_xml_gradient)
    print("\n")

    # Test exact ramp
    qgis_xml_exact = _export_qgis_color_ramp_impl(
        cmap,
        lin_scaler,  # Scaler is less relevant for "exact" if using original stops' positions
        domain_min=0,  # Domain for mapping stop.pos to values
        domain_max=100,
        ramp_type="exact",
        name="My Exact Test",
        tags=["test", "exact"],
        discrete=True,  # Hint for exact interpretation
        opacity=1.0,
    )
    print("--- QGIS Exact Ramp ---")
    print(qgis_xml_exact)

    # Test with empty stops for exact ramp
    empty_cmap = Colormap([], name="EmptyQGIS")
    qgis_xml_empty_exact = _export_qgis_color_ramp_impl(
        empty_cmap,
        lin_scaler,
        domain_min=0,
        domain_max=100,
        ramp_type="exact",
        name="Empty Exact Test",
    )
    print("\n--- QGIS Empty Exact Ramp ---")
    print(qgis_xml_empty_exact)

    # Test with a more complex colormap (e.g., from preset)
    try:
        from palettize.presets import load_preset_data

        # Assuming a short viridis preset exists for testing purposes
        # If PRESET_PALETTES is directly accessible and populated:
        # from palettize.presets import PRESET_PALETTES
        # viridis_data = PRESET_PALETTES["viridis_short"]
        # For now, stick to load_preset_data if it's the intended API for preset access
        try:
            viridis_data = load_preset_data("viridis_short")
        except KeyError:
            print("\nSkipping Viridis preset test, 'viridis_short' not found.")
            viridis_data = None  # Ensure viridis_data is defined

        if viridis_data:
            viridis_cmap = Colormap.from_list(
                viridis_data, name="Viridis Short QGIS", interpolation_space="srgb"
            )

            qgis_xml_viridis_gradient = _export_qgis_color_ramp_impl(
                viridis_cmap,
                lin_scaler,
                domain_min=-5,
                domain_max=5,
                num_colors=64,
                name="Viridis Example",
                tags=["example", "viridis"],
                opacity=0.9,
            )
            print("\n--- QGIS Viridis Gradient Ramp ---")
            print(qgis_xml_viridis_gradient)

            qgis_xml_viridis_exact = _export_qgis_color_ramp_impl(
                viridis_cmap,
                lin_scaler,
                domain_min=-5,
                domain_max=5,
                ramp_type="exact",
                name="Viridis Exact Example",
                opacity=1.0,
            )
            print("\n--- QGIS Viridis Exact Ramp ---")
            print(qgis_xml_viridis_exact)

    except ImportError:
        print("\nSkipping preset example, presets module not found in this context.")
    # except KeyError: # Already handled for load_preset_data specific key error
    #     print("\nSkipping preset example, preset not found.")

# src/palettize/exporters/sld.py

"""OGC SLD (Styled Layer Descriptor) Exporter for Palettize."""

import xml.etree.ElementTree as ET
from palettize.core import Colormap, ScalingFunction, ColorStop
from typing import Optional, Dict, Any
from ._base import BaseExporter


def _create_sld_element(
    tag: str,
    ns_map: dict,
    parent: Optional[ET.Element] = None,
    attrib: Optional[dict] = None,
    text: Optional[str] = None,
) -> ET.Element:
    """Helper to create namespaced SLD elements."""
    # For SLD 1.0, the namespace is typically 'http://www.opengis.net/sld'
    # However, some elements might be from SE (Symbology Encoding) 'http://www.opengis.net/se'
    # For simplicity, we'll assume default or handle prefixes if absolutely needed.
    # Most common SLD <ColorMap> elements don't strictly require explicit ns prefixing in simple cases,
    # but it's good practice for the root.

    # Determine the namespace for the tag, default to SLD if not specified by prefix
    ns_prefix = ""
    actual_tag = tag
    if ":" in tag:
        ns_prefix, actual_tag = tag.split(":", 1)

    namespace = ns_map.get(
        ns_prefix, ns_map.get("sld")
    )  # Default to sld namespace if prefix not in map

    if namespace:
        qualified_tag = f"{{{namespace}}}{actual_tag}"
    else:
        qualified_tag = (
            actual_tag  # No namespace if not found (e.g. for non-namespaced wrapper)
        )

    element = (
        ET.Element(qualified_tag, attrib=attrib or {})
        if parent is None
        else ET.SubElement(parent, qualified_tag, attrib=attrib or {})
    )
    if text:
        element.text = text
    return element


class SldExporter(BaseExporter):
    """
    Exporter for OGC Styled Layer Descriptor (SLD) XML.
    """

    @property
    def identifier(self) -> str:
        return "sld"

    @property
    def name(self) -> str:
        return "OGC SLD XML"

    @property
    def default_file_extension(self) -> str:
        return "sld"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the colormap to OGC SLD XML format.

        Accepted options:
            num_colors (int): Number of color steps for "ramp" type. Default 256.
            sld_version (str): SLD version. Default "1.0.0".
            output_type (str): ColorMap type: "ramp", "intervals", "values". Default "ramp".
            opacity (float): Global opacity (0.0-1.0). Overrides stop alpha.
            layer_name (str): UserLayer name. Default "palettize_layer".
            style_name (str): UserStyle name. Default "palettize_style".
            geometry_type (str): Symbolizer geometry: "raster", "polygon", etc. Default "raster".
            band (int): Band number for RasterSymbolizer.
        """
        options = options or {}
        num_colors = options.get("num_colors", 256)
        sld_version = options.get("sld_version", "1.0.0")
        output_type = options.get("output_type", "ramp")
        opacity = options.get("opacity")  # Allow None
        layer_name = options.get("layer_name", "palettize_layer")
        style_name = options.get("style_name", "palettize_style")
        geometry_type = options.get("geometry_type", "raster")
        band = options.get("band")  # Allow None

        # Basic type validation for options
        if not isinstance(num_colors, int):
            raise ValueError("Option 'num_colors' must be an int.")
        if not isinstance(sld_version, str):
            raise ValueError("Option 'sld_version' must be a string.")
        if not isinstance(output_type, str):
            raise ValueError("Option 'output_type' must be a string.")
        if opacity is not None and not (
            isinstance(opacity, (float, int)) and 0.0 <= opacity <= 1.0
        ):
            raise ValueError(
                "Option 'opacity' must be a float between 0.0 and 1.0 or None."
            )
        if not isinstance(layer_name, str):
            raise ValueError("Option 'layer_name' must be a string.")
        if not isinstance(style_name, str):
            raise ValueError("Option 'style_name' must be a string.")
        if not isinstance(geometry_type, str):
            raise ValueError("Option 'geometry_type' must be a string.")
        if band is not None and not isinstance(band, int):
            raise ValueError("Option 'band' must be an integer or None.")

        return _export_sld_impl(
            colormap=colormap,
            scaler=scaler,
            domain_min=domain_min,
            domain_max=domain_max,
            num_colors=num_colors,
            sld_version=sld_version,
            output_type=output_type,
            opacity=opacity,
            layer_name=layer_name,
            style_name=style_name,
            geometry_type=geometry_type,
            band=band,
        )


def _export_sld_impl(
    colormap: Colormap,
    scaler: ScalingFunction,
    domain_min: float,
    domain_max: float,
    num_colors: int = 256,
    sld_version: str = "1.0.0",
    output_type: str = "ramp",
    opacity: Optional[float] = None,
    layer_name: Optional[str] = "palettize_layer",
    style_name: Optional[str] = "palettize_style",
    geometry_type: str = "raster",
    band: Optional[int] = None,
) -> str:
    """Internal implementation for exporting SLD XML."""
    if domain_min >= domain_max:
        raise ValueError("domain_min must be less than domain_max.")
    if num_colors < 2 and output_type == "ramp":
        raise ValueError("num_colors must be at least 2 for ramp type ColorMap.")

    # Define namespaces (these might vary or need to be registered based on server/client)
    # For SLD 1.0.0, 'sld' is common. For SE 1.1.0, 'se' is used.
    # We'll use a general approach and allow helper to qualify.
    ns = {
        "sld": "http://www.opengis.net/sld",
        "ogc": "http://www.opengis.net/ogc",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "se": "http://www.opengis.net/se",  # Symbology Encoding, often used with SLD 1.1+
        # Add other namespaces like xlink if needed
    }
    # For ET.register_namespace to work for output serialization with prefixes
    for prefix, uri in ns.items():
        ET.register_namespace(prefix, uri)

    # Root SLD element
    sld_root_attrs = {
        "version": sld_version,
        f"{{{ns['xsi']}}}schemaLocation": f"{ns['sld']} http://schemas.opengis.net/sld/{sld_version}/StyledLayerDescriptor.xsd",
    }
    sld_root = ET.Element(
        f"{{{ns['sld']}}}StyledLayerDescriptor", attrib=sld_root_attrs
    )

    # UserLayer
    user_layer = _create_sld_element("sld:UserLayer", ns, sld_root)
    _create_sld_element(
        "sld:Name",
        ns,
        user_layer,
        text=layer_name or colormap.name or "Palettize Layer",
    )

    # UserStyle
    user_style = _create_sld_element("sld:UserStyle", ns, user_layer)
    _create_sld_element(
        "sld:Name",
        ns,
        user_style,
        text=style_name or colormap.name or "Palettize Style",
    )
    _create_sld_element("sld:IsDefault", ns, user_style, text="1")

    # FeatureTypeStyle (assuming one)
    feature_type_style = _create_sld_element("sld:FeatureTypeStyle", ns, user_style)
    # Rule (assuming one default rule)
    rule = _create_sld_element("sld:Rule", ns, feature_type_style)
    _create_sld_element("sld:Name", ns, rule, text="Default Rule")

    # Symbolizer (RasterSymbolizer or PolygonSymbolizer etc.)
    symbolizer: ET.Element
    if geometry_type.lower() == "raster":
        symbolizer = _create_sld_element("sld:RasterSymbolizer", ns, rule)
        if band is not None:
            # GeoServer specific: <ChannelSelection><GrayChannel><SourceChannelName>band_num</SourceChannelName>... or just <GrayChannel>
            # Standard SLD <ColorMap> is usually applied to the first band if not specified
            # For more complex band mapping, more specific XML needed.
            # For simple grayscale to color, often band is implied or set in <SourceChannelName>1</SourceChannelName>
            # or <ChannelSelection><GrayChannel><SourceChannelName>{band}</SourceChannelName></GrayChannel></ChannelSelection>
            # Let's create a simple SourceChannelName if band is specified.
            if (
                sld_version == "1.0.0"
            ):  # SLD 1.0.0 uses <SourceChannelName> directly in RasterSymbolizer for opacity or band
                pass  # Band selection might be implicit or need specific vendor options outside simple ColorMap.
            elif sld_version.startswith(
                "1.1"
            ):  # SE 1.1.0 has more explicit ChannelSelection
                chan_sel = _create_sld_element("se:ChannelSelection", ns, symbolizer)
                gray_chan = _create_sld_element("se:GrayChannel", ns, chan_sel)
                _create_sld_element(
                    "se:SourceChannelName", ns, gray_chan, text=str(band)
                )

    elif geometry_type.lower() == "polygon":
        symbolizer = _create_sld_element("sld:PolygonSymbolizer", ns, rule)
    elif geometry_type.lower() == "line":
        symbolizer = _create_sld_element("sld:LineSymbolizer", ns, rule)
    # Add more symbolizer types if needed (PointSymbolizer etc.)
    else:
        symbolizer = _create_sld_element(
            "sld:RasterSymbolizer", ns, rule
        )  # Default to raster

    # ColorMap element
    # SLD 1.0.0 uses <ColorMap>, SE 1.1.0 (often with SLD 1.1.0) uses <se:ColorMap>
    colormap_tag = "sld:ColorMap" if sld_version == "1.0.0" else "se:ColorMap"
    color_map = _create_sld_element(
        colormap_tag, ns, symbolizer, attrib={"type": output_type}
    )

    # Generate ColorMapEntry elements
    if output_type == "ramp":
        for i in range(num_colors):
            t_sample = i / (num_colors - 1) if num_colors > 1 else 0.0
            data_val = domain_min + t_sample * (domain_max - domain_min)
            # Ensure apply_scaler returns a 4-tuple (R, G, B, A)
            color_components = colormap.apply_scaler(
                data_val, scaler, output_format="rgba_tuple"
            )
            if not (isinstance(color_components, tuple) and len(color_components) == 4):
                raise ValueError(
                    f"Color for data_val {data_val} not in expected RGBA tuple. Got: {color_components}"
                )
            r, g, b, a_val = color_components

            current_opacity = (a_val / 255.0) if opacity is None else opacity

            entry_attrs = {
                "color": f"#{r:02x}{g:02x}{b:02x}",
                "quantity": f"{data_val:.6f}",
                "opacity": f"{current_opacity:.2f}",
            }
            if colormap.name and i == 0:  # Label for first/last perhaps
                entry_attrs["label"] = f"{colormap.name} Start ({data_val:.2f})"
            elif colormap.name and i == num_colors - 1:
                entry_attrs["label"] = f"{colormap.name} End ({data_val:.2f})"

            _create_sld_element(
                colormap_tag + "Entry", ns, color_map, attrib=entry_attrs
            )  # e.g. sld:ColorMapEntry

    elif output_type in ["intervals", "values"]:
        # Use original stops for discrete types
        if not colormap.stops:
            # Handle empty colormap stops for discrete types
            # Depending on desired behavior, could return minimal SLD or raise error
            # For now, let it proceed; it will produce a ColorMap with no entries.
            pass

        sorted_stops = sorted(colormap.stops, key=lambda s: s.pos)
        for i, stop in enumerate(sorted_stops):
            data_val = domain_min + stop.pos * (domain_max - domain_min)

            # Get color directly from stop (sRGB for output)
            # Using stop._parsed_color_obj as per convention in other exporters
            if not hasattr(stop, "_parsed_color_obj") or stop._parsed_color_obj is None:
                # This case should ideally be prevented by Colormap structure or validation
                # Fallback or raise error if a stop has no parsed color object.
                # For now, let's use a default color like black if this happens, with a warning.
                import warnings

                warnings.warn(
                    f"ColorStop at pos {stop.pos} has no valid _parsed_color_obj. Using black.",
                    RuntimeWarning,
                )
                srgb_color = ColorStop(0, "black")._parsed_color_obj.convert(
                    "srgb"
                )  # Create a dummy black ColorStop
            else:
                srgb_color = stop._parsed_color_obj.convert("srgb")

            r_val, g_val, b_val = [
                int(round(c * 255)) for c in srgb_color.coords(nans=False)[:3]
            ]
            alpha_srgb = srgb_color.alpha(nans=False)  # 0-1 or nan
            # Ensure alpha_srgb is not None before using it, and handle NaN from coloraide if alpha is not set
            a_val_0_1 = (
                alpha_srgb
                if alpha_srgb is not None and not srgb_color.is_nan("alpha")
                else 1.0
            )

            current_opacity = a_val_0_1 if opacity is None else opacity

            entry_attrs = {
                "color": f"#{r_val:02x}{g_val:02x}{b_val:02x}",
                "quantity": f"{data_val:.6f}",
                "opacity": f"{current_opacity:.2f}",
                "label": f"{stop.color} ({data_val:.2f})"
                if isinstance(stop.color, str)
                else f"Value {data_val:.2f}",
            }
            _create_sld_element(
                colormap_tag + "Entry", ns, color_map, attrib=entry_attrs
            )

            # For 'intervals', need to define the upper bound of the interval using the next stop's value
            # This is a simplified interpretation. Proper interval handling might need more logic.
            # SLD 'intervals' type often implies entries are min bounds of class.
            # If this is the last stop and type is 'intervals', it might need special handling or be implied to extend to +inf.
            # For simplicity, we treat 'values' and 'intervals' similarly here, using stop quantities.
            # A true 'intervals' might define <ColorMapEntry quantity="min1" color="c1"/><ColorMapEntry quantity="min2" color="c2"/>
            # where color c1 applies to [min1, min2).

    else:
        raise ValueError(f"Unsupported SLD ColorMap output_type: {output_type}")

    # Add ExtendedColorMap support for nodata (GeoServer specific)
    # if nodata_value is not None:
    #    # This is a GeoServer extension, not standard SLD for all servers.
    #    # <VendorOption name="nodata">...</VendorOption> or specific elements for ExtendedColorMap.
    #    pass

    # Convert XML tree to string with pretty printing
    try:
        ET.indent(sld_root, space="  ")
    except AttributeError:
        pass  # Fallback for older Python versions

    return ET.tostring(sld_root, encoding="unicode", xml_declaration=True)


# Example Usage:
if __name__ == "__main__":
    from palettize.core import Colormap, ColorStop
    from palettize.scaling import get_linear_scaler

    # Test colormap
    stops = [
        ColorStop("red", 0.0),
        ColorStop("yellow", 0.5),
        ColorStop((0, 255, 0, 128), 1.0),  # Green with alpha
    ]
    cmap = Colormap(stops, name="TestSLDRamp")
    scaler = get_linear_scaler(0, 100)

    print("--- SLD 1.0.0 RasterSymbolizer (ramp) ---")
    sld_output_ramp_raster = _export_sld_impl(
        cmap,
        scaler,
        0,
        100,
        num_colors=5,
        sld_version="1.0.0",
        output_type="ramp",
        geometry_type="raster",
        layer_name="MyRasterLayer",
        style_name="MyRasterStyle",
        band=1,
    )
    print(sld_output_ramp_raster)
    print("\n")

    print("--- SLD 1.1.0 PolygonSymbolizer (values, global opacity) ---")
    sld_output_values_poly = _export_sld_impl(
        cmap,
        scaler,
        0,
        100,
        sld_version="1.1.0",
        output_type="values",
        opacity=0.75,
        geometry_type="polygon",
        layer_name="MyPolygonLayer",
        style_name="MyPolygonStyle",
    )
    print(sld_output_values_poly)
    print("\n")

    # Test with a simpler colormap for intervals
    simple_stops = [ColorStop("blue", 0.25), ColorStop("green", 0.75)]
    simple_cmap = Colormap(simple_stops, name="IntervalTest")
    print("--- SLD 1.0.0 RasterSymbolizer (intervals) ---")
    sld_output_intervals = _export_sld_impl(
        simple_cmap,
        scaler,
        0,
        100,
        output_type="intervals",
        sld_version="1.0.0",
        geometry_type="raster",
        layer_name="MyIntervalLayer",
        style_name="MyIntervalStyle",
    )
    print(sld_output_intervals)

"""OGC SLD (Styled Layer Descriptor) exporter for Palettize."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec

NAMESPACES = {
    "sld": "http://www.opengis.net/sld",
    "ogc": "http://www.opengis.net/ogc",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "se": "http://www.opengis.net/se",
}

_SYMBOLIZERS = {
    "raster": "sld:RasterSymbolizer",
    "polygon": "sld:PolygonSymbolizer",
    "line": "sld:LineSymbolizer",
    "point": "sld:PointSymbolizer",
}


def _element(
    tag: str,
    parent: ET.Element | None = None,
    attrib: dict[str, str] | None = None,
    text: str | None = None,
) -> ET.Element:
    """Create a namespaced SLD element, optionally as a child of ``parent``."""
    prefix, _, local = tag.rpartition(":")
    namespace = NAMESPACES.get(prefix or "sld", NAMESPACES["sld"])
    qualified = f"{{{namespace}}}{local}"

    element = (
        ET.Element(qualified, attrib=attrib or {})
        if parent is None
        else ET.SubElement(parent, qualified, attrib=attrib or {})
    )
    if text:
        element.text = text
    return element


class SldExporter(BaseExporter):
    """OGC Styled Layer Descriptor XML, as used by GeoServer and MapServer."""

    uses_domain: ClassVar[bool] = True
    uses_scaler: ClassVar[bool] = True

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt("sld_version", str, "1.0.0", "SLD version.", choices=("1.0.0", "1.1.0")),
        Opt(
            "output_type",
            str,
            "ramp",
            "Interpolated ramp, or discrete entries from the colormap stops.",
            choices=("ramp", "intervals", "values"),
        ),
        Opt(
            "opacity",
            float,
            None,
            "Fixed opacity for every entry. Defaults to each color's own alpha.",
            minimum=0.0,
            maximum=1.0,
        ),
        Opt("layer_name", str, "palettize_layer", "UserLayer name."),
        Opt("style_name", str, "palettize_style", "UserStyle name."),
        Opt(
            "geometry_type",
            str,
            "raster",
            "Symbolizer to wrap the color map in.",
            choices=tuple(_SYMBOLIZERS),
        ),
        Opt("band", int, None, "Source band for the raster symbolizer (SLD 1.1 only)."),
    )

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
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        self.validate_domain(domain_min, domain_max)

        sld_version = opts["sld_version"]
        for prefix, uri in NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        root = ET.Element(
            f"{{{NAMESPACES['sld']}}}StyledLayerDescriptor",
            attrib={
                "version": sld_version,
                f"{{{NAMESPACES['xsi']}}}schemaLocation": (
                    f"{NAMESPACES['sld']} "
                    f"http://schemas.opengis.net/sld/{sld_version}/StyledLayerDescriptor.xsd"
                ),
            },
        )

        user_layer = _element("sld:UserLayer", root)
        _element(
            "sld:Name",
            user_layer,
            text=opts["layer_name"] or colormap.name or "Palettize Layer",
        )

        user_style = _element("sld:UserStyle", user_layer)
        _element(
            "sld:Name",
            user_style,
            text=opts["style_name"] or colormap.name or "Palettize Style",
        )
        _element("sld:IsDefault", user_style, text="1")

        rule = _element("sld:Rule", _element("sld:FeatureTypeStyle", user_style))
        _element("sld:Name", rule, text="Default Rule")

        geometry_type = opts["geometry_type"]
        symbolizer = _element(_SYMBOLIZERS[geometry_type], rule)
        if geometry_type == "raster" and opts["band"] is not None and sld_version.startswith("1.1"):
            channel = _element("se:ChannelSelection", symbolizer)
            gray = _element("se:GrayChannel", channel)
            _element("se:SourceChannelName", gray, text=str(opts["band"]))

        colormap_tag = "sld:ColorMap" if sld_version == "1.0.0" else "se:ColorMap"
        color_map = _element(colormap_tag, symbolizer, attrib={"type": opts["output_type"]})

        if opts["output_type"] == "ramp":
            self._add_ramp_entries(
                color_map,
                colormap_tag,
                colormap,
                scaler,
                domain_min,
                domain_max,
                opts["num_colors"],
                opts["opacity"],
            )
        else:
            self._add_stop_entries(
                color_map, colormap_tag, colormap, domain_min, domain_max, opts["opacity"]
            )

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def _add_ramp_entries(
        self,
        color_map: ET.Element,
        colormap_tag: str,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        num_colors: int,
        opacity: float | None,
    ) -> None:
        samples = self.sample_scaled(colormap, scaler, num_colors, domain_min, domain_max)
        for i, (data_value, color) in enumerate(samples):
            r, g, b, a = color
            attrs = {
                "color": f"#{r:02x}{g:02x}{b:02x}",
                "quantity": f"{data_value:.6f}",
                "opacity": f"{(a / 255.0 if opacity is None else opacity):.2f}",
            }
            if colormap.name and i == 0:
                attrs["label"] = f"{colormap.name} Start ({data_value:.2f})"
            elif colormap.name and i == len(samples) - 1:
                attrs["label"] = f"{colormap.name} End ({data_value:.2f})"
            _element(f"{colormap_tag}Entry", color_map, attrib=attrs)

    def _add_stop_entries(
        self,
        color_map: ET.Element,
        colormap_tag: str,
        colormap: Colormap,
        domain_min: float,
        domain_max: float,
        opacity: float | None,
    ) -> None:
        for stop in sorted(colormap.stops, key=lambda s: s.position or 0.0):
            position = stop.position or 0.0
            data_value = domain_min + position * (domain_max - domain_min)
            srgb = stop.parsed_color.convert("srgb")
            r, g, b = (round(c * 255) for c in srgb.coords(nans=False)[:3])
            alpha = 1.0 if srgb.is_nan("alpha") else srgb.alpha()

            label = (
                f"{stop.color} ({data_value:.2f})"
                if isinstance(stop.color, str)
                else f"Value {data_value:.2f}"
            )
            _element(
                f"{colormap_tag}Entry",
                color_map,
                attrib={
                    "color": f"#{r:02x}{g:02x}{b:02x}",
                    "quantity": f"{data_value:.6f}",
                    "opacity": f"{(alpha if opacity is None else opacity):.2f}",
                    "label": label,
                },
            )

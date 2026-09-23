"""QGIS color ramp exporter for Palettize."""

from __future__ import annotations

import warnings
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec


class QgisExporter(BaseExporter):
    """QGIS color ramp XML, loadable as a style or embedded in a ``.qml``."""

    uses_domain: ClassVar[bool] = True
    uses_scaler: ClassVar[bool] = True

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "ramp_type",
            str,
            "gradient",
            "Interpolated gradient, or discrete entries from the colormap stops.",
            choices=("gradient", "exact", "approximate"),
        ),
        Opt("name", str, None, "Ramp name. Defaults to the colormap name."),
        Opt("tags", list, None, "Comma-separated tags recorded on the ramp."),
        Opt(
            "opacity",
            float,
            1.0,
            "Overall opacity multiplier applied to every entry.",
            minimum=0.0,
            maximum=1.0,
        ),
        Opt("color_space", str, None, "QGIS colorSpace attribute hint, e.g. RGB."),
    )

    @property
    def identifier(self) -> str:
        return "qgis"

    @property
    def name(self) -> str:
        return "QGIS Color Ramp XML"

    @property
    def default_file_extension(self) -> str:
        return "xml"

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

        ramp_type = opts["ramp_type"]
        opacity = opts["opacity"]

        attribs = {
            "name": opts["name"] or colormap.name or "Palettize Ramp",
            "type": ramp_type,
        }
        if opts["tags"]:
            attribs["tags"] = ";".join(opts["tags"])
        if opts["color_space"]:
            attribs["colorSpace"] = opts["color_space"]

        root = ET.Element("colorramps")
        ramp = ET.SubElement(root, "colorramp", attribs)

        if ramp_type == "gradient":
            self._add_gradient_items(
                ramp, colormap, scaler, domain_min, domain_max, opts["num_colors"], opacity
            )
        else:
            self._add_discrete_items(ramp, colormap, domain_min, domain_max, opacity)

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def _add_gradient_items(
        self,
        ramp: ET.Element,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        num_colors: int,
        opacity: float,
    ) -> None:
        positions = self.sample_positions(num_colors)
        samples = self.sample_scaled(colormap, scaler, num_colors, domain_min, domain_max)
        for position, (_, color) in zip(positions, samples, strict=True):
            r, g, b, a = color
            ET.SubElement(
                ramp,
                "item",
                {
                    "alpha": str(self._scaled_alpha(a, opacity)),
                    "color": f"#{r:02x}{g:02x}{b:02x}",
                    "position": f"{position:.4f}",
                },
            )

    def _add_discrete_items(
        self,
        ramp: ET.Element,
        colormap: Colormap,
        domain_min: float,
        domain_max: float,
        opacity: float,
    ) -> None:
        if not colormap.stops:
            warnings.warn(
                "Colormap has no stops; generating an empty QGIS ramp.",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        for stop in sorted(colormap.stops, key=lambda s: s.position or 0.0):
            position = stop.position or 0.0
            data_value = domain_min + position * (domain_max - domain_min)
            srgb = stop.parsed_color.convert("srgb")
            r, g, b = (round(c * 255) for c in srgb.coords(nans=False)[:3])
            a = 255 if srgb.is_nan("alpha") else round(srgb.alpha() * 255)
            ET.SubElement(
                ramp,
                "item",
                {
                    "value": f"{data_value:.4f}",
                    "color": f"#{r:02x}{g:02x}{b:02x}",
                    "alpha": str(self._scaled_alpha(a, opacity)),
                    "label": f"{data_value:.2f}",
                },
            )

    @staticmethod
    def _scaled_alpha(alpha_255: int, opacity: float) -> int:
        """Combine a per-color alpha with the ramp-wide opacity, clamped to 0-255."""
        return max(0, min(255, int(alpha_255 * opacity)))

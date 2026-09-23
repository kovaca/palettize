"""Exporter for SVG gradient elements."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar
from xml.sax.saxutils import escape, quoteattr

from palettize.core import Colormap, ScalingFunction

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec


class SVGExporter(BaseExporter):
    """SVG ``<linearGradient>`` / ``<radialGradient>`` definitions."""

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "gradient_type",
            str,
            "linear",
            "Gradient element to emit.",
            choices=("linear", "radial"),
        ),
        Opt("gradient_id", str, "palette", "id attribute of the gradient element."),
        Opt("include_defs", bool, True, "Wrap the gradient in a <defs> element."),
        Opt("full_svg", bool, False, "Emit a complete SVG document with a preview shape."),
        Opt("x1", str, "0%", "Linear gradient start x."),
        Opt("y1", str, "0%", "Linear gradient start y."),
        Opt("x2", str, "100%", "Linear gradient end x."),
        Opt("y2", str, "0%", "Linear gradient end y."),
        Opt("cx", str, "50%", "Radial gradient center x."),
        Opt("cy", str, "50%", "Radial gradient center y."),
        Opt("r", str, "50%", "Radial gradient radius."),
    )

    @property
    def identifier(self) -> str:
        return "svg"

    @property
    def name(self) -> str:
        return "SVG Gradient"

    @property
    def default_file_extension(self) -> str:
        return "svg"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        num_colors = opts["num_colors"]

        stops = "\n".join(
            f'    <stop offset="{position * 100:.2f}%" stop-color="{color}"/>'
            for position, color in zip(
                self.sample_positions(num_colors),
                colormap.hex_colors(num_colors),
                strict=True,
            )
        )

        gradient_id = opts["gradient_id"]
        # quoteattr escapes quotes inside the reference; escape() alone would
        # leave `fill="url(#a"b)"` as broken markup.
        fill_ref = quoteattr(f"url(#{gradient_id})")
        if opts["gradient_type"] == "linear":
            coords = " ".join(f"{k}={quoteattr(str(opts[k]))}" for k in ("x1", "y1", "x2", "y2"))
            gradient = (
                f"  <linearGradient id={quoteattr(gradient_id)} {coords}>\n"
                f"{stops}\n"
                f"  </linearGradient>"
            )
        else:
            coords = " ".join(f"{k}={quoteattr(str(opts[k]))}" for k in ("cx", "cy", "r"))
            gradient = (
                f"  <radialGradient id={quoteattr(gradient_id)} {coords}>\n"
                f"{stops}\n"
                f"  </radialGradient>"
            )

        content = f"<defs>\n{gradient}\n</defs>" if opts["include_defs"] else gradient

        if opts["full_svg"]:
            if opts["gradient_type"] == "linear":
                shape = f'<rect x="0" y="0" width="400" height="50" fill={fill_ref}/>'
            else:
                shape = f'<circle cx="200" cy="100" r="100" fill={fill_ref}/>'
            title = escape(colormap.name or "palette")
            content = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">\n'
                f"  <title>{title}</title>\n"
                f"{content}\n"
                f"  {shape}\n"
                "</svg>"
            )

        return content

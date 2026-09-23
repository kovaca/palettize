"""Exporter for CSS custom properties (CSS variables)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction
from palettize.exceptions import ExporterOptionError

from ._base import NUM_COLORS_OPT, BaseExporter
from ._options import Opt, OptionSpec


def _reject_css_breakout(name: str, value: Any) -> str:
    """Refuse values that can close a rule or a comment."""
    text = str(value)
    if any(token in text for token in ("}", "\n", "\r", "*/")):
        raise ExporterOptionError(
            f"Option '{name}' must not contain '}}', newlines, or '*/'. Got: {value!r}"
        )
    return text


def _parse_prefix(value: Any) -> str:
    return _reject_css_breakout("prefix", value)


def _parse_selector(value: Any) -> str:
    return _reject_css_breakout("selector", value)


class CSSExporter(BaseExporter):
    """CSS custom properties, one variable per sampled color."""

    options: ClassVar[OptionSpec] = OptionSpec(
        NUM_COLORS_OPT,
        Opt(
            "prefix",
            str,
            "color",
            "Variable name prefix, as in --{prefix}-0.",
            parser=_parse_prefix,
        ),
        Opt(
            "selector",
            str,
            ":root",
            "Selector wrapping the variables. Empty string emits bare declarations.",
            parser=_parse_selector,
        ),
        Opt(
            "color_format",
            str,
            "hex",
            "Format of the primary color value.",
            choices=("hex", "hsl", "rgb"),
        ),
        Opt("include_hsl", bool, False, "Also emit --{prefix}-{n}-hsl variables."),
        Opt(
            "include_rgb",
            bool,
            False,
            "Also emit --{prefix}-{n}-r/-g/-b component variables.",
        ),
    )

    @property
    def identifier(self) -> str:
        return "css"

    @property
    def name(self) -> str:
        return "CSS Custom Properties"

    @property
    def default_file_extension(self) -> str:
        return "css"

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
        prefix = opts["prefix"]
        color_format = opts["color_format"]
        include_hsl = opts["include_hsl"]
        include_rgb = opts["include_rgb"]

        hex_colors = colormap.hex_colors(num_colors)
        hsl_colors = colormap.hsl_colors(num_colors)
        rgb_colors = colormap.rgb_colors(num_colors)

        lines: list[str] = []
        for i in range(num_colors):
            h, s, lightness = hsl_colors[i]
            r, g, b = rgb_colors[i]
            var_name = f"--{prefix}-{i}"
            hsl_text = f"hsl({h:.0f}, {s:.0f}%, {lightness:.0f}%)"

            if color_format == "hex":
                lines.append(f"  {var_name}: {hex_colors[i]};")
            elif color_format == "hsl":
                lines.append(f"  {var_name}: {hsl_text};")
            else:
                lines.append(f"  {var_name}: rgb({r}, {g}, {b});")

            if include_hsl and color_format != "hsl":
                lines.append(f"  {var_name}-hsl: {hsl_text};")
            if include_rgb:
                lines.append(f"  {var_name}-r: {r};")
                lines.append(f"  {var_name}-g: {g};")
                lines.append(f"  {var_name}-b: {b};")

        selector = opts["selector"]
        if selector:
            return f"{selector} {{\n" + "\n".join(lines) + "\n}"
        return "\n".join(lines)

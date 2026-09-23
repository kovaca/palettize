"""Palettize: Python utility and CLI tool for generating and exporting colormaps.

This module exposes a small, stable programmatic API so Palettize can be used
directly from Python scripts and notebooks (in addition to the CLI).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _pkg_version

from .analysis import ColormapAnalysis, analyze, simulate_cvd
from .core import (
    SCHEMA_VERSION,
    Colormap,
    ColorStop,
    InputColor,
    format_color,
    parse_input_color,
    sample_positions,
)
from .exceptions import (
    ColormapFileError,
    ExporterOptionError,
    InvalidColorError,
    PalettizeError,
    PresetNotFoundError,
)
from .exporters import (
    BaseExporter,
    Opt,
    OptionSpec,
    get_exporter,
    list_available_exporters,
    load_plugin_exporters,
    register_exporter,
)
from .presets import (
    PresetInfo,
    get_preset_info,
    list_available_presets,
    list_categories,
    load_preset_data,
    search_presets,
)
from .render import png_bytes, svg_document, terminal_swatch, write_image
from .scaling import (
    ScalingFunction,
    get_linear_scaler,
    get_log_scaler,
    get_power_scaler,
    get_scaler_by_name,
    get_sqrt_scaler,
    get_symlog_scaler,
)

try:
    __version__ = _pkg_version("palettize")
except _PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0.dev0"


def create_colormap(
    *,
    preset: str | None = None,
    colors: list[InputColor] | None = None,
    interpolation_space: str = "oklch",
    name: str | None = None,
    cut_start: float = 0.0,
    cut_end: float = 1.0,
) -> Colormap:
    """Create a `Colormap` either from a preset name or a list of colors.

    Exactly one of `preset` or `colors` must be provided.

    Args:
        preset: Name of a preset palette (e.g., "viridis" or "custom/grayscale").
        colors: List of colors (hex, tuples, named strings, ColorAide `Color`, or dicts).
        interpolation_space: Color space used for interpolation (default "oklch").
        name: Optional name for the resulting colormap.
        cut_start: Start of the sub-segment of the colormap to use (0-1).
        cut_end: End of the sub-segment of the colormap to use (0-1).

    Returns:
        A `Colormap` instance.

    Raises:
        ValueError: If neither or both of `preset` and `colors` are provided, or
                    if parameters are otherwise invalid.
    """
    if (preset is None and not colors) or (preset is not None and colors):
        raise ValueError("Provide exactly one of `preset` or `colors`.")

    if preset is not None:
        cmap = Colormap.from_preset(
            preset_name=preset,
            interpolation_space=interpolation_space,
            cut_start=cut_start,
            cut_end=cut_end,
        )
    else:
        assert colors is not None
        cmap = Colormap.from_list(
            colors=colors,
            interpolation_space=interpolation_space,
            cut_start=cut_start,
            cut_end=cut_end,
        )

    if name:
        cmap.name = name
    return cmap


__all__ = (
    "SCHEMA_VERSION",
    "BaseExporter",
    "ColorStop",
    "Colormap",
    "ColormapAnalysis",
    "ColormapFileError",
    "ExporterOptionError",
    "InputColor",
    "InvalidColorError",
    "Opt",
    "OptionSpec",
    "PalettizeError",
    "PresetInfo",
    "PresetNotFoundError",
    "ScalingFunction",
    "__version__",
    "analyze",
    "create_colormap",
    "format_color",
    "get_exporter",
    "get_linear_scaler",
    "get_log_scaler",
    "get_power_scaler",
    "get_preset_info",
    "get_scaler_by_name",
    "get_sqrt_scaler",
    "get_symlog_scaler",
    "list_available_exporters",
    "list_available_presets",
    "list_categories",
    "load_plugin_exporters",
    "load_preset_data",
    "parse_input_color",
    "png_bytes",
    "register_exporter",
    "sample_positions",
    "search_presets",
    "simulate_cvd",
    "svg_document",
    "terminal_swatch",
    "write_image",
)

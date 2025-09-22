"""Palettize: Python utility and CLI tool for generating and exporting colormaps.

This module exposes a small, stable programmatic API so Palettize can be used
directly from Python scripts and notebooks (in addition to the CLI).
"""

from __future__ import annotations

from typing import List, Optional

from .core import (
    Colormap,
    ColorStop,
    InputColor,
    parse_input_color,
)
from .presets import list_available_presets, load_preset_data
from .scaling import (
    ScalingFunction,
    get_scaler_by_name,
    get_linear_scaler,
    get_power_scaler,
    get_sqrt_scaler,
    get_log_scaler,
    get_symlog_scaler,
)
from .exporters import (
    list_available_exporters,
    get_exporter,
    register_exporter,
    load_plugin_exporters,
)

# NOTE: When packaging via setuptools_scm, the version is provided dynamically.
# Keeping a fallback here for local development if desired.
__version__ = "0.0.1.dev0"


def create_colormap(
    *,
    preset: Optional[str] = None,
    colors: Optional[List[InputColor]] = None,
    interpolation_space: str = "oklch",
    name: Optional[str] = None,
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
    # Version
    "__version__",
    # Core colormap API
    "Colormap",
    "ColorStop",
    "InputColor",
    "parse_input_color",
    "create_colormap",
    # Presets
    "list_available_presets",
    "load_preset_data",
    # Scaling
    "ScalingFunction",
    "get_scaler_by_name",
    "get_linear_scaler",
    "get_power_scaler",
    "get_sqrt_scaler",
    "get_log_scaler",
    "get_symlog_scaler",
    # Exporters
    "list_available_exporters",
    "get_exporter",
    "register_exporter",
    "load_plugin_exporters",
)

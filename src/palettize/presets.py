# src/palettize/presets.py

"""Manages preset colormaps for Palettize."""

from typing import Dict, List, Union, Optional, Tuple, TYPE_CHECKING
from palettize.exceptions import PresetNotFoundError

if TYPE_CHECKING:
    from palettize.core import InputColor
    # import cmap as cmap_module # Keep for potential type hinting needs

# Attempt to import cmap for extended presets
try:
    import cmap as cmap_module
    from coloraide import Color as ColorAideColor  # For converting cmap colors

    CMAP_AVAILABLE = True
except ImportError:
    cmap_module = None
    ColorAideColor = None  # type: ignore # To satisfy linter if CMAP_AVAILABLE is false
    CMAP_AVAILABLE = False

# Preset definitions: A dictionary where keys are preset names
# and values are lists of colors or (color, position) tuples.
# Positions are optional and normalized between 0.0 and 1.0.
PresetDataType = List[Union["InputColor", Tuple["InputColor", Optional[float]]]]

# Palettize's native presets
# User has prefixed these with "custom/"
PRESET_PALETTES: Dict[str, PresetDataType] = {
    "custom/grayscale": ["#000000", "#FFFFFF"],
    "custom/simple_rgb": ["#FF0000", "#00FF00", "#0000FF"],
    "custom/custom_stops": [("#FF0000", 0.0), ("#FFFF00", 0.5), ("#00FF00", 1.0)],
    "custom/viridis_short": [  # A very short, simplified version of viridis for testing
        "#440154",
        "#31688E",
        "#35B779",
        "#FDE725",
    ],
}

# Cache for cmap preset data to avoid repeated conversions
_cmap_preset_cache: Dict[str, PresetDataType] = {}
_cmap_available_names_cache: Optional[List[str]] = None


def _get_cmap_color_data(cmap_name_from_cmap: str) -> Optional[PresetDataType]:
    """
    Fetches and converts color data for a given cmap preset name (e.g., 'matplotlib:viridis').
    Returns None if cmap is not available or the specific map is not found/convertible.
    """
    if not CMAP_AVAILABLE or not ColorAideColor or not cmap_module:
        return None

    if cmap_name_from_cmap in _cmap_preset_cache:
        return _cmap_preset_cache[cmap_name_from_cmap]

    actual_cmap_name = cmap_name_from_cmap

    try:
        cmap_obj = cmap_module.Colormap(actual_cmap_name)
        if cmap_obj is None:
            return None

        hex_colors: PresetDataType = []

        if hasattr(cmap_obj, "colors") and cmap_obj.colors is not None:
            for idx, color_data in enumerate(cmap_obj.colors):
                if not (isinstance(color_data, (list, tuple)) and len(color_data) >= 3):
                    continue
                try:
                    r, g, b = color_data[0], color_data[1], color_data[2]
                    hex_color_str = ColorAideColor(
                        "srgb", [float(r), float(g), float(b)]
                    ).to_string(hex=True)
                    hex_colors.append(hex_color_str)
                except Exception:
                    continue
        elif hasattr(cmap_obj, "iter_colors"):
            num_samples = getattr(cmap_obj, "num_colors", 256)
            try:
                for color_data_item in cmap_obj.iter_colors(num_samples):
                    if (
                        cmap_module
                        and hasattr(cmap_module, "_color")
                        and isinstance(color_data_item, cmap_module._color.Color)
                    ):
                        hex_colors.append(str(color_data_item))
                    elif isinstance(color_data_item, str):
                        hex_colors.append(color_data_item)
                    elif (
                        isinstance(color_data_item, tuple) and len(color_data_item) >= 3
                    ):
                        try:
                            rgb_components = [float(c) for c in color_data_item[:3]]
                            hex_color_str = ColorAideColor(
                                "srgb", rgb_components
                            ).to_string(hex=True)
                            hex_colors.append(hex_color_str)
                        except Exception:
                            continue
                    else:
                        continue
            except Exception:
                pass  # Error calling iter_colors or during its iteration
        else:
            return None

        if hex_colors:
            _cmap_preset_cache[cmap_name_from_cmap] = hex_colors
            return hex_colors

        return None

    except Exception:
        return None


def load_preset_data(name: str) -> PresetDataType:
    """Loads raw preset data (list of colors/stops) by name."""
    if name in PRESET_PALETTES:
        return PRESET_PALETTES[name]

    if CMAP_AVAILABLE:
        cmap_data = _get_cmap_color_data(name)
        if cmap_data:
            return cmap_data

    raise PresetNotFoundError(
        f"Preset '{name}' not found. If using a cmap preset (e.g., matplotlib:viridis), ensure 'cmap' library is installed and the name is correct."
    )


def list_available_presets() -> List[str]:
    """Returns a list of available preset names, including those from cmap if installed."""
    global _cmap_available_names_cache

    native_presets = sorted(list(PRESET_PALETTES.keys()))

    if not CMAP_AVAILABLE:
        return native_presets

    if _cmap_available_names_cache is not None:
        return sorted(list(set(native_presets + _cmap_available_names_cache)))

    _cmap_available_names_cache = []
    if cmap_module:
        try:
            if hasattr(cmap_module, "Catalog"):
                catalog_instance = cmap_module.Catalog()
                all_cmap_keys = catalog_instance.unique_keys(
                    prefer_short_names=False, normalized_names=True
                )
                _cmap_available_names_cache.extend(all_cmap_keys)

            _cmap_available_names_cache.sort()
        except Exception:
            pass

    return sorted(
        list(
            set(
                native_presets
                + (_cmap_available_names_cache if _cmap_available_names_cache else [])
            )
        )
    )

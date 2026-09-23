"""Preset colormap management for Palettize.

Palettize ships a handful of native presets and, when the optional ``cmap``
dependency is installed, exposes its full catalog of several hundred named
colormaps along with their category and provenance metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Union

from palettize.exceptions import PresetNotFoundError

if TYPE_CHECKING:
    from palettize.core import InputColor

try:
    import cmap as cmap_module
    from coloraide import Color as ColorAideColor

    CMAP_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the optional dep
    cmap_module = None  # type: ignore[assignment]
    ColorAideColor = None  # type: ignore[assignment,misc]
    CMAP_AVAILABLE = False

#: A preset is a list of colors, optionally paired with explicit positions.
PresetDataType = list[Union["InputColor", tuple["InputColor", float | None]]]

#: Category assigned to Palettize's own presets, which ``cmap`` knows nothing about.
NATIVE_NAMESPACE = "palettize"

# Palettize's native presets.
PRESET_PALETTES: dict[str, PresetDataType] = {
    "custom/grayscale": ["#000000", "#FFFFFF"],
    "custom/simple_rgb": ["#FF0000", "#00FF00", "#0000FF"],
    "custom/custom_stops": [("#FF0000", 0.0), ("#FFFF00", 0.5), ("#00FF00", 1.0)],
    "custom/viridis_short": [
        "#440154",
        "#31688E",
        "#35B779",
        "#FDE725",
    ],
}

_cmap_preset_cache: dict[str, PresetDataType] = {}
_cmap_names_cache: list[str] | None = None
_preset_info_cache: dict[str, PresetInfo] = {}


@dataclass(frozen=True)
class PresetInfo:
    """Descriptive metadata about a single preset."""

    name: str
    """Fully qualified preset name, as accepted by :func:`load_preset_data`."""

    category: str
    """``sequential``, ``diverging``, ``cyclic``, ``qualitative``, or ``miscellaneous``."""

    namespace: str
    """Publisher of the colormap, e.g. ``matplotlib`` or ``colorbrewer``."""

    license: str = ""
    source: str = ""

    @property
    def short_name(self) -> str:
        """The name without its namespace prefix."""
        return self.name.rpartition(":")[2] if ":" in self.name else self.name


def _get_cmap_color_data(name: str) -> PresetDataType | None:
    """Fetch and convert color data for a ``cmap`` preset, or ``None`` if absent."""
    if not CMAP_AVAILABLE:
        return None
    if name in _cmap_preset_cache:
        return _cmap_preset_cache[name]

    try:
        cmap_obj = cmap_module.Colormap(name)
    except Exception:
        return None

    hex_colors: PresetDataType = []
    raw_colors = getattr(cmap_obj, "colors", None)
    if raw_colors:
        for color_data in raw_colors:
            converted = _to_hex(color_data)
            if converted:
                hex_colors.append(converted)
    elif hasattr(cmap_obj, "iter_colors"):
        try:
            for item in cmap_obj.iter_colors(getattr(cmap_obj, "num_colors", 256)):
                converted = _to_hex(item)
                if converted:
                    hex_colors.append(converted)
        except Exception:
            return None

    if not hex_colors:
        return None
    _cmap_preset_cache[name] = hex_colors
    return hex_colors


def _to_hex(color_data: Any) -> str | None:
    """Best-effort conversion of one ``cmap`` color into a hex string."""
    if isinstance(color_data, str):
        return color_data
    if isinstance(color_data, (list, tuple)) and len(color_data) >= 3:
        try:
            components = [float(c) for c in color_data[:3]]
        except (TypeError, ValueError):
            return None
        return ColorAideColor("srgb", components).to_string(hex=True)
    # cmap's own Color objects stringify to a usable CSS color.
    text = str(color_data)
    return text if text else None


def load_preset_data(name: str) -> PresetDataType:
    """Load the raw color data for a preset by name.

    Raises:
        PresetNotFoundError: If no built-in or ``cmap`` preset matches.
    """
    if name in PRESET_PALETTES:
        return PRESET_PALETTES[name]

    if CMAP_AVAILABLE:
        cmap_data = _get_cmap_color_data(name)
        if cmap_data:
            return cmap_data

    hint = (
        " Run 'palettize list presets --search <term>' to find one."
        if CMAP_AVAILABLE
        else " Install the 'cmap' package for several hundred additional presets."
    )
    raise PresetNotFoundError(f"Preset '{name}' not found.{hint}")


def list_available_presets() -> list[str]:
    """Return every available preset name, sorted."""
    global _cmap_names_cache

    native = sorted(PRESET_PALETTES)
    if not CMAP_AVAILABLE:
        return native

    if _cmap_names_cache is None:
        _cmap_names_cache = []
        try:
            catalog = cmap_module.Catalog()
            _cmap_names_cache = sorted(
                catalog.unique_keys(prefer_short_names=False, normalized_names=True)
            )
        except Exception:  # pragma: no cover - depends on cmap internals
            _cmap_names_cache = []

    return sorted(set(native) | set(_cmap_names_cache))


def get_preset_info(name: str) -> PresetInfo | None:
    """Return metadata for a preset, or ``None`` if it is unknown."""
    if name in _preset_info_cache:
        return _preset_info_cache[name]

    if name in PRESET_PALETTES:
        info = PresetInfo(name=name, category="miscellaneous", namespace=NATIVE_NAMESPACE)
        _preset_info_cache[name] = info
        return info

    if not CMAP_AVAILABLE:
        return None

    try:
        item = cmap_module.Catalog()[name]
    except Exception:
        return None

    info = PresetInfo(
        name=name,
        category=getattr(item, "category", "miscellaneous") or "miscellaneous",
        namespace=getattr(item, "namespace", "") or "",
        license=getattr(item, "license", "") or "",
        source=getattr(item, "source", "") or "",
    )
    _preset_info_cache[name] = info
    return info


def search_presets(
    query: str | None = None,
    category: str | None = None,
    namespace: str | None = None,
) -> list[PresetInfo]:
    """Find presets matching all of the given filters.

    Args:
        query: Case-insensitive substring matched against the preset name.
        category: Exact category match, e.g. ``"diverging"``.
        namespace: Exact namespace match, e.g. ``"colorbrewer"``.

    Returns:
        Matching presets sorted by name. Metadata lookups that fail are skipped
        only when a metadata-dependent filter is active, so a plain name search
        still returns presets whose catalog entry cannot be read.
    """
    query_lower = query.lower() if query else None
    needs_metadata = bool(category or namespace)

    results: list[PresetInfo] = []
    for name in list_available_presets():
        if query_lower and query_lower not in name.lower():
            continue

        info = get_preset_info(name)
        if info is None:
            if needs_metadata:
                continue
            info = PresetInfo(name=name, category="unknown", namespace="")

        if category and info.category != category:
            continue
        if namespace and info.namespace != namespace:
            continue
        results.append(info)

    return results


def list_categories() -> list[str]:
    """Return the distinct categories present in the available presets."""
    return sorted({info.category for info in search_presets()})

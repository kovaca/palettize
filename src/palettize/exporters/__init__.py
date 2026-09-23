"""Exporter registration and discovery for Palettize.

Built-in exporters are registered lazily: the registry knows their module and
class names up front, but nothing is imported until an exporter is actually
requested. This keeps ``palettize --help`` from paying to import 14 modules.
Third-party exporters register through the ``palettize.exporters`` entry point
group and are discovered on first use.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import warnings
from typing import TYPE_CHECKING

from ._base import BaseExporter
from ._options import Opt, OptionSpec

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checkers only
    pass

#: Entry point group third-party exporter plugins register under.
EXPORTER_ENTRY_POINT_GROUP = "palettize.exporters"

# identifier -> (module suffix, class name, human-readable name, file extension).
# Mirrors each exporter's own metadata so listings and lookups avoid imports.
_BUILTIN_SPECS: dict[str, tuple[str, str, str, str]] = {
    "gdal": ("gdal", "GdalExporter", "GDAL Color Relief Text", "txt"),
    "qgis": ("qgis", "QgisExporter", "QGIS Color Ramp XML", "xml"),
    "sld": ("sld", "SldExporter", "OGC SLD XML", "sld"),
    "titiler": ("titiler", "TitilerExporter", "TiTiler Colormap URL Parameter", "txt"),
    "mapgl": ("mapgl", "MapglExporter", "MapLibre GL JS Expression", "json"),
    "observable": (
        "observable_plot",
        "ObservablePlotExporter",
        "Observable Plot Scale",
        "json",
    ),
    "gee": ("gee", "GEEExporter", "Google Earth Engine Snippet", "js"),
    "hex": ("plaintext", "HexExporter", "Plaintext Hashed Hexadecimal", "txt"),
    "rgba": ("plaintext", "RGBAExporter", "Plaintext RGBA", "txt"),
    "hsl": ("plaintext", "HSLExporter", "Plaintext HSL", "txt"),
    "json": ("json", "JSONExporter", "JSON", "json"),
    "css": ("css", "CSSExporter", "CSS Custom Properties", "css"),
    "gimp": ("gimp", "GIMPExporter", "GIMP Palette", "gpl"),
    "svg": ("svg", "SVGExporter", "SVG Gradient", "svg"),
}

_EXPORTER_REGISTRY: dict[str, BaseExporter] = {}
_PLUGINS_LOADED = False


def register_exporter(exporter_instance: BaseExporter, overwrite: bool = False) -> None:
    """Register an exporter instance in the global registry.

    Args:
        exporter_instance: An instance of a :class:`BaseExporter` subclass.
        overwrite: Allow replacing an exporter that already claims this identifier.

    Raises:
        TypeError: If the object is not a :class:`BaseExporter`.
        ValueError: If the identifier is taken and ``overwrite`` is ``False``.
    """
    if not isinstance(exporter_instance, BaseExporter):
        raise TypeError(
            f"Exporter must be an instance of BaseExporter. Received: {type(exporter_instance)}"
        )

    identifier = exporter_instance.identifier
    if identifier in _EXPORTER_REGISTRY and not overwrite:
        raise ValueError(
            f"Exporter with identifier '{identifier}' already registered. "
            f"Use overwrite=True to replace it."
        )
    _EXPORTER_REGISTRY[identifier] = exporter_instance


def get_exporter(identifier: str) -> BaseExporter | None:
    """Return the exporter registered under ``identifier``, or ``None``.

    Built-in exporters are imported on first request; plugins are discovered
    the first time an unknown identifier is looked up.
    """
    if identifier in _EXPORTER_REGISTRY:
        return _EXPORTER_REGISTRY[identifier]

    if identifier in _BUILTIN_SPECS:
        instance = _instantiate_builtin(identifier)
        if instance is not None:
            return instance

    load_plugin_exporters()
    return _EXPORTER_REGISTRY.get(identifier)


def _instantiate_builtin(identifier: str) -> BaseExporter | None:
    """Import and register one built-in exporter, warning if it fails."""
    module_name, class_name, _, _ = _BUILTIN_SPECS[identifier]
    try:
        module = importlib.import_module(f".{module_name}", __name__)
        instance: BaseExporter = getattr(module, class_name)()
        register_exporter(instance, overwrite=True)
        return instance
    except Exception as e:  # pragma: no cover - defensive; a broken build only
        warnings.warn(
            f"Failed to load built-in exporter '{identifier}': {e}",
            RuntimeWarning,
            stacklevel=2,
        )
        return None


def list_available_exporters() -> dict[str, str]:
    """Map every known exporter identifier to its human-readable name.

    Built-in names come from the registry table, so listing stays import-free.
    """
    load_plugin_exporters()
    listing = {identifier: spec[2] for identifier, spec in _BUILTIN_SPECS.items()}
    listing.update(
        {identifier: exporter.name for identifier, exporter in _EXPORTER_REGISTRY.items()}
    )
    return listing


def exporter_file_extension(identifier: str) -> str | None:
    """Return an exporter's default file extension without importing it."""
    if identifier in _BUILTIN_SPECS:
        return _BUILTIN_SPECS[identifier][3]
    exporter = get_exporter(identifier)
    return exporter.default_file_extension if exporter else None


def load_plugin_exporters(force_reload: bool = False) -> None:
    """Discover exporter plugins via the ``palettize.exporters`` entry point group.

    Each entry point must resolve to a :class:`BaseExporter` subclass that can be
    instantiated with no arguments. A plugin that fails to load is skipped with a
    warning rather than taking down the whole registry.
    """
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED and not force_reload:
        return
    # Set before loading so a plugin importing palettize cannot recurse forever.
    _PLUGINS_LOADED = True

    try:
        entry_points = importlib.metadata.entry_points(group=EXPORTER_ENTRY_POINT_GROUP)
    except Exception as e:
        warnings.warn(
            f"Could not discover exporter plugins for group "
            f"'{EXPORTER_ENTRY_POINT_GROUP}': {e}. Proceeding without plugins.",
            RuntimeWarning,
            stacklevel=2,
        )
        return

    for entry_point in entry_points:
        try:
            exporter_class = entry_point.load()
            if not (isinstance(exporter_class, type) and issubclass(exporter_class, BaseExporter)):
                warnings.warn(
                    f"Plugin '{entry_point.name}' from '{entry_point.value}' does not "
                    f"inherit from BaseExporter. Skipping.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            register_exporter(exporter_class(), overwrite=True)
        except Exception as e:
            warnings.warn(
                f"Failed to load exporter plugin '{entry_point.name}' from "
                f"'{entry_point.value}': {e}",
                RuntimeWarning,
                stacklevel=2,
            )


__all__ = [
    "EXPORTER_ENTRY_POINT_GROUP",
    "BaseExporter",
    "Opt",
    "OptionSpec",
    "exporter_file_extension",
    "get_exporter",
    "list_available_exporters",
    "load_plugin_exporters",
    "register_exporter",
]

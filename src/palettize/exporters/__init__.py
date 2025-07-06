"""Exporters module for Palettize.

This module handles the registration and retrieval of colormap exporters.
"""

from typing import Dict, Optional
import warnings
from ._base import BaseExporter
import importlib.metadata
from .gdal import GdalExporter
from .qgis import QgisExporter
from .sld import SldExporter
from .titiler import TitilerExporter
from .mapgl import MapglExporter
from .observable_plot import ObservablePlotExporter

# Global registry for exporters
# Maps an identifier string to an instantiated exporter object or a callable that returns one.
# Using instantiated objects for now, assuming they are lightweight to create.
_EXPORTER_REGISTRY: Dict[str, BaseExporter] = {}


def register_exporter(exporter_instance: BaseExporter, overwrite: bool = False) -> None:
    """
    Registers an exporter instance in the global registry.

    Args:
        exporter_instance: An instance of a class derived from BaseExporter.
        overwrite: If True, allows overwriting an existing exporter with the same identifier.

    Raises:
        ValueError: If an exporter with the same identifier already exists and overwrite is False.
        TypeError: If the provided object is not an instance of BaseExporter.
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


def get_exporter(identifier: str) -> Optional[BaseExporter]:
    """
    Retrieves an exporter instance from the registry by its identifier.

    Args:
        identifier: The unique identifier of the exporter.

    Returns:
        The exporter instance if found, otherwise None.
    """
    return _EXPORTER_REGISTRY.get(identifier)


def list_available_exporters() -> Dict[str, str]:
    """
    Lists all available (registered) exporters.

    Returns:
        A dictionary mapping exporter identifiers to their human-readable names.
    """
    return {
        identifier: exporter.name for identifier, exporter in _EXPORTER_REGISTRY.items()
    }


# --- Built-in Exporter Registration ---
# Import and register built-in exporters here.
# This ensures they are available as soon as this module is imported.



_BUILTIN_EXPORTERS = [
    GdalExporter(),
    QgisExporter(),
    SldExporter(),
    TitilerExporter(),
    MapglExporter(),
    ObservablePlotExporter(),
]

for exporter_instance in _BUILTIN_EXPORTERS:
    try:
        register_exporter(exporter_instance)
    except ValueError as e:  # Handle if an identifier is somehow duplicated (should not happen for built-ins)
        warnings.warn(
            f"Failed to register built-in exporter {exporter_instance.identifier}: {e}",
            RuntimeWarning,
        )
    except (
        TypeError
    ) as e:  # Handle if an exporter does not correctly inherit from BaseExporter
        warnings.warn(
            f"Built-in exporter {type(exporter_instance).__name__} is not a valid BaseExporter: {e}",
            RuntimeWarning,
        )


# Future: Load built-in exporters here, or handle entry point loading.
# For now, built-in exporters will need to be refactored to use the BaseExporter
# interface and then registered manually or discovered.



# Define the entry point group name
EXPORTER_ENTRY_POINT_GROUP = "palettize.exporters"

_PLUGINS_LOADED = False


def load_plugin_exporters(force_reload: bool = False) -> None:
    """
    Discovers and loads exporter plugins using importlib.metadata entry points.

    Plugins should be registered under the group 'palettize.exporters'.
    Each entry point should point to a class that implements BaseExporter.

    Args:
        force_reload: If True, reloads plugins even if they have been loaded before.
    """
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED and not force_reload:
        return

    try:
        entry_points = importlib.metadata.entry_points(group=EXPORTER_ENTRY_POINT_GROUP)
    except TypeError:  # Compatibility for Python < 3.10 where select was used
        try:
            entry_points = importlib.metadata.entry_points().select(
                group=EXPORTER_ENTRY_POINT_GROUP
            )
        except (
            AttributeError
        ):  # In case .select is also not available or group is not found
            entry_points = []  # No plugins found or error during discovery
            warnings.warn(
                f"Could not discover plugins using importlib.metadata for group '{EXPORTER_ENTRY_POINT_GROUP}'. "
                f"This might be due to an older Python version or an issue with plugin discovery mechanism. Proceeding without plugins.",
                RuntimeWarning,
            )
    except (
        Exception
    ) as e:  # Catch any other unexpected errors during entry point discovery
        entry_points = []
        warnings.warn(
            f"An unexpected error occurred during plugin discovery for group '{EXPORTER_ENTRY_POINT_GROUP}': {e}. "
            f"Proceeding without plugins.",
            RuntimeWarning,
        )

    for entry_point in entry_points:
        try:
            exporter_class = entry_point.load()
            if not issubclass(exporter_class, BaseExporter):
                warnings.warn(
                    f"Plugin '{entry_point.name}' from '{entry_point.value}' does not inherit from BaseExporter. Skipping.",
                    RuntimeWarning,
                )
                continue

            # Exporter plugins should ideally be designed to be instantiated without arguments,
            # or the entry point itself should be a factory function that returns an instance.
            # For now, assuming direct instantiation of the loaded class.
            exporter_instance = exporter_class()
            register_exporter(
                exporter_instance, overwrite=True
            )  # Allow plugins to override built-ins or other plugins
            # print(f"Successfully loaded and registered exporter plugin: {entry_point.name}") # Optional: for verbose logging
        except Exception as e:
            warnings.warn(
                f"Failed to load or register exporter plugin '{entry_point.name}' from '{entry_point.value}'. Error: {e}",
                RuntimeWarning,
            )
    _PLUGINS_LOADED = True


# Automatically load plugins when the module is imported.
# This ensures that plugins are available as soon as the exporters module is used.
# Applications can call load_plugin_exporters(force_reload=True) if they need to refresh.
load_plugin_exporters()

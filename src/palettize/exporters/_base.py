"""Base classes and interfaces for Palettize exporters."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from palettize.core import Colormap, ScalingFunction


class BaseExporter(ABC):
    """
    Abstract Base Class for Palettize exporters.

    Each exporter plugin should inherit from this class and implement
    the `export` method and the `identifier` and `name` properties.
    """

    @property
    @abstractmethod
    def identifier(self) -> str:
        """A short, unique, machine-readable identifier for the format (e.g., "gdal_txt", "qgis_xml")."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """A human-readable name for the export format (e.g., "GDAL Color Relief Text", "QGIS Color Ramp XML")."""
        pass

    @property
    def default_file_extension(self) -> Optional[str]:
        """
        Optional. The default file extension for this format (e.g., "txt", "xml", "json").
        Return None if no typical extension or if output is not usually a file.
        """
        return None

    @abstractmethod
    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Exports the given colormap to the specific format as a string.

        Args:
            colormap: The Colormap object to export.
            scaler: The ScalingFunction to map data values to [0,1] for the colormap.
            domain_min: The minimum data value of the domain.
            domain_max: The maximum data value of the domain.
            options: A dictionary of format-specific options.
                     Exporters should define what options they accept.

        Returns:
            A string representation of the colormap in the target format.

        Raises:
            NotImplementedError: If the export method is not implemented by the subclass.
            ValueError: For invalid options or if colormap/scaler/domain are unsuitable.
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} (identifier='{self.identifier}', name='{self.name}')>"

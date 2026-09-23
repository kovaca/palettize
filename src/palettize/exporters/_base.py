"""Base classes and shared helpers for Palettize exporters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction, sample_positions

from ._options import Opt, OptionSpec

# Every exporter that emits a fixed number of samples shares this option.
NUM_COLORS_OPT = Opt(
    "num_colors",
    int,
    256,
    "Number of colors to sample from the colormap.",
    minimum=2,
)


class BaseExporter(ABC):
    """Abstract base class for Palettize exporters.

    Subclasses implement :meth:`export` and the :attr:`identifier` and
    :attr:`name` properties, and declare the options they accept in
    :attr:`options`. That declaration is the single source of truth for option
    coercion, validation, and the help tables rendered by ``palettize formats``.
    """

    #: Options this exporter accepts. Declared once; used for both coercion and help.
    options: ClassVar[OptionSpec] = OptionSpec()

    #: Whether output can depend on the data domain, either by embedding the
    #: min/max or by placing colors at data values. Exporters that emit a plain
    #: list of colors (CSS, GIMP, SVG, ...) have no data axis and say so here
    #: rather than silently ignoring the arguments they are handed. Some formats
    #: only use the domain under certain options, so this flag means "can",
    #: not "always".
    uses_domain: ClassVar[bool] = False

    #: Whether the scaling function repositions colors by default. This is the
    #: strong form of :attr:`uses_domain`: when ``True``, switching from a linear
    #: to a log scale is guaranteed to change the output. Formats that hand
    #: scaling off to the consuming application (Observable Plot, MapLibre) or
    #: that only emit a palette leave this ``False``.
    uses_scaler: ClassVar[bool] = False

    @property
    @abstractmethod
    def identifier(self) -> str:
        """Short, unique, machine-readable format id (e.g. ``"gdal"``)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable format name (e.g. ``"GDAL Color Relief Text"``)."""

    @property
    def default_file_extension(self) -> str | None:
        """Default file extension for this format, or ``None`` if not file-based."""
        return None

    @abstractmethod
    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        """Export ``colormap`` to this exporter's format.

        Args:
            colormap: The colormap to export.
            scaler: Maps data values into ``[0, 1]``. Ignored when
                :attr:`uses_domain` is ``False``.
            domain_min: Minimum data value. Ignored when :attr:`uses_domain` is ``False``.
            domain_max: Maximum data value. Ignored when :attr:`uses_domain` is ``False``.
            options: Format-specific options; see :attr:`options`.

        Returns:
            The formatted colormap as a string.

        Raises:
            ExporterOptionError: If an option is unknown, mistyped, or out of range.
            ValueError: If the colormap, scaler, or domain is unusable.
        """

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def resolve_options(self, options: Mapping[str, Any] | None) -> dict[str, Any]:
        """Coerce and validate ``options`` against this exporter's declaration."""
        return self.options.resolve(options)

    @staticmethod
    def validate_domain(domain_min: float, domain_max: float) -> None:
        """Ensure the data domain is a non-empty, increasing interval."""
        if domain_min >= domain_max:
            raise ValueError(
                f"domain_min must be less than domain_max. Got: [{domain_min}, {domain_max}]"
            )

    @staticmethod
    def sample_positions(n: int) -> list[float]:
        """``n`` evenly spaced colormap positions across ``[0, 1]``."""
        return sample_positions(n)

    @staticmethod
    def sample_data_values(n: int, domain_min: float, domain_max: float) -> list[float]:
        """``n`` evenly spaced data values across ``[domain_min, domain_max]``."""
        return [domain_min + t * (domain_max - domain_min) for t in sample_positions(n)]

    @staticmethod
    def sample_scaled(
        colormap: Colormap,
        scaler: ScalingFunction,
        n: int,
        domain_min: float,
        domain_max: float,
        output_format: str = "rgba_tuple",
    ) -> list[tuple[float, Any]]:
        """Sample ``n`` ``(data_value, color)`` pairs through ``scaler``.

        Used by domain-aware exporters so that a non-linear ``--scale`` shifts
        which color lands on which data value.
        """
        return [
            (value, colormap.apply_scaler(value, scaler, output_format=output_format))
            for value in BaseExporter.sample_data_values(n, domain_min, domain_max)
        ]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} (identifier={self.identifier!r}, name={self.name!r})>"

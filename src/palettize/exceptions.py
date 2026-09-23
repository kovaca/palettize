"""Custom exceptions for the Palettize package."""


class PalettizeError(Exception):
    """Base class for exceptions in this module."""

    pass


class InvalidColorError(PalettizeError):
    """Raised when an invalid color input is provided."""

    pass


class PresetNotFoundError(PalettizeError):
    """Raised when a preset is not found."""

    pass


class ColormapFileError(PalettizeError):
    """Raised when a saved colormap file is missing, malformed, or unsupported."""

    pass


class ExporterOptionError(PalettizeError, ValueError):
    """Raised when an exporter option is unknown, mistyped, or out of range.

    Subclasses :class:`ValueError` so existing callers that catch invalid-option
    errors keep working.
    """

    pass

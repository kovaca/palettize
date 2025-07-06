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

"""Core colormap generation logic for Palettize."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias, TypeVar, cast

from coloraide import Color, stop

from . import presets as preset_module
from .exceptions import ColormapFileError, InvalidColorError
from .scaling import ScalingFunction

# User-facing color representation
InputColor: TypeAlias = "tuple[float, ...] | str | dict[str, list[float]] | Color"
# Internal representation for colors after parsing
ParsedColorType: TypeAlias = Color

C = TypeVar("C", bound="Colormap")

#: Version of the on-disk colormap JSON schema written by :meth:`Colormap.save`.
SCHEMA_VERSION = 1

#: Decimal places kept for stop positions and cut bounds. Chained transforms
#: accumulate float noise (``1.0 - 0.8`` is not ``0.2``); rounding on construction
#: keeps equality, hashing, and serialization consistent. Twelve places is far
#: finer than any perceptible difference in a 0-1 colormap coordinate.
POSITION_PRECISION = 12

#: Output formats accepted by :meth:`Colormap.get_color`.
OUTPUT_FORMATS = (
    "hex",
    "rgb_tuple",
    "rgba_tuple",
    "rgb_float",
    "rgba_float",
    "hsl_tuple",
    "hsl_string",
    "oklch_string",
    "css_color",
)


def _is_byte_rgb(channels: tuple[float, ...]) -> bool:
    """True when RGB channels look like 0-255 rather than 0-1 floats."""
    return all(0 <= x <= 255 for x in channels) and any(x > 1 for x in channels)


def parse_input_color(color_input: InputColor, target_space: str = "srgb") -> ParsedColorType:
    """
    Parses various color input formats into a ColorAide Color object,
    optionally converting it to a target color space.
    """
    try:
        if isinstance(color_input, Color):
            # If already a ColorAide object, just ensure it's in the target space
            c = color_input
        elif isinstance(color_input, tuple):
            # Numeric tuples are assumed to be sRGB. RGB channels are 0-255 when
            # any of them is above 1; alpha stays 0-1 unless it is itself above 1.
            if len(color_input) == 3 and all(isinstance(x, (int, float)) for x in color_input):
                # Alpha must go through the constructor: assigning `c.alpha`
                # shadows ColorAide's alpha() method on the instance.
                if _is_byte_rgb(color_input):
                    c = Color("srgb", [x / 255.0 for x in color_input], alpha=1.0)
                else:
                    c = Color("srgb", list(color_input), alpha=1.0)
            elif len(color_input) == 4 and all(isinstance(x, (int, float)) for x in color_input):
                rgb = color_input[:3]
                # Scale RGB from the color channels alone. Alpha is 0-1 unless it
                # is itself above 1, so (128, 64, 32, 0.5) stays half-opaque.
                alpha = float(color_input[3])
                if alpha > 1:
                    alpha /= 255.0
                if _is_byte_rgb(rgb):
                    c = Color("srgb", [x / 255.0 for x in rgb], alpha=alpha)
                else:
                    c = Color("srgb", list(rgb), alpha=alpha)
            else:
                c = Color(color_input)  # type: ignore[arg-type]
        elif isinstance(color_input, (str, dict)):
            c = Color(color_input)
        else:
            raise InvalidColorError(f"Unsupported color input type: {type(color_input)}")

        if c.space() != target_space:
            return c.convert(target_space)
        return c
    except InvalidColorError:
        raise
    except Exception as e:
        # ColorAide raises a variety of error types for malformed input.
        raise InvalidColorError(f"Failed to parse color '{color_input}': {e}") from e


def format_color(
    color: ParsedColorType,
    output_format: str = "hex",
    output_space: str = "srgb",
) -> str | tuple[int, ...] | tuple[float, ...]:
    """Render a ColorAide color in one of Palettize's output formats.

    Args:
        color: The color to format.
        output_format: One of :data:`OUTPUT_FORMATS`.
        output_space: ``"srgb"`` (default) or ``"display-p3"``. Affects ``rgb_*``,
            ``rgba_*``, and ``css_color``. Hex is always sRGB.

    Returns:
        A string or numeric tuple, depending on ``output_format``.

    Raises:
        ValueError: If ``output_format`` is not recognised.
    """
    if output_format not in OUTPUT_FORMATS:
        raise ValueError(
            f"Unsupported output_format: {output_format}. Supported: {', '.join(OUTPUT_FORMATS)}"
        )

    srgb_color = color.convert("srgb")
    output_color = color.convert(output_space) if output_space != "srgb" else srgb_color

    if output_format == "hex":
        return srgb_color.to_string(hex=True, fit="clip")

    if output_format == "css_color":
        if output_space == "srgb":
            return srgb_color.to_string(hex=True, fit="clip")
        coords = output_color.coords(nans=False)
        alpha = output_color.alpha(nans=False)
        alpha = 1.0 if alpha is None else alpha
        body = f"{output_space} {coords[0]:.4f} {coords[1]:.4f} {coords[2]:.4f}"
        if abs(alpha - 1.0) < 0.001:
            return f"color({body})"
        return f"color({body} / {alpha:.4f})"

    if output_format in ("hsl_tuple", "hsl_string"):
        h, s, lightness = srgb_color.convert("hsl").coords(nans=False)
        if output_format == "hsl_tuple":
            # ColorAide gives h in 0-360 and s/l in 0-1; expose s/l as percentages.
            return (round(h, 1), round(s * 100, 1), round(lightness * 100, 1))
        return f"hsl({h:.0f}, {s * 100:.0f}%, {lightness * 100:.0f}%)"

    if output_format == "oklch_string":
        lightness, chroma, hue = color.convert("oklch").coords(nans=False)
        return f"oklch({lightness * 100:.1f}% {chroma:.3f} {hue:.1f})"

    coords = output_color.coords(nans=False)
    alpha = output_color.alpha(nans=False)
    alpha = 1.0 if alpha is None else alpha

    r_f, g_f, b_f = (max(0.0, min(1.0, v)) for v in coords[:3])
    a_f = max(0.0, min(1.0, alpha))

    if output_format == "rgb_float":
        return (r_f, g_f, b_f)
    if output_format == "rgba_float":
        return (r_f, g_f, b_f, a_f)

    r, g, b, a = (round(v * 255) for v in (r_f, g_f, b_f, a_f))
    if output_format == "rgb_tuple":
        return (r, g, b)
    return (r, g, b, a)


def _at_position(source: ColorStop, position: float) -> ColorStop:
    """Copy a stop to a rounded position, reusing the already-parsed color."""
    rounded = round(position, POSITION_PRECISION)
    if source.position == rounded:
        return source
    clone = ColorStop(source.color, rounded)
    clone._parsed_color_obj = source._parsed_color_obj
    return clone


def _is_position(value: Any) -> bool:
    """Whether a preset tuple's second element is a stop position rather than a color."""
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def _colors_match(a: ParsedColorType, b: ParsedColorType, tol: float = 1e-9) -> bool:
    """True when two same-space colors agree on every coordinate and alpha."""
    a_alpha = a.alpha(nans=False)
    b_alpha = b.alpha(nans=False)
    if (
        abs((a_alpha if a_alpha is not None else 1.0) - (b_alpha if b_alpha is not None else 1.0))
        > tol
    ):
        return False
    return all(
        abs(x - y) <= tol for x, y in zip(a.coords(nans=False), b.coords(nans=False), strict=True)
    )


@dataclass
class ColorStop:
    """A single color stop in a colormap.

    Args:
        color: Any supported color input (hex, CSS name, tuple, dict, ColorAide color).
        position: Position in ``[0, 1]``. ``None`` means "assign automatically",
            which :class:`Colormap` resolves by spacing stops evenly.
    """

    color: InputColor
    position: float | None = None
    _parsed_color_obj: ParsedColorType | None = field(
        default=None, repr=False, init=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.position is not None and not (0.0 <= self.position <= 1.0):
            raise ValueError("ColorStop position must be between 0.0 and 1.0")
        try:
            # Stops always store sRGB internally; interpolation converts as needed.
            self._parsed_color_obj = parse_input_color(self.color, target_space="srgb")
        except InvalidColorError as e:
            raise ValueError(
                f"Invalid color for stop (color={self.color}, position={self.position}): {e}"
            ) from e

    @property
    def parsed_color(self) -> ParsedColorType:
        """The stop's color as a ColorAide object in sRGB."""
        if self._parsed_color_obj is None:
            self._parsed_color_obj = parse_input_color(self.color, target_space="srgb")
        return self._parsed_color_obj

    def to_hex(self) -> str:
        """The stop's color as a hex string, including alpha when not opaque."""
        return self.parsed_color.to_string(hex=True, fit="clip")

    def to_serializable(self) -> str:
        """The stop's color as a lossless, re-parseable string.

        Prefers hex for readability, falling back to an explicit ``color(srgb ...)``
        form when hex would lose precision (fractional alpha, out-of-gamut coords).
        """
        color = self.parsed_color
        hex_str = self.to_hex()
        if _colors_match(Color(hex_str).convert("srgb"), color):
            return hex_str
        return color.to_string(color=True, precision=8, fit=False)


class Colormap:
    """A colormap defined by a series of color stops.

    Sampling is always expressed in ``[0, 1]`` over the *visible* range of the
    map. When ``cut_start``/``cut_end`` narrow that range, position ``0`` maps to
    ``cut_start`` and position ``1`` to ``cut_end`` of the underlying stops.

    Transform methods (:meth:`reversed`, :meth:`resampled`, :meth:`quantized`,
    :meth:`cut`, :meth:`blend`, :meth:`concat`) never mutate the receiver; each
    returns a new ``Colormap``.
    """

    def __init__(
        self,
        stops: list[ColorStop],
        name: str | None = None,
        interpolation_space: str = "oklch",
        cut_start: float = 0.0,
        cut_end: float = 1.0,
    ) -> None:
        if not stops:
            raise ValueError("Colormap must have at least one color stop.")

        if not (0.0 <= cut_start <= 1.0 and 0.0 <= cut_end <= 1.0 and cut_start <= cut_end):
            raise ValueError(
                "Invalid cut range: cut_start and cut_end must be between 0.0 and 1.0, "
                "and cut_start <= cut_end."
            )

        self.name: str | None = name
        self.interpolation_space: str = interpolation_space
        self.stops: list[ColorStop] = self._normalize_and_sort_stops(stops)
        self.cut_start: float = round(cut_start, POSITION_PRECISION)
        self.cut_end: float = round(cut_end, POSITION_PRECISION)
        self._interpolator: Any | None = None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_list(
        cls: type[C],
        colors: list[InputColor],
        name: str | None = None,
        interpolation_space: str = "oklch",
        cut_start: float = 0.0,
        cut_end: float = 1.0,
    ) -> C:
        """Build a colormap from evenly spaced colors."""
        if not colors:
            raise ValueError("Color list cannot be empty for Colormap.from_list().")
        return cls(
            stops=[ColorStop(color=c) for c in colors],
            name=name,
            interpolation_space=interpolation_space,
            cut_start=cut_start,
            cut_end=cut_end,
        )

    @classmethod
    def from_preset(
        cls: type[C],
        preset_name: str,
        interpolation_space: str = "oklch",
        cut_start: float = 0.0,
        cut_end: float = 1.0,
    ) -> C:
        """Build a colormap from a named preset (built-in or from ``cmap``)."""
        preset_data = preset_module.load_preset_data(preset_name)
        stops: list[ColorStop] = []
        for item in preset_data:
            # A preset entry is either a bare color or a (color, position) pair.
            # A bare 3- or 4-component numeric tuple is a color, not a pair.
            if isinstance(item, tuple) and len(item) == 2 and _is_position(item[1]):
                color, position = cast("tuple[InputColor, float | None]", item)
                stops.append(ColorStop(color=color, position=position))
            elif isinstance(item, (str, tuple, dict, Color)):
                stops.append(ColorStop(color=cast("InputColor", item), position=None))
            else:
                raise ValueError(f"Invalid item format in preset '{preset_name}': {item}")
        return cls(
            stops=stops,
            name=preset_name,
            interpolation_space=interpolation_space,
            cut_start=cut_start,
            cut_end=cut_end,
        )

    def _normalize_and_sort_stops(self, stops: list[ColorStop]) -> list[ColorStop]:
        for i, s_data in enumerate(stops):
            if not isinstance(s_data, ColorStop):
                raise TypeError(
                    f"Stop at index {i} is not a ColorStop instance. Received {type(s_data)}."
                )

        num_stops = len(stops)
        has_any_position = any(s.position is not None for s in stops)
        all_have_positions = all(s.position is not None for s in stops)

        if all_have_positions:
            ordered = sorted(stops, key=lambda s: s.position)  # type: ignore[arg-type,return-value]
            return [_at_position(s, s.position) for s in ordered]  # type: ignore[arg-type]
        if has_any_position:
            raise ValueError(
                "Mixed color stop position specification (some with, some without) is not "
                "supported. Please provide positions for all stops or for no stops."
            )
        if num_stops == 1:
            return [_at_position(stops[0], 0.0)]
        return [_at_position(s, i / (num_stops - 1)) for i, s in enumerate(stops)]

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def _get_interpolator(self) -> Any:
        """Build (and cache) a ColorAide interpolator over this map's stops.

        ColorAide handles positioned stops, cylindrical hue paths and NaN
        (powerless) hues correctly, which hand-rolled per-segment mixing does not.
        """
        if self._interpolator is None:
            self._interpolator = Color.interpolate(
                [
                    stop(
                        s.parsed_color.convert(self.interpolation_space),
                        s.position if s.position is not None else 0.0,
                    )
                    for s in self.stops
                ],
                space=self.interpolation_space,
            )
        return self._interpolator

    def get_color_object(self, position: float) -> ParsedColorType:
        """Return the interpolated color at ``position`` as a ColorAide object.

        ``position`` is relative to the cut segment and is clamped to ``[0, 1]``.
        """
        position = max(0.0, min(1.0, position))
        actual_position = self.cut_start + position * (self.cut_end - self.cut_start)
        actual_position = max(0.0, min(1.0, actual_position))

        if len(self.stops) == 1:
            return self.stops[0].parsed_color.convert(self.interpolation_space)

        interpolated: ParsedColorType = self._get_interpolator()(actual_position)
        return interpolated

    def get_color(
        self, position: float, output_format: str = "hex", output_space: str = "srgb"
    ) -> str | tuple[int, ...] | tuple[float, ...]:
        """Return the interpolated color at ``position``, formatted for output.

        Args:
            position: Position in the colormap (0.0 to 1.0).
            output_format: One of :data:`OUTPUT_FORMATS`.
            output_space: ``"srgb"`` (default) or ``"display-p3"``.
        """
        return format_color(self.get_color_object(position), output_format, output_space)

    def colors(
        self,
        n: int,
        output_format: str = "hex",
        output_space: str = "srgb",
    ) -> list[str | tuple[int, ...] | tuple[float, ...]]:
        """Sample ``n`` evenly spaced colors across the colormap.

        For ``n == 1`` the midpoint is returned; otherwise samples span the full
        range inclusive of both endpoints.
        """
        if n < 1:
            raise ValueError("n must be at least 1.")
        return [
            format_color(self.get_color_object(t), output_format, output_space)
            for t in sample_positions(n)
        ]

    def hex_colors(self, n: int) -> list[str]:
        """Sample ``n`` evenly spaced colors as ``#rrggbb`` strings."""
        return cast("list[str]", self.colors(n, "hex"))

    def rgb_colors(self, n: int) -> list[tuple[int, int, int]]:
        """Sample ``n`` evenly spaced colors as 0-255 ``(r, g, b)`` tuples."""
        return cast("list[tuple[int, int, int]]", self.colors(n, "rgb_tuple"))

    def rgba_colors(self, n: int) -> list[tuple[int, int, int, int]]:
        """Sample ``n`` evenly spaced colors as 0-255 ``(r, g, b, a)`` tuples."""
        return cast("list[tuple[int, int, int, int]]", self.colors(n, "rgba_tuple"))

    def hsl_colors(self, n: int) -> list[tuple[float, float, float]]:
        """Sample ``n`` evenly spaced colors as ``(h, s%, l%)`` tuples."""
        return cast("list[tuple[float, float, float]]", self.colors(n, "hsl_tuple"))

    def apply_scaler(
        self,
        data_value: float,
        scaler: ScalingFunction,
        output_format: str = "hex",
        output_space: str = "srgb",
    ) -> str | tuple[int, ...] | tuple[float, ...]:
        """Map a data value through ``scaler`` and return the resulting color."""
        normalized_position = scaler(data_value)
        return self.get_color(
            max(0.0, min(1.0, normalized_position)),
            output_format=output_format,
            output_space=output_space,
        )

    # ------------------------------------------------------------------
    # Transforms (all return new instances)
    # ------------------------------------------------------------------

    def _derive(self, **overrides: Any) -> Colormap:
        """Build a new Colormap from this one with selected fields replaced."""
        params: dict[str, Any] = {
            "stops": list(self.stops),
            "name": self.name,
            "interpolation_space": self.interpolation_space,
            "cut_start": self.cut_start,
            "cut_end": self.cut_end,
        }
        params.update(overrides)
        return Colormap(**params)

    def renamed(self, name: str | None) -> Colormap:
        """Return a copy with a different name."""
        return self._derive(name=name)

    def reversed(self) -> Colormap:
        """Return a colormap sampling this one back-to-front.

        Follows the matplotlib convention of toggling an ``_r`` name suffix.
        """
        mirrored = [
            ColorStop(s.color, position=1.0 - (s.position or 0.0)) for s in reversed(self.stops)
        ]
        name = self.name
        if name:
            name = name[:-2] if name.endswith("_r") else f"{name}_r"
        # Mirroring the cut window keeps reversed(t) == original(1 - t).
        return Colormap(
            stops=mirrored,
            name=name,
            interpolation_space=self.interpolation_space,
            cut_start=1.0 - self.cut_end,
            cut_end=1.0 - self.cut_start,
        )

    def cut(self, start: float, end: float) -> Colormap:
        """Return the sub-segment of this colormap between ``start`` and ``end``.

        Coordinates are relative to the current visible range, so cuts compose:
        ``cmap.cut(0.5, 1.0).cut(0.0, 0.5)`` is the third quarter of ``cmap``.
        """
        if not (0.0 <= start <= 1.0 and 0.0 <= end <= 1.0 and start <= end):
            raise ValueError(
                "Invalid cut range: start and end must be between 0.0 and 1.0, and start <= end."
            )
        span = self.cut_end - self.cut_start
        return self._derive(
            cut_start=self.cut_start + start * span,
            cut_end=self.cut_start + end * span,
        )

    def resampled(self, n: int) -> Colormap:
        """Return a colormap of ``n`` evenly spaced stops sampled from this one.

        Any active cut is baked into the result, so the new map spans ``[0, 1]``.
        """
        if n < 2:
            raise ValueError("resampled() requires n >= 2.")
        return Colormap(
            stops=[
                ColorStop(self.get_color_object(t).convert("srgb"), position=t)
                for t in sample_positions(n)
            ],
            name=self.name,
            interpolation_space=self.interpolation_space,
        )

    def quantized(self, n: int) -> Colormap:
        """Return a colormap of ``n`` hard-edged bands of constant color.

        Each band takes the color at its own midpoint, producing a stepped ramp
        rather than a continuous gradient.
        """
        if n < 1:
            raise ValueError("quantized() requires n >= 1.")
        stops: list[ColorStop] = []
        for i in range(n):
            band_color = self.get_color_object((i + 0.5) / n).convert("srgb")
            # Two stops per band, sharing a color, create a discontinuity at the edge.
            stops.append(ColorStop(band_color, position=i / n))
            stops.append(ColorStop(band_color, position=(i + 1) / n))
        return Colormap(
            stops=stops,
            name=self.name,
            interpolation_space=self.interpolation_space,
        )

    def blend(self, other: Colormap, t: float = 0.5, n: int = 256) -> Colormap:
        """Return a colormap that is a ``t``-weighted mix of this one and ``other``.

        Both maps are sampled at ``n`` positions and mixed pairwise, so blending
        works regardless of how the two maps' stops line up.
        """
        if not (0.0 <= t <= 1.0):
            raise ValueError("blend() requires t between 0.0 and 1.0.")
        if n < 2:
            raise ValueError("blend() requires n >= 2.")
        space = self.interpolation_space
        stops = [
            ColorStop(
                self.get_color_object(p)
                .convert(space)
                .mix(other.get_color_object(p).convert(space), t, space=space, in_place=False)
                .convert("srgb"),
                position=p,
            )
            for p in sample_positions(n)
        ]
        return Colormap(stops=stops, name=self.name, interpolation_space=space)

    def concat(self, other: Colormap, at: float = 0.5, n: int = 128) -> Colormap:
        """Return this colormap followed by ``other``, joined at ``at``.

        This map is squeezed into ``[0, at]`` and ``other`` into ``[at, 1]``.
        """
        if not (0.0 < at < 1.0):
            raise ValueError("concat() requires at strictly between 0.0 and 1.0.")
        if n < 2:
            raise ValueError("concat() requires n >= 2.")
        stops: list[ColorStop] = []
        for p in sample_positions(n):
            stops.append(ColorStop(self.get_color_object(p).convert("srgb"), position=p * at))
        for p in sample_positions(n):
            stops.append(
                ColorStop(
                    other.get_color_object(p).convert("srgb"),
                    position=at + p * (1.0 - at),
                )
            )
        name = None
        if self.name and other.name:
            name = f"{self.name}+{other.name}"
        return Colormap(stops=stops, name=name, interpolation_space=self.interpolation_space)

    def __add__(self, other: Colormap) -> Colormap:
        if not isinstance(other, Colormap):
            return NotImplemented
        return self.concat(other)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict matching the Palettize colormap schema."""
        # Positions are already rounded to POSITION_PRECISION on construction,
        # so a saved file reloads to a colormap that compares equal to this one.
        return {
            "palettize": SCHEMA_VERSION,
            "name": self.name,
            "interpolation_space": self.interpolation_space,
            "cut": [self.cut_start, self.cut_end],
            "stops": [{"color": s.to_serializable(), "position": s.position} for s in self.stops],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Colormap:
        """Rebuild a colormap from :meth:`to_dict` output.

        Raises:
            ColormapFileError: If the payload is malformed or written by a newer
                , incompatible schema version.
        """
        if not isinstance(data, dict):
            raise ColormapFileError("Colormap data must be a JSON object.")

        schema = data.get("palettize")
        if schema is None:
            raise ColormapFileError(
                "Not a Palettize colormap file (missing 'palettize' schema key)."
            )
        # `bool` is an `int`, so JSON `true` must be rejected before the comparison.
        if type(schema) is not int or schema != SCHEMA_VERSION:
            hint = " Upgrade Palettize." if type(schema) is int and schema > SCHEMA_VERSION else ""
            raise ColormapFileError(
                f"Unsupported colormap schema version {schema!r}; this build of "
                f"Palettize understands version {SCHEMA_VERSION}.{hint}"
            )

        raw_stops = data.get("stops")
        if not isinstance(raw_stops, list) or not raw_stops:
            raise ColormapFileError("Colormap file must contain a non-empty 'stops' list.")

        stops: list[ColorStop] = []
        for i, raw in enumerate(raw_stops):
            if isinstance(raw, str):
                color, position = raw, None
            elif isinstance(raw, dict) and "color" in raw:
                color, position = raw["color"], raw.get("position")
            else:
                raise ColormapFileError(
                    f"Stop {i} must be a color string or an object with a 'color' key."
                )
            try:
                stops.append(ColorStop(color, position))
            except ValueError as e:
                raise ColormapFileError(f"Stop {i} is invalid: {e}") from e

        cut = data.get("cut", [0.0, 1.0])
        if not (isinstance(cut, (list, tuple)) and len(cut) == 2):
            raise ColormapFileError("'cut' must be a two-element [start, end] list.")

        try:
            return cls(
                stops=stops,
                name=data.get("name"),
                interpolation_space=data.get("interpolation_space", "oklch"),
                cut_start=float(cut[0]),
                cut_end=float(cut[1]),
            )
        except (TypeError, ValueError) as e:
            raise ColormapFileError(f"Invalid colormap definition: {e}") from e

    def save(self, path: str | Path, indent: int = 2) -> Path:
        """Write this colormap to a JSON file and return the path written."""
        target = Path(path)
        if target.parent != Path():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=indent) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> Colormap:
        """Read a colormap from a JSON file written by :meth:`save`."""
        source = Path(path)
        try:
            raw = source.read_text(encoding="utf-8")
        except OSError as e:
            raise ColormapFileError(f"Could not read colormap file '{source}': {e}") from e
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ColormapFileError(f"'{source}' is not valid JSON: {e}") from e
        return cls.from_dict(data)

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    def __call__(self, position: float) -> str:
        """Shorthand for ``get_color(position)``; returns a hex string."""
        return self.get_color(position)  # type: ignore[return-value]

    def __len__(self) -> int:
        return len(self.stops)

    def __iter__(self) -> Iterator[ColorStop]:
        return iter(self.stops)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Colormap):
            return NotImplemented
        return (
            self.name == other.name
            and self.interpolation_space == other.interpolation_space
            and (self.cut_start, self.cut_end) == (other.cut_start, other.cut_end)
            and [(s.to_hex(), s.position) for s in self.stops]
            == [(s.to_hex(), s.position) for s in other.stops]
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.name,
                self.interpolation_space,
                self.cut_start,
                self.cut_end,
                tuple((s.to_hex(), s.position) for s in self.stops),
            )
        )

    def __repr__(self) -> str:
        cut = ""
        if (self.cut_start, self.cut_end) != (0.0, 1.0):
            cut = f", cut=({self.cut_start}, {self.cut_end})"
        return (
            f"Colormap(name={self.name!r}, space={self.interpolation_space!r}, "
            f"stops={len(self.stops)}{cut})"
        )


def sample_positions(n: int) -> list[float]:
    """Return ``n`` evenly spaced positions across ``[0, 1]``.

    A single sample is taken at the midpoint; otherwise both endpoints are included.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    if n == 1:
        return [0.5]
    return [i / (n - 1) for i in range(n)]

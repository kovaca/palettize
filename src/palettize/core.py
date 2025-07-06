"""Core colormap generation logic for Palettize."""

from typing import List, Optional, Union, Tuple, TypeAlias, TypeVar, Type, Dict
from dataclasses import dataclass, field
from .exceptions import InvalidColorError
from . import presets as preset_module
from .scaling import ScalingFunction  # Import for apply_scaler

from coloraide import Color

# User-facing color representation
InputColor: TypeAlias = Union[Tuple[float, ...], str, Dict[str, List[float]], Color]
# Internal representation for colors after parsing
ParsedColorType: TypeAlias = Color

# Generic type for Colormap class methods
C = TypeVar("C", bound="Colormap")


def parse_input_color(
    color_input: InputColor, target_space: str = "srgb"
) -> ParsedColorType:
    """
    Parses various color input formats into a ColorAide Color object,
    optionally converting it to a target color space.
    """
    try:
        if isinstance(color_input, Color):
            # If already a ColorAide object, just ensure it's in the target space
            c = color_input
        elif isinstance(color_input, tuple):
            # Handle common numerical tuple cases (RGB 0-255 or 0-1)
            # Assuming sRGB for such tuples if not otherwise specified by ColorAide itself
            if len(color_input) == 3 and all(
                isinstance(x, (int, float)) for x in color_input
            ):
                if all(
                    0 <= x <= 255 for x in color_input
                ):  # Check if all are in 0-255 range
                    c = Color("srgb", [x / 255.0 for x in color_input[:3]])
                    c.alpha = 1.0
                else:  # Assume 0-1 range if not all in 0-255
                    c = Color("srgb", list(color_input[:3]))
                    c.alpha = 1.0  # Default alpha
            elif len(color_input) == 4 and all(
                isinstance(x, (int, float)) for x in color_input
            ):
                if all(0 <= x <= 255 for x in color_input):  # RGBA 0-255
                    c = Color(
                        "srgb",
                        [x / 255.0 for x in color_input[:3]],
                        alpha=color_input[3] / 255.0,
                    )
                else:  # RGBA 0-1
                    c = Color(
                        "srgb", list(color_input[:3]), alpha=float(color_input[3])
                    )
            else:
                # Let ColorAide try to parse other tuple structures if any
                c = Color(color_input)  # type: ignore
        elif isinstance(color_input, str):
            c = Color(color_input)
        elif isinstance(color_input, dict):
            c = Color(color_input)
        else:
            raise InvalidColorError(
                f"Unsupported color input type: {type(color_input)}"
            )

        # Convert to target space if different
        if c.space() != target_space:
            return c.convert(target_space)
        return c
    except Exception as e:
        # Catching generic Exception as ColorAide can raise various errors
        raise InvalidColorError(f"Failed to parse color '{color_input}': {e}") from e


@dataclass
class ColorStop:
    """
    Represents a single color stop in a colormap.
    """

    color: InputColor
    position: Optional[float] = None
    _parsed_color_obj: Optional[ParsedColorType] = field(
        default=None, repr=False, init=False
    )

    def __post_init__(self):
        if self.position is not None and not (0.0 <= self.position <= 1.0):
            raise ValueError("ColorStop position must be between 0.0 and 1.0")
        try:
            # Default internal parsing to sRGB for consistent storage within ColorStop
            self._parsed_color_obj = parse_input_color(self.color, target_space="srgb")
        except InvalidColorError as e:
            raise ValueError(
                f"Invalid color for stop (color={self.color}, position={self.position}): {e}"
            ) from e

    @property
    def parsed_color(self) -> ParsedColorType:
        """Returns the parsed ColorAide.Color object, ensuring it's initialized."""
        if self._parsed_color_obj is None:
            # This fallback should ideally not be hit if __post_init__ runs correctly.
            self._parsed_color_obj = parse_input_color(self.color, target_space="srgb")
        return self._parsed_color_obj


class Colormap:
    """
    Represents a colormap, defined by a series of color stops.
    The `interpolation_space` attribute defines the space for `get_color_object`.
    The `cut_start` and `cut_end` attributes define the segment of the colormap to use.
    """

    def __init__(
        self,
        stops: List[ColorStop],
        name: Optional[str] = None,
        interpolation_space: str = "oklch",
        cut_start: float = 0.0,
        cut_end: float = 1.0,
    ):
        if not stops:
            raise ValueError("Colormap must have at least one color stop.")

        if not (
            0.0 <= cut_start <= 1.0 and 0.0 <= cut_end <= 1.0 and cut_start <= cut_end
        ):
            raise ValueError(
                "Invalid cut range: cut_start and cut_end must be between 0.0 and 1.0, and cut_start <= cut_end."
            )

        self.name: Optional[str] = name
        self.interpolation_space: str = interpolation_space
        self.stops: List[ColorStop] = self._normalize_and_sort_stops(stops)
        self.cut_start: float = cut_start
        self.cut_end: float = cut_end

    @classmethod
    def from_list(
        cls: Type[C],
        colors: List[InputColor],
        name: Optional[str] = None,
        interpolation_space: str = "oklch",
        cut_start: float = 0.0,
        cut_end: float = 1.0,
    ) -> C:
        if not colors:
            raise ValueError("Color list cannot be empty for Colormap.from_list().")
        stops = [ColorStop(color=c) for c in colors]
        return cls(
            stops=stops,
            name=name,
            interpolation_space=interpolation_space,
            cut_start=cut_start,
            cut_end=cut_end,
        )

    @classmethod
    def from_preset(
        cls: Type[C],
        preset_name: str,
        interpolation_space: str = "oklch",
        cut_start: float = 0.0,
        cut_end: float = 1.0,
    ) -> C:
        preset_data = preset_module.load_preset_data(preset_name)
        stops: List[ColorStop] = []
        for item in preset_data:
            if isinstance(item, tuple) and len(item) == 2:
                color_val, pos_val = item
                stops.append(ColorStop(color=color_val, position=pos_val))  # type: ignore
            elif isinstance(item, (str, tuple, dict, Color)):
                stops.append(ColorStop(color=item, position=None))
            else:
                raise ValueError(
                    f"Invalid item format in preset '{preset_name}': {item}"
                )
        return cls(
            stops=stops,
            name=preset_name,
            interpolation_space=interpolation_space,
            cut_start=cut_start,
            cut_end=cut_end,
        )

    def _normalize_and_sort_stops(self, stops: List[ColorStop]) -> List[ColorStop]:
        processed_stops: List[ColorStop] = []
        for i, s_data in enumerate(stops):
            if isinstance(s_data, ColorStop):
                processed_stops.append(s_data)
            else:
                raise TypeError(
                    f"Stop at index {i} is not a ColorStop instance. Received {type(s_data)}."
                )

        num_stops = len(processed_stops)
        if num_stops == 0:
            return []

        has_any_position = any(s.position is not None for s in processed_stops)
        all_have_positions = all(s.position is not None for s in processed_stops)

        final_stops: List[ColorStop]
        if all_have_positions:
            # Ensure all positions are not None before sorting for type checker
            valid_stops = [s for s in processed_stops if s.position is not None]
            final_stops = sorted(valid_stops, key=lambda s: s.position)  # type: ignore [arg-type, return-value]
        elif not has_any_position:
            if num_stops == 1:
                s = processed_stops[0]
                final_stops = [ColorStop(s.color, position=0.0)]
            else:
                final_stops = [
                    ColorStop(s.color, position=i / (num_stops - 1))
                    for i, s in enumerate(processed_stops)
                ]
        else:
            raise ValueError(
                "Mixed color stop position specification (some with, some without) is not yet supported. "
                "Please provide positions for all stops or for no stops."
            )

        for i in range(len(final_stops) - 1):
            pos_current = final_stops[i].position
            pos_next = final_stops[i + 1].position
            assert (
                pos_current is not None and pos_next is not None
            )  # Should be true due to logic above
            if pos_current > pos_next:
                raise ValueError(
                    "ColorStop positions must be non-decreasing after sorting."
                )
        return final_stops

    def get_color_object(self, position: float) -> ParsedColorType:
        """Gets the interpolated color as a ColorAide.Color object.
        The input position is relative to the cut segment [0,1] of the colormap.
        """
        if not (0.0 <= position <= 1.0):
            # Allow extrapolation by not clamping, but this position is for the *cut* segment.
            # The actual lookup position will be scaled by cut_start and cut_end.
            # Clamping here would make it impossible to get colors at the very edges if position is slightly off.
            # Position is clamped to [0,1] before scaling if it's outside this range to prevent inverse scaling issues.
            position = max(0.0, min(1.0, position))
            # raise ValueError("Position must be between 0.0 and 1.0")

        # Scale the position to the actual segment of the underlying colormap
        # Example: if cut is [0.2, 0.8] and position is 0.5 (midpoint of cut segment),
        # actual_position = 0.2 + 0.5 * (0.8 - 0.2) = 0.2 + 0.5 * 0.6 = 0.2 + 0.3 = 0.5
        # If position is 0 (start of cut segment), actual_position = self.cut_start
        # If position is 1 (end of cut segment), actual_position = self.cut_end
        actual_position = self.cut_start + position * (self.cut_end - self.cut_start)
        # Ensure actual_position is also clamped, e.g. if cut_start=cut_end
        actual_position = max(0.0, min(1.0, actual_position))

        if not self.stops:
            raise RuntimeError("Colormap has no stops.")

        if len(self.stops) == 1:
            return self.stops[0].parsed_color.convert(self.interpolation_space)

        # Ensure positions are asserted as non-None for type checker after _normalize_and_sort_stops
        first_stop_pos = self.stops[0].position
        last_stop_pos = self.stops[-1].position
        assert first_stop_pos is not None, (
            "First stop position is None after normalization"
        )
        assert last_stop_pos is not None, (
            "Last stop position is None after normalization"
        )

        if actual_position <= first_stop_pos:
            return self.stops[0].parsed_color.convert(self.interpolation_space)
        if actual_position >= last_stop_pos:
            return self.stops[-1].parsed_color.convert(self.interpolation_space)

        s1: ColorStop = self.stops[0]  # Initialize for type checker
        s2: ColorStop = self.stops[1]  # Initialize for type checker
        for i in range(len(self.stops) - 1):
            current_stop = self.stops[i]
            next_stop = self.stops[i + 1]
            # Positions here are guaranteed non-None from _normalize_and_sort_stops logic for multiple stops
            if current_stop.position <= actual_position < next_stop.position:  # type: ignore
                s1 = current_stop
                s2 = next_stop
                break
        else:  # Loop finished without break, means position might be == last_stop_pos
            if actual_position == last_stop_pos:
                return self.stops[-1].parsed_color.convert(self.interpolation_space)
            # This path should ideally not be hit if boundary checks are correct.
            # Fallback or raise error, for now, assume previous checks cover this.
            s1 = self.stops[-2]  # Default to last segment if something went wrong
            s2 = self.stops[-1]

        s1_pos = s1.position
        s2_pos = s2.position
        assert s1_pos is not None and s2_pos is not None  # Should be true

        if s1_pos == s2_pos:  # Avoid division by zero if stops are at the same position
            return s1.parsed_color.convert(self.interpolation_space)

        # Interpolate based on actual_position within the original stop positions
        t = (actual_position - s1_pos) / (s2_pos - s1_pos)

        color1 = s1.parsed_color.convert(self.interpolation_space)
        color2 = s2.parsed_color.convert(self.interpolation_space)

        interpolated_color = color1.mix(
            color2, t, space=self.interpolation_space, in_place=False
        )

        return interpolated_color

    def get_color(
        self, position: float, output_format: str = "hex"
    ) -> Union[str, Tuple[int, ...]]:
        """Gets the interpolated color, formatted as string or tuple."""
        color_obj = self.get_color_object(position)
        srgb_color = color_obj.convert(
            "srgb"
        )  # Convert to sRGB for standard output formats

        if output_format == "hex":
            return srgb_color.to_string(hex=True, fit="clip")

        coords_0_1 = srgb_color.coords(nans=False)
        alpha_0_1 = srgb_color.alpha(nans=False)
        if alpha_0_1 is None:
            alpha_0_1 = 1.0  # Handle cases where alpha might be None

        r = int(max(0, min(255, coords_0_1[0] * 255)))
        g = int(max(0, min(255, coords_0_1[1] * 255)))
        b = int(max(0, min(255, coords_0_1[2] * 255)))
        a = int(max(0, min(255, alpha_0_1 * 255)))

        if output_format == "rgb_tuple":
            return (r, g, b)
        elif output_format == "rgba_tuple":
            return (r, g, b, a)
        else:
            raise ValueError(
                f"Unsupported output_format: {output_format}. Supported: hex, rgb_tuple, rgba_tuple"
            )

    def __repr__(self) -> str:
        return f"Colormap(name='{self.name}', interpolation_space='{self.interpolation_space}', stops={self.stops}, cut=({self.cut_start},{self.cut_end}))"

    def apply_scaler(
        self, data_value: float, scaler: ScalingFunction, output_format: str = "hex"
    ) -> Union[str, Tuple[int, ...]]:
        """
        Applies a scaling function to the data_value to get a normalized position,
        then retrieves the color from the colormap in the specified output_format.
        """
        normalized_position = scaler(data_value)
        clamped_normalized_position = max(0.0, min(1.0, normalized_position))
        return self.get_color(clamped_normalized_position, output_format=output_format)

    # Further methods for interpolation, preset loading etc. will be added.

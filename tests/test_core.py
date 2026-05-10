"""Tests for palettize.core module."""

import pytest
from coloraide import Color

from palettize.core import Colormap, ColorStop, parse_input_color
from palettize.exceptions import InvalidColorError
from palettize.scaling import get_linear_scaler


class TestParseInputColor:
    """Tests for parse_input_color function."""

    def test_hex_string(self):
        """Test parsing hex color strings."""
        color = parse_input_color("#ff0000")
        assert color.space() == "srgb"
        coords = color.coords(nans=False)
        assert abs(coords[0] - 1.0) < 0.01
        assert abs(coords[1] - 0.0) < 0.01
        assert abs(coords[2] - 0.0) < 0.01

    def test_named_color(self):
        """Test parsing named colors."""
        color = parse_input_color("red")
        assert color.space() == "srgb"
        coords = color.coords(nans=False)
        assert abs(coords[0] - 1.0) < 0.01

    def test_rgb_tuple_0_255(self):
        """Test parsing RGB tuple in 0-255 range."""
        color = parse_input_color((255, 0, 0))
        coords = color.coords(nans=False)
        assert abs(coords[0] - 1.0) < 0.01
        assert abs(coords[1] - 0.0) < 0.01
        assert abs(coords[2] - 0.0) < 0.01

    def test_rgba_tuple_0_255(self):
        """Test parsing RGBA tuple in 0-255 range."""
        color = parse_input_color((255, 128, 0, 128))
        coords = color.coords(nans=False)
        assert abs(coords[0] - 1.0) < 0.01
        assert abs(coords[1] - 0.5) < 0.01
        assert abs(coords[2] - 0.0) < 0.01
        assert abs(color.alpha() - 0.5) < 0.01

    def test_coloraide_object(self):
        """Test passing a ColorAide Color object."""
        input_color = Color("oklch", [0.7, 0.15, 30])
        result = parse_input_color(input_color, target_space="srgb")
        assert result.space() == "srgb"

    def test_target_space_conversion(self):
        """Test converting to different color space."""
        color = parse_input_color("#ff0000", target_space="oklch")
        assert color.space() == "oklch"

    def test_invalid_color_raises_error(self):
        """Test that invalid colors raise InvalidColorError."""
        with pytest.raises(InvalidColorError):
            parse_input_color("not_a_color_123")


class TestColorStop:
    """Tests for ColorStop dataclass."""

    def test_basic_creation(self):
        """Test creating a basic ColorStop."""
        stop = ColorStop(color="red", position=0.5)
        assert stop.position == 0.5
        assert stop.color == "red"
        assert stop._parsed_color_obj is not None

    def test_no_position(self):
        """Test ColorStop without position (will be normalized later)."""
        stop = ColorStop(color="#00ff00")
        assert stop.position is None

    def test_invalid_position_below_zero(self):
        """Test that position below 0 raises ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ColorStop(color="red", position=-0.1)

    def test_invalid_position_above_one(self):
        """Test that position above 1 raises ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ColorStop(color="red", position=1.5)

    def test_invalid_color_raises_value_error(self):
        """Test that invalid color raises ValueError."""
        with pytest.raises(ValueError, match="Invalid color"):
            ColorStop(color="not_a_valid_color")


class TestColormap:
    """Tests for Colormap class."""

    def test_basic_creation(self):
        """Test creating a basic Colormap."""
        stops = [ColorStop("red"), ColorStop("blue")]
        cmap = Colormap(stops, name="TestMap")
        assert cmap.name == "TestMap"
        assert len(cmap.stops) == 2

    def test_empty_stops_raises_error(self):
        """Test that empty stops list raises ValueError."""
        with pytest.raises(ValueError, match="at least one color stop"):
            Colormap([])

    def test_position_auto_normalization(self):
        """Test that positions are auto-normalized when not specified."""
        stops = [ColorStop("red"), ColorStop("green"), ColorStop("blue")]
        cmap = Colormap(stops)
        assert cmap.stops[0].position == 0.0
        assert cmap.stops[1].position == 0.5
        assert cmap.stops[2].position == 1.0

    def test_single_stop(self):
        """Test colormap with single stop."""
        stops = [ColorStop("red")]
        cmap = Colormap(stops)
        assert cmap.stops[0].position == 0.0

    def test_from_list(self):
        """Test Colormap.from_list factory method."""
        colors = ["red", "#00ff00", (0, 0, 255)]
        cmap = Colormap.from_list(colors, name="ListMap")
        assert cmap.name == "ListMap"
        assert len(cmap.stops) == 3

    def test_from_list_empty_raises_error(self):
        """Test that empty color list raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Colormap.from_list([])

    def test_cut_range(self):
        """Test colormap with cut range."""
        stops = [ColorStop("red"), ColorStop("blue")]
        cmap = Colormap(stops, cut_start=0.2, cut_end=0.8)
        assert cmap.cut_start == 0.2
        assert cmap.cut_end == 0.8

    def test_invalid_cut_range(self):
        """Test that invalid cut range raises ValueError."""
        stops = [ColorStop("red"), ColorStop("blue")]
        with pytest.raises(ValueError, match="Invalid cut range"):
            Colormap(stops, cut_start=0.8, cut_end=0.2)

    def test_get_color_hex(self):
        """Test getting color in hex format."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        cmap = Colormap(stops)
        color = cmap.get_color(0.0, output_format="hex")
        assert isinstance(color, str)
        assert color.startswith("#")

    def test_get_color_rgba_tuple(self):
        """Test getting color in RGBA tuple format."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        cmap = Colormap(stops)
        color = cmap.get_color(0.5, output_format="rgba_tuple")
        assert isinstance(color, tuple)
        assert len(color) == 4
        # All values should be 0-255 integers
        assert all(isinstance(c, int) for c in color)
        assert all(0 <= c <= 255 for c in color)

    def test_get_color_rgb_tuple(self):
        """Test getting color in RGB tuple format."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        cmap = Colormap(stops)
        color = cmap.get_color(0.5, output_format="rgb_tuple")
        assert isinstance(color, tuple)
        assert len(color) == 3

    def test_get_color_invalid_format(self):
        """Test that invalid output format raises ValueError."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        cmap = Colormap(stops)
        with pytest.raises(ValueError, match="Unsupported output_format"):
            cmap.get_color(0.5, output_format="invalid")

    def test_get_color_at_boundaries(self):
        """Test getting colors at boundary positions."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        cmap = Colormap(stops)

        start_color = cmap.get_color(0.0, output_format="rgb_tuple")
        end_color = cmap.get_color(1.0, output_format="rgb_tuple")

        # Red at start (approximately 255, 0, 0) - allow tolerance for color space math
        assert start_color[0] >= 250  # Red channel high
        assert start_color[2] <= 5    # Blue channel low

        # Blue at end (approximately 0, 0, 255)
        assert end_color[0] <= 5      # Red channel low
        assert end_color[2] >= 250    # Blue channel high

    def test_apply_scaler(self):
        """Test applying a scaler to get colors."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        cmap = Colormap(stops)
        scaler = get_linear_scaler(0, 100)

        # At data value 0 (domain_min), should get red - allow tolerance
        color_start = cmap.apply_scaler(0, scaler, output_format="rgb_tuple")
        assert color_start[0] >= 250  # Red channel high

        # At data value 100 (domain_max), should get blue - allow tolerance
        color_end = cmap.apply_scaler(100, scaler, output_format="rgb_tuple")
        assert color_end[2] >= 250  # Blue channel high


class TestColormapInterpolation:
    """Tests for colormap color interpolation."""

    def test_interpolation_midpoint(self):
        """Test interpolation at midpoint."""
        stops = [ColorStop("#000000", 0.0), ColorStop("#ffffff", 1.0)]
        cmap = Colormap(stops, interpolation_space="srgb")
        color = cmap.get_color(0.5, output_format="rgb_tuple")
        # Midpoint between black and white should be gray
        assert 120 <= color[0] <= 140  # Allow some tolerance for color space math
        assert color[0] == color[1] == color[2]  # Gray has equal R, G, B

    def test_interpolation_space_affects_result(self):
        """Test that different interpolation spaces produce different results."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]

        cmap_srgb = Colormap(stops, interpolation_space="srgb")
        cmap_oklch = Colormap(stops, interpolation_space="oklch")

        color_srgb = cmap_srgb.get_color(0.5, output_format="rgb_tuple")
        color_oklch = cmap_oklch.get_color(0.5, output_format="rgb_tuple")

        # Different interpolation spaces should produce different midpoint colors
        # sRGB interpolation between red and blue goes through magenta
        # oklch interpolation takes a different path through color space
        assert color_srgb != color_oklch


class TestNewOutputFormats:
    """Tests for new output formats added to Colormap.get_color()."""

    @pytest.fixture
    def red_colormap(self):
        """Create a red colormap for testing."""
        return Colormap([ColorStop("red", 0.0)])

    @pytest.fixture
    def red_blue_colormap(self):
        """Create a red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops)

    def test_hsl_tuple_format(self, red_colormap):
        """Test HSL tuple format."""
        h, s, l = red_colormap.get_color(0.0, output_format="hsl_tuple")
        # Red in HSL is approximately (0, 100, 50)
        assert abs(h - 0) < 1 or abs(h - 360) < 1  # Hue can be 0 or 360
        assert abs(s - 100) < 1
        assert abs(l - 50) < 1

    def test_hsl_string_format(self, red_colormap):
        """Test HSL string format."""
        hsl_str = red_colormap.get_color(0.0, output_format="hsl_string")
        assert isinstance(hsl_str, str)
        assert hsl_str.startswith("hsl(")
        assert "%" in hsl_str

    def test_rgb_float_format(self, red_colormap):
        """Test RGB float format."""
        r, g, b = red_colormap.get_color(0.0, output_format="rgb_float")
        # Red should be (1.0, 0.0, 0.0)
        assert abs(r - 1.0) < 0.01
        assert abs(g - 0.0) < 0.01
        assert abs(b - 0.0) < 0.01

    def test_rgba_float_format(self, red_colormap):
        """Test RGBA float format."""
        r, g, b, a = red_colormap.get_color(0.0, output_format="rgba_float")
        # Red with full alpha should be (1.0, 0.0, 0.0, 1.0)
        assert abs(r - 1.0) < 0.01
        assert abs(g - 0.0) < 0.01
        assert abs(b - 0.0) < 0.01
        assert abs(a - 1.0) < 0.01

    def test_oklch_string_format(self, red_colormap):
        """Test OKLCH string format."""
        oklch_str = red_colormap.get_color(0.0, output_format="oklch_string")
        assert isinstance(oklch_str, str)
        assert oklch_str.startswith("oklch(")
        assert "%" in oklch_str

    def test_css_color_srgb(self, red_colormap):
        """Test CSS color format with sRGB output space."""
        color = red_colormap.get_color(0.0, output_format="css_color", output_space="srgb")
        # With sRGB, should return hex format
        assert isinstance(color, str)
        assert color.startswith("#")

    def test_css_color_display_p3(self, red_colormap):
        """Test CSS color format with Display P3 output space."""
        color = red_colormap.get_color(0.0, output_format="css_color", output_space="display-p3")
        assert isinstance(color, str)
        assert "display-p3" in color
        assert color.startswith("color(display-p3")

    def test_output_space_parameter(self, red_blue_colormap):
        """Test output_space parameter affects output."""
        # Both should return valid colors
        srgb_color = red_blue_colormap.get_color(0.5, output_format="rgb_float", output_space="srgb")
        p3_color = red_blue_colormap.get_color(0.5, output_format="rgb_float", output_space="display-p3")

        # Both should be tuples of 3 floats
        assert len(srgb_color) == 3
        assert len(p3_color) == 3
        assert all(isinstance(c, float) for c in srgb_color)
        assert all(isinstance(c, float) for c in p3_color)

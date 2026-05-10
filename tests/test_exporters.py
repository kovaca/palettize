"""Tests for palettize.exporters module.

Includes tests converted from inline __main__ blocks in exporter modules.
"""

import json
import urllib.parse

import pytest

from palettize.core import Colormap, ColorStop
from palettize.exporters import get_exporter, list_available_exporters
from palettize.scaling import get_linear_scaler


class TestExporterRegistry:
    """Tests for exporter registry functionality."""

    def test_list_available_exporters(self):
        """Test that exporters are properly registered."""
        exporters = list_available_exporters()
        assert isinstance(exporters, dict)
        # Check some expected exporters exist
        assert "gdal" in exporters
        assert "qgis" in exporters
        assert "sld" in exporters
        assert "titiler" in exporters
        assert "hex" in exporters
        assert "rgba" in exporters

    def test_get_exporter(self):
        """Test getting an exporter by identifier."""
        exporter = get_exporter("gdal")
        assert exporter is not None
        assert exporter.identifier == "gdal"

    def test_get_nonexistent_exporter(self):
        """Test that getting a nonexistent exporter returns None."""
        exporter = get_exporter("nonexistent")
        assert exporter is None


class TestPlaintextExporters:
    """Tests for hex and rgba plaintext exporters."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_hex_exporter_basic(self, simple_colormap, linear_scaler):
        """Test hex exporter produces valid output."""
        exporter = get_exporter("hex")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100, options={"num_colors": 5}
        )
        lines = output.strip().split("\n")
        assert len(lines) == 5
        # Each line should be a hex color
        for line in lines:
            assert line.startswith("#")
            assert len(line) == 7  # #RRGGBB

    def test_rgba_exporter_basic(self, simple_colormap, linear_scaler):
        """Test rgba exporter produces valid output."""
        exporter = get_exporter("rgba")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100, options={"num_colors": 5}
        )
        lines = output.strip().split("\n")
        assert len(lines) == 5
        # Each line should be rgba format
        for line in lines:
            assert line.startswith("rgba(")
            assert line.endswith(")")


class TestTitilerExporter:
    """Tests for TiTiler exporter (converted from inline tests)."""

    @pytest.fixture
    def titiler_exporter(self):
        """Get TiTiler exporter instance."""
        return get_exporter("titiler")

    @pytest.fixture
    def blue_yellow_red_colormap(self):
        """Create a blue-yellow-red colormap."""
        stops = [
            ColorStop("blue", 0.0),
            ColorStop("yellow", 0.5),
            ColorStop("red", 1.0),
        ]
        return Colormap(stops, name="BlueYellowRed")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler."""
        return get_linear_scaler(0, 100)

    def test_default_steps(self, titiler_exporter, blue_yellow_red_colormap, linear_scaler):
        """Test TiTiler exporter with default 11 steps."""
        output = titiler_exporter.export(
            blue_yellow_red_colormap, linear_scaler, 0, 100
        )
        decoded_payload = urllib.parse.parse_qs(output)
        colormap_json = json.loads(decoded_payload["colormap"][0])
        assert len(colormap_json) == 11
        # Check first, middle, and last colors
        assert colormap_json["0"].lower() == "#0000ff"  # Blue
        assert colormap_json["128"].lower() == "#ffff00"  # Yellow
        assert colormap_json["255"].lower() == "#ff0000"  # Red

    def test_custom_num_colors(
        self, titiler_exporter, blue_yellow_red_colormap, linear_scaler
    ):
        """Test TiTiler exporter with custom num_colors=5."""
        output = titiler_exporter.export(
            blue_yellow_red_colormap, linear_scaler, 0, 100, options={"num_colors": 5}
        )
        decoded_payload = urllib.parse.parse_qs(output)
        colormap_json = json.loads(decoded_payload["colormap"][0])
        assert len(colormap_json) == 5
        # Check keys exist: 0, 64, 128, 191, 255
        assert "64" in colormap_json
        assert "191" in colormap_json

    def test_single_color_colormap(self, titiler_exporter, linear_scaler):
        """Test TiTiler exporter with single color colormap."""
        single_stop_cmap = Colormap([ColorStop("green", 0.5)])
        output = titiler_exporter.export(
            single_stop_cmap, linear_scaler, 0, 100, options={"num_colors": 3}
        )
        decoded_payload = urllib.parse.parse_qs(output)
        colormap_json = json.loads(decoded_payload["colormap"][0])
        assert len(colormap_json) == 3
        # All colors should be green
        assert colormap_json["0"].lower() == "#008000"
        assert colormap_json["128"].lower() == "#008000"
        assert colormap_json["255"].lower() == "#008000"

    def test_num_colors_less_than_2_raises_error(
        self, titiler_exporter, blue_yellow_red_colormap, linear_scaler
    ):
        """Test that num_colors < 2 raises ValueError."""
        with pytest.raises(ValueError, match="must be an integer >= 2"):
            titiler_exporter.export(
                blue_yellow_red_colormap,
                linear_scaler,
                0,
                100,
                options={"num_colors": 1},
            )


class TestQGISExporter:
    """Tests for QGIS exporter (converted from inline tests)."""

    @pytest.fixture
    def qgis_exporter(self):
        """Get QGIS exporter instance."""
        return get_exporter("qgis")

    @pytest.fixture
    def test_colormap(self):
        """Create a test colormap."""
        stops = [
            ColorStop("red", 0.0),
            ColorStop("lime", 0.5),
            ColorStop((0, 0, 255, 128), 1.0),  # Blue with alpha
        ]
        return Colormap(stops, name="TestQGIS", interpolation_space="oklch")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler."""
        return get_linear_scaler(0, 100)

    def test_gradient_ramp(self, qgis_exporter, test_colormap, linear_scaler):
        """Test QGIS gradient ramp export."""
        output = qgis_exporter.export(
            test_colormap,
            linear_scaler,
            0,
            100,
            options={
                "num_colors": 10,
                "ramp_type": "gradient",
                "name": "My Gradient Test",
                "tags": ["test", "gradient"],
                "opacity": 0.8,
            },
        )
        assert "<?xml version=" in output
        assert "<colorramps>" in output
        assert 'type="gradient"' in output
        assert "My Gradient Test" in output

    def test_exact_ramp(self, qgis_exporter, test_colormap, linear_scaler):
        """Test QGIS exact ramp export."""
        output = qgis_exporter.export(
            test_colormap,
            linear_scaler,
            0,
            100,
            options={
                "ramp_type": "exact",
                "name": "My Exact Test",
                "tags": ["test", "exact"],
                "discrete": True,
                "opacity": 1.0,
            },
        )
        assert "<?xml version=" in output
        assert 'type="exact"' in output


class TestSLDExporter:
    """Tests for SLD exporter (converted from inline tests)."""

    @pytest.fixture
    def sld_exporter(self):
        """Get SLD exporter instance."""
        return get_exporter("sld")

    @pytest.fixture
    def test_colormap(self):
        """Create a test colormap."""
        stops = [
            ColorStop("red", 0.0),
            ColorStop("yellow", 0.5),
            ColorStop((0, 255, 0, 128), 1.0),  # Green with alpha
        ]
        return Colormap(stops, name="TestSLDRamp")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler."""
        return get_linear_scaler(0, 100)

    def test_sld_100_raster_ramp(self, sld_exporter, test_colormap, linear_scaler):
        """Test SLD 1.0.0 RasterSymbolizer with ramp type."""
        output = sld_exporter.export(
            test_colormap,
            linear_scaler,
            0,
            100,
            options={
                "num_colors": 5,
                "sld_version": "1.0.0",
                "output_type": "ramp",
                "geometry_type": "raster",
                "layer_name": "MyRasterLayer",
                "style_name": "MyRasterStyle",
            },
        )
        assert "<?xml version=" in output
        assert "StyledLayerDescriptor" in output
        assert "RasterSymbolizer" in output
        assert "MyRasterLayer" in output

    def test_sld_110_polygon_values(self, sld_exporter, test_colormap, linear_scaler):
        """Test SLD 1.1.0 PolygonSymbolizer with values type."""
        output = sld_exporter.export(
            test_colormap,
            linear_scaler,
            0,
            100,
            options={
                "sld_version": "1.1.0",
                "output_type": "values",
                "opacity": 0.75,
                "geometry_type": "polygon",
                "layer_name": "MyPolygonLayer",
                "style_name": "MyPolygonStyle",
            },
        )
        assert "<?xml version=" in output
        assert "PolygonSymbolizer" in output

    def test_sld_intervals(self, sld_exporter, linear_scaler):
        """Test SLD with intervals type."""
        simple_stops = [ColorStop("blue", 0.25), ColorStop("green", 0.75)]
        simple_cmap = Colormap(simple_stops, name="IntervalTest")
        output = sld_exporter.export(
            simple_cmap,
            linear_scaler,
            0,
            100,
            options={
                "output_type": "intervals",
                "sld_version": "1.0.0",
                "geometry_type": "raster",
            },
        )
        assert "StyledLayerDescriptor" in output
        assert 'type="intervals"' in output


class TestGDALExporter:
    """Tests for GDAL exporter."""

    @pytest.fixture
    def gdal_exporter(self):
        """Get GDAL exporter instance."""
        return get_exporter("gdal")

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple colormap."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestGDAL")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler."""
        return get_linear_scaler(0, 100)

    def test_gdal_basic_output(self, gdal_exporter, simple_colormap, linear_scaler):
        """Test GDAL exporter produces valid output."""
        output = gdal_exporter.export(
            simple_colormap, linear_scaler, 0, 100, options={"num_colors": 5}
        )
        lines = output.strip().split("\n")
        # Should have header comments and color entries
        assert any(line.startswith("#") for line in lines)
        # Should have at least 5 color entries (plus comments)
        data_lines = [l for l in lines if not l.startswith("#")]
        assert len(data_lines) >= 5

    def test_gdal_with_nodata(self, gdal_exporter, simple_colormap, linear_scaler):
        """Test GDAL exporter with nodata value."""
        output = gdal_exporter.export(
            simple_colormap,
            linear_scaler,
            0,
            100,
            options={
                "num_colors": 5,
                "nodata_value": "nv",
                "nodata_color": (0, 0, 0, 0),
            },
        )
        assert "nv 0 0 0 0" in output


class TestNewExporterRegistration:
    """Tests that new exporters are properly registered."""

    def test_new_exporters_registered(self):
        """Test that all new exporters are registered."""
        exporters = list_available_exporters()
        # Check new exporters exist
        assert "hsl" in exporters
        assert "json" in exporters
        assert "css" in exporters
        assert "gimp" in exporters
        assert "svg" in exporters


class TestHexExporterFormats:
    """Tests for enhanced HexExporter with output_format options."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_hex_lines_format(self, simple_colormap, linear_scaler):
        """Test hex exporter with lines format (default)."""
        exporter = get_exporter("hex")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "lines"}
        )
        lines = output.strip().split("\n")
        assert len(lines) == 3
        assert all(line.startswith("#") for line in lines)

    def test_hex_json_format(self, simple_colormap, linear_scaler):
        """Test hex exporter with JSON format."""
        exporter = get_exporter("hex")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "json"}
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert all(c.startswith("#") for c in data)

    def test_hex_json_nohash_format(self, simple_colormap, linear_scaler):
        """Test hex exporter with JSON no-hash format."""
        exporter = get_exporter("hex")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "json_nohash"}
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert not any(c.startswith("#") for c in data)

    def test_hex_csv_format(self, simple_colormap, linear_scaler):
        """Test hex exporter with CSV format."""
        exporter = get_exporter("hex")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "csv"}
        )
        colors = output.split(", ")
        assert len(colors) == 3
        assert all(c.startswith("#") for c in colors)


class TestRGBAExporterFormats:
    """Tests for enhanced RGBAExporter with output_format options."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_rgba_css_format(self, simple_colormap, linear_scaler):
        """Test rgba exporter with CSS format (default)."""
        exporter = get_exporter("rgba")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "css"}
        )
        lines = output.strip().split("\n")
        assert len(lines) == 3
        assert all(line.startswith("rgba(") for line in lines)

    def test_rgba_tuple_format(self, simple_colormap, linear_scaler):
        """Test rgba exporter with tuple format."""
        exporter = get_exporter("rgba")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "tuple"}
        )
        lines = output.strip().split("\n")
        assert len(lines) == 3
        assert all(line.startswith("(") for line in lines)

    def test_rgba_json_format(self, simple_colormap, linear_scaler):
        """Test rgba exporter with JSON format."""
        exporter = get_exporter("rgba")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "json"}
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert all(len(c) == 4 for c in data)

    def test_rgba_alpha_float_format(self, simple_colormap, linear_scaler):
        """Test rgba exporter with float alpha."""
        exporter = get_exporter("rgba")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "json", "alpha_format": "float"}
        )
        data = json.loads(output)
        # Alpha should be 1.0 for fully opaque colors
        assert all(c[3] == 1.0 for c in data)


class TestHSLExporter:
    """Tests for HSL exporter."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_hsl_css_format(self, simple_colormap, linear_scaler):
        """Test HSL exporter with CSS format."""
        exporter = get_exporter("hsl")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "css"}
        )
        lines = output.strip().split("\n")
        assert len(lines) == 3
        assert all("hsl(" in line for line in lines)

    def test_hsl_json_format(self, simple_colormap, linear_scaler):
        """Test HSL exporter with JSON format."""
        exporter = get_exporter("hsl")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "output_format": "json"}
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert all(len(c) == 3 for c in data)


class TestJSONExporter:
    """Tests for JSON exporter."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_json_array_structure(self, simple_colormap, linear_scaler):
        """Test JSON exporter with array structure."""
        exporter = get_exporter("json")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "structure": "array"}
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_json_array_objects_structure(self, simple_colormap, linear_scaler):
        """Test JSON exporter with array_objects structure."""
        exporter = get_exporter("json")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "structure": "array_objects"}
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert all("position" in item and "color" in item for item in data)

    def test_json_object_structure(self, simple_colormap, linear_scaler):
        """Test JSON exporter with object structure."""
        exporter = get_exporter("json")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "structure": "object"}
        )
        data = json.loads(output)
        assert isinstance(data, dict)
        assert "0" in data
        assert "255" in data

    def test_json_full_structure(self, simple_colormap, linear_scaler):
        """Test JSON exporter with full structure."""
        exporter = get_exporter("json")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "structure": "full"}
        )
        data = json.loads(output)
        assert isinstance(data, dict)
        assert "name" in data
        assert "colors" in data
        assert "domain" in data
        assert data["name"] == "TestMap"

    def test_json_rgb_color_format(self, simple_colormap, linear_scaler):
        """Test JSON exporter with RGB color format."""
        exporter = get_exporter("json")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "structure": "array", "color_format": "rgb"}
        )
        data = json.loads(output)
        assert all(isinstance(c, list) and len(c) == 3 for c in data)


class TestCSSExporter:
    """Tests for CSS exporter."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_css_basic_output(self, simple_colormap, linear_scaler):
        """Test CSS exporter produces valid output."""
        exporter = get_exporter("css")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3}
        )
        assert ":root {" in output
        assert "--color-0:" in output
        assert "--color-1:" in output
        assert "--color-2:" in output

    def test_css_custom_prefix(self, simple_colormap, linear_scaler):
        """Test CSS exporter with custom prefix."""
        exporter = get_exporter("css")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "prefix": "my-palette"}
        )
        assert "--my-palette-0:" in output

    def test_css_custom_selector(self, simple_colormap, linear_scaler):
        """Test CSS exporter with custom selector."""
        exporter = get_exporter("css")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "selector": ".theme-dark"}
        )
        assert ".theme-dark {" in output

    def test_css_include_hsl(self, simple_colormap, linear_scaler):
        """Test CSS exporter with HSL inclusion."""
        exporter = get_exporter("css")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "include_hsl": True}
        )
        assert "--color-0-hsl:" in output


class TestGIMPExporter:
    """Tests for GIMP exporter."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_gimp_basic_output(self, simple_colormap, linear_scaler):
        """Test GIMP exporter produces valid output."""
        exporter = get_exporter("gimp")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3}
        )
        assert "GIMP Palette" in output
        assert "Name: TestMap" in output
        assert "Columns:" in output

    def test_gimp_custom_name(self, simple_colormap, linear_scaler):
        """Test GIMP exporter with custom palette name."""
        exporter = get_exporter("gimp")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "palette_name": "My Custom Palette"}
        )
        assert "Name: My Custom Palette" in output

    def test_gimp_color_format(self, simple_colormap, linear_scaler):
        """Test GIMP exporter color format."""
        exporter = get_exporter("gimp")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3}
        )
        lines = output.strip().split("\n")
        # Skip header lines, check color entries
        color_lines = [l for l in lines if not l.startswith(("GIMP", "Name:", "Columns:", "#"))]
        assert len(color_lines) >= 3


class TestSVGExporter:
    """Tests for SVG exporter."""

    @pytest.fixture
    def simple_colormap(self):
        """Create a simple red-blue colormap for testing."""
        stops = [ColorStop("red", 0.0), ColorStop("blue", 1.0)]
        return Colormap(stops, name="TestMap")

    @pytest.fixture
    def linear_scaler(self):
        """Create a linear scaler from 0-100."""
        return get_linear_scaler(0, 100)

    def test_svg_linear_gradient(self, simple_colormap, linear_scaler):
        """Test SVG exporter with linear gradient."""
        exporter = get_exporter("svg")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "gradient_type": "linear"}
        )
        assert "<defs>" in output
        assert "<linearGradient" in output
        assert "<stop" in output
        assert "stop-color=" in output

    def test_svg_radial_gradient(self, simple_colormap, linear_scaler):
        """Test SVG exporter with radial gradient."""
        exporter = get_exporter("svg")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "gradient_type": "radial"}
        )
        assert "<radialGradient" in output

    def test_svg_custom_id(self, simple_colormap, linear_scaler):
        """Test SVG exporter with custom gradient ID."""
        exporter = get_exporter("svg")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "gradient_id": "my-gradient"}
        )
        assert 'id="my-gradient"' in output

    def test_svg_full_output(self, simple_colormap, linear_scaler):
        """Test SVG exporter with full SVG output."""
        exporter = get_exporter("svg")
        output = exporter.export(
            simple_colormap, linear_scaler, 0, 100,
            options={"num_colors": 3, "full_svg": True}
        )
        assert '<?xml version="1.0"' in output
        assert "<svg" in output
        assert "<rect" in output or "<circle" in output

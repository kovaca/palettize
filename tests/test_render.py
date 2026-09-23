"""Tests for terminal and image rendering."""

from __future__ import annotations

import struct
import zlib

import pytest
from rich.console import Console

from palettize import render
from palettize.core import Colormap

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def render_to_text(renderable, width: int = 80) -> str:
    """Render a Rich object to a plain string with color forced on."""
    console = Console(
        file=None,
        color_system="truecolor",
        force_terminal=True,
        width=width,
        no_color=False,
        legacy_windows=False,
    )
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class TestTerminalSwatch:
    def test_width_is_respected(self, viridis):
        text = render.terminal_swatch(viridis, 20)
        assert len(text.plain) == 20

    def test_height_repeats_the_bar(self, viridis):
        assert render.terminal_swatch(viridis, 10, 3).plain.count("\n") == 2

    def test_uses_block_glyphs_so_shape_survives_color_stripping(self, viridis):
        assert set(render.terminal_swatch(viridis, 10).plain) == {render.BLOCK}

    def test_each_position_gets_its_own_color(self, viridis):
        assert len(render.terminal_swatch(viridis, 16).spans) == 16

    def test_identical_neighbours_collapse_into_one_span(self):
        # A constant colormap needs exactly one styled run, not one per cell.
        flat = Colormap.from_list(["red", "red"])
        assert len(render.terminal_swatch(flat, 32).spans) == 1

    def test_steps_quantize_the_bar(self, viridis):
        assert len(render.terminal_swatch(viridis, 40, steps=4).spans) == 4

    def test_emits_truecolor_escapes_when_the_terminal_supports_it(self, viridis):
        assert "\x1b[38;2;" in render_to_text(render.terminal_swatch(viridis, 8))

    @pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (-5, 1)])
    def test_non_positive_dimensions_are_rejected(self, viridis, width, height):
        with pytest.raises(ValueError, match="at least 1"):
            render.terminal_swatch(viridis, width, height)


class TestPNG:
    def test_has_a_valid_signature(self, viridis):
        assert render.png_bytes(viridis, 16, 4).startswith(PNG_SIGNATURE)

    def test_header_records_the_requested_dimensions(self, viridis):
        data = render.png_bytes(viridis, 123, 45)
        # IHDR data begins 8 (signature) + 4 (length) + 4 (tag) bytes in.
        width, height = struct.unpack(">II", data[16:24])
        assert (width, height) == (123, 45)

    def test_declares_8_bit_rgba(self, viridis):
        bit_depth, color_type = render.png_bytes(viridis, 8, 8)[24:26]
        assert (bit_depth, color_type) == (8, 6)

    def test_ends_with_the_iend_chunk(self, viridis):
        assert render.png_bytes(viridis, 8, 8).endswith(b"IEND\xae\x42\x60\x82")

    def test_every_chunk_crc_validates(self, viridis):
        data = render.png_bytes(viridis, 32, 8)
        offset = len(PNG_SIGNATURE)
        chunks = []
        while offset < len(data):
            (length,) = struct.unpack(">I", data[offset : offset + 4])
            tag = data[offset + 4 : offset + 8]
            payload = data[offset + 8 : offset + 8 + length]
            (crc,) = struct.unpack(">I", data[offset + 8 + length : offset + 12 + length])
            assert crc == zlib.crc32(tag + payload) & 0xFFFFFFFF, f"bad CRC in {tag!r}"
            chunks.append(tag)
            offset += 12 + length
        assert chunks == [b"IHDR", b"IDAT", b"IEND"]

    def test_pixel_data_matches_the_colormap(self, viridis):
        width = 8
        data = render.png_bytes(viridis, width, 1)
        # Locate and inflate the IDAT payload.
        start = data.index(b"IDAT") + 4
        (length,) = struct.unpack(">I", data[start - 8 : start - 4])
        scanline = zlib.decompress(data[start : start + length])
        assert scanline[0] == 0  # filter type "None"
        assert scanline[1:4] == bytes(viridis.rgb_colors(width)[0])

    def test_a_single_pixel_wide_image_uses_the_midpoint(self, viridis):
        data = render.png_bytes(viridis, 1, 1)
        start = data.index(b"IDAT") + 4
        (length,) = struct.unpack(">I", data[start - 8 : start - 4])
        scanline = zlib.decompress(data[start : start + length])
        assert scanline[1:4] == bytes(viridis.get_color(0.5, output_format="rgb_tuple"))

    def test_non_positive_dimensions_are_rejected(self, viridis):
        with pytest.raises(ValueError, match="at least 1"):
            render.png_bytes(viridis, 0, 10)


class TestSVG:
    def test_is_a_standalone_document(self, viridis):
        svg = render.svg_document(viridis)
        assert svg.startswith('<?xml version="1.0"') and svg.rstrip().endswith("</svg>")

    def test_records_the_requested_dimensions(self, viridis):
        assert 'width="300"' in render.svg_document(viridis, 300, 40)

    def test_contains_a_gradient_with_stops(self, viridis):
        svg = render.svg_document(viridis)
        assert "<linearGradient" in svg and svg.count("<stop ") == 64

    def test_name_is_escaped_into_the_title(self):
        cmap = Colormap.from_list(["red", "blue"], name="a & b <script>")
        assert "a &amp; b &lt;script&gt;" in render.svg_document(cmap)

    def test_non_positive_dimensions_are_rejected(self, viridis):
        with pytest.raises(ValueError, match="at least 1"):
            render.svg_document(viridis, 10, 0)


class TestWriteImage:
    def test_png_extension_writes_a_png(self, tmp_path, viridis):
        path = render.write_image(viridis, tmp_path / "out.png", 32, 8)
        assert path.read_bytes().startswith(PNG_SIGNATURE)

    def test_svg_extension_writes_an_svg(self, tmp_path, viridis):
        path = render.write_image(viridis, tmp_path / "out.svg", 32, 8)
        assert path.read_text().startswith("<?xml")

    def test_extension_matching_is_case_insensitive(self, tmp_path, viridis):
        path = render.write_image(viridis, tmp_path / "out.PNG", 32, 8)
        assert path.read_bytes().startswith(PNG_SIGNATURE)

    def test_missing_directories_are_created(self, tmp_path, viridis):
        path = render.write_image(viridis, tmp_path / "a" / "b" / "out.png", 16, 4)
        assert path.exists()

    @pytest.mark.parametrize("filename", ["out.gif", "out.jpg", "out"])
    def test_unsupported_extensions_are_rejected(self, tmp_path, viridis, filename):
        with pytest.raises(ValueError, match="Unsupported image format"):
            render.write_image(viridis, tmp_path / filename)

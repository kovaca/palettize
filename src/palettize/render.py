"""Rendering colormaps to the terminal and to image files.

PNG encoding is done with the standard library alone (``zlib`` + ``struct``), so
image output adds no dependency on Pillow or numpy.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from xml.sax.saxutils import escape

from rich.style import Style
from rich.text import Text

from .core import Colormap

#: File extensions :func:`write_image` knows how to produce.
IMAGE_FORMATS = ("png", "svg")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _rgba_row(colormap: Colormap, width: int) -> list[tuple[int, int, int, int]]:
    """Sample one row of RGBA pixels spanning the colormap."""
    if width < 1:
        raise ValueError("width must be at least 1.")
    if width == 1:
        return [colormap.get_color(0.5, output_format="rgba_tuple")]  # type: ignore[list-item]
    return [
        colormap.get_color(x / (width - 1), output_format="rgba_tuple")  # type: ignore[misc]
        for x in range(width)
    ]


# ----------------------------------------------------------------------
# Terminal
# ----------------------------------------------------------------------


#: Full block glyph. Colored as foreground rather than background so the bar
#: still has visible shape when Rich strips color (piped output, dumb terminals).
BLOCK = "█"


def terminal_swatch(
    colormap: Colormap,
    width: int,
    height: int = 1,
    *,
    steps: int | None = None,
) -> Text:
    """Render a colormap as a Rich :class:`~rich.text.Text` bar of colored blocks.

    Runs of identical color collapse into a single styled segment, so a
    256-cell bar costs a handful of spans rather than 256.

    Args:
        colormap: The colormap to draw.
        width: Width in terminal cells.
        height: Number of lines to repeat.
        steps: If given, quantize into this many discrete bands.
    """
    if width < 1 or height < 1:
        raise ValueError("width and height must be at least 1.")

    source = colormap.quantized(steps) if steps else colormap
    row = _rgba_row(source, width)

    line = Text()
    run_start = 0
    for x in range(1, width + 1):
        if x < width and row[x] == row[run_start]:
            continue
        r, g, b, _ = row[run_start]
        line.append(BLOCK * (x - run_start), style=Style(color=f"rgb({r},{g},{b})"))
        run_start = x

    block = Text()
    for i in range(height):
        if i:
            block.append("\n")
        block.append_text(line.copy())
    return block


# ----------------------------------------------------------------------
# PNG
# ----------------------------------------------------------------------


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    """Assemble one length-prefixed, CRC-suffixed PNG chunk."""
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def png_bytes(colormap: Colormap, width: int = 512, height: int = 64) -> bytes:
    """Encode a colormap as an 8-bit RGBA PNG.

    Args:
        colormap: The colormap to draw, left to right.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        The complete PNG file contents.
    """
    if width < 1 or height < 1:
        raise ValueError("width and height must be at least 1.")

    row = _rgba_row(colormap, width)
    # Filter type 0 (None) prefixes every scanline; all rows are identical.
    scanline = b"\x00" + bytes(channel for pixel in row for channel in pixel)

    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,  # bit depth
        6,  # color type: truecolor with alpha
        0,  # deflate compression
        0,  # adaptive filtering
        0,  # no interlacing
    )
    return (
        _PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(scanline * height, 9))
        + _png_chunk(b"IEND", b"")
    )


# ----------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------


def svg_document(colormap: Colormap, width: int = 512, height: int = 64) -> str:
    """Render a colormap as a standalone SVG document with a gradient fill."""
    if width < 1 or height < 1:
        raise ValueError("width and height must be at least 1.")

    # 64 stops is well past the point where banding is visible at any sane size.
    positions = [i / 63 for i in range(64)]
    stops = "\n".join(
        f'      <stop offset="{p * 100:.3f}%" stop-color="{colormap.get_color(p)}"/>'
        for p in positions
    )
    title = escape(colormap.name or "palette")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f"  <title>{title}</title>\n"
        "  <defs>\n"
        '    <linearGradient id="palettize" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f"{stops}\n"
        "    </linearGradient>\n"
        "  </defs>\n"
        f'  <rect width="{width}" height="{height}" fill="url(#palettize)"/>\n'
        "</svg>\n"
    )


# ----------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------


def write_image(
    colormap: Colormap,
    path: str | Path,
    width: int = 512,
    height: int = 64,
) -> Path:
    """Write a colormap preview to ``path``, choosing the format by extension.

    Args:
        colormap: The colormap to draw.
        path: Destination file; the suffix must be ``.png`` or ``.svg``.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        The path written.

    Raises:
        ValueError: If the file extension is not a supported image format.
    """
    target = Path(path)
    suffix = target.suffix.lower().lstrip(".")
    if suffix not in IMAGE_FORMATS:
        raise ValueError(
            f"Unsupported image format '{target.suffix or target.name}'. "
            f"Supported: {', '.join('.' + f for f in IMAGE_FORMATS)}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    if suffix == "png":
        target.write_bytes(png_bytes(colormap, width, height))
    else:
        target.write_text(svg_document(colormap, width, height), encoding="utf-8")
    return target

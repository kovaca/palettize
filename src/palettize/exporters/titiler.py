"""TiTiler colormap exporter for Palettize."""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction

from ._base import BaseExporter
from ._options import Opt, OptionSpec


class TitilerExporter(BaseExporter):
    """A URL-encoded ``colormap=`` query parameter for TiTiler.

    TiTiler keys colors by raster value in ``0-255``, so the output is
    independent of the data domain and scaling function.
    """

    options: ClassVar[OptionSpec] = OptionSpec(
        Opt(
            "num_colors",
            int,
            11,
            "Number of discrete color steps to sample.",
            minimum=2,
        ),
    )

    @property
    def identifier(self) -> str:
        return "titiler"

    @property
    def name(self) -> str:
        return "TiTiler Colormap URL Parameter"

    @property
    def default_file_extension(self) -> str:
        return "txt"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        num_colors = opts["num_colors"]

        color_map: dict[str, str] = {}
        for position, hex_color in zip(
            self.sample_positions(num_colors),
            colormap.hex_colors(num_colors),
            strict=True,
        ):
            # TiTiler expects #RRGGBB, so drop any alpha channel.
            color_map[str(round(position * 255))] = hex_color[:7]

        payload = {"colormap": json.dumps(color_map, indent=None, separators=(",", ":"))}
        return urllib.parse.urlencode(payload, quote_via=urllib.parse.quote)

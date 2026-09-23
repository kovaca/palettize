"""Exporter for MapLibre GL JS style expressions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, ClassVar

from palettize.core import Colormap, ScalingFunction

from ._base import BaseExporter
from ._options import Opt, OptionSpec


class MapglExporter(BaseExporter):
    """A MapLibre GL ``interpolate`` expression.

    See https://maplibre.org/maplibre-style-spec/expressions/
    """

    uses_domain: ClassVar[bool] = True
    uses_scaler: ClassVar[bool] = True

    options: ClassVar[OptionSpec] = OptionSpec(
        Opt("num_colors", int, 11, "Number of interpolation stops.", minimum=2),
        Opt("precision", int, None, "Decimal places for data values.", minimum=0),
        Opt("property_name", str, "value", "Feature property read by the expression."),
    )

    @property
    def identifier(self) -> str:
        return "mapgl"

    @property
    def name(self) -> str:
        return "MapLibre GL JS Expression"

    @property
    def default_file_extension(self) -> str:
        return "json"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        opts = self.resolve_options(options)
        self.validate_domain(domain_min, domain_max)
        precision = opts["precision"]

        expression: list[Any] = [
            "interpolate",
            ["linear"],
            ["get", opts["property_name"]],
        ]
        for data_value, color in self.sample_scaled(
            colormap,
            scaler,
            opts["num_colors"],
            domain_min,
            domain_max,
            output_format="hex",
        ):
            expression.append(round(data_value, precision) if precision is not None else data_value)
            expression.append(color)

        return json.dumps(expression, indent=2)

from palettize.core import Colormap, ScalingFunction
from ._base import BaseExporter
from typing import Any, Dict, Optional
import json


class MapglExporter(BaseExporter):
    """
    Exports a colormap to a MapLibre GL JS style expression.
    See: https://maplibre.org/maplibre-style-spec/expressions/
    """

    @property
    def identifier(self) -> str:
        return "mapgl"

    @property
    def name(self) -> str:
        return "MapLibre GL JS Expression"

    @property
    def default_file_extension(self) -> Optional[str]:
        return "json"

    def export(
        self,
        colormap: Colormap,
        scaler: ScalingFunction,
        domain_min: float,
        domain_max: float,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        opts = options or {}
        num_colors = opts.get("num_colors", 11)
        precision = opts.get("precision")
        property_name = opts.get("property_name", "value")

        expression = ["interpolate", ["linear"], ["get", property_name]]

        for i in range(num_colors):
            data_val = domain_min + (i / (num_colors - 1)) * (domain_max - domain_min)
            norm_val = scaler(data_val)
            color_hex = colormap.get_color(norm_val, output_format="hex")

            if precision is not None:
                data_val = round(data_val, precision)

            expression.append(data_val)
            expression.append(color_hex)

        return json.dumps(expression, indent=2)

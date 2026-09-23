"""Tests for colormap save/load and the on-disk schema."""

from __future__ import annotations

import json

import pytest

from palettize.core import SCHEMA_VERSION, Colormap, ColorStop
from palettize.exceptions import ColormapFileError


class TestToDict:
    def test_schema_version_is_recorded(self, simple_colormap):
        assert simple_colormap.to_dict()["palettize"] == SCHEMA_VERSION

    def test_opaque_colors_serialize_as_hex(self, simple_colormap):
        colors = [s["color"] for s in simple_colormap.to_dict()["stops"]]
        assert colors == ["#ff0000", "#0000ff"]

    def test_fractional_alpha_uses_a_lossless_form(self):
        cmap = Colormap.from_list(["red", "rgba(0,0,255,0.5)"])
        color = cmap.to_dict()["stops"][1]["color"]
        # Hex would round 0.5 alpha to 128/255, so a precise form is used instead.
        assert color.startswith("color(srgb") and "0.5" in color

    def test_float_noise_is_rounded_away(self, viridis):
        # 1.0 - 0.8 is not exactly 0.2 in binary floating point.
        assert viridis.cut(0.2, 0.8).reversed().to_dict()["cut"] == [0.2, 0.8]


class TestRoundTrip:
    @pytest.mark.parametrize(
        "cmap_factory",
        [
            lambda: Colormap.from_list(["red", "blue"], name="Simple"),
            lambda: Colormap.from_preset("viridis"),
            lambda: Colormap.from_preset("viridis").cut(0.2, 0.8).reversed(),
            lambda: Colormap.from_list(["red", "rgba(0,0,255,0.5)"]),
            lambda: Colormap.from_list(["red", "blue"], interpolation_space="srgb"),
            lambda: Colormap([ColorStop("green", 0.5)]),
        ],
        ids=["simple", "preset", "cut-reversed", "alpha", "srgb-space", "single-stop"],
    )
    def test_dict_round_trip_preserves_equality(self, cmap_factory):
        original = cmap_factory()
        assert Colormap.from_dict(original.to_dict()) == original

    def test_file_round_trip_preserves_sampled_colors(self, tmp_path):
        original = Colormap.from_list(["red", "white", "rgba(0,0,255,0.5)"], name="Test").cut(
            0.1, 0.9
        )
        loaded = Colormap.load(original.save(tmp_path / "map.json"))
        positions = [i / 10 for i in range(11)]
        assert [loaded.get_color(t) for t in positions] == [
            original.get_color(t) for t in positions
        ]

    def test_save_creates_missing_parent_directories(self, tmp_path, simple_colormap):
        path = simple_colormap.save(tmp_path / "deep" / "nested" / "map.json")
        assert path.exists()

    def test_saved_file_is_readable_json_ending_in_a_newline(self, tmp_path, simple_colormap):
        text = simple_colormap.save(tmp_path / "map.json").read_text()
        assert text.endswith("\n")
        assert json.loads(text)["name"] == "TestMap"


class TestFromDictErrors:
    def test_non_dict_payload(self):
        with pytest.raises(ColormapFileError, match="must be a JSON object"):
            Colormap.from_dict(["red", "blue"])  # type: ignore[arg-type]

    def test_missing_schema_key(self):
        with pytest.raises(ColormapFileError, match="missing 'palettize' schema key"):
            Colormap.from_dict({"stops": ["red"]})

    def test_future_schema_version_is_refused_with_an_upgrade_hint(self):
        with pytest.raises(ColormapFileError, match="Upgrade Palettize"):
            Colormap.from_dict({"palettize": SCHEMA_VERSION + 1, "stops": ["red"]})

    def test_older_or_non_integer_schema_is_refused(self):
        for schema in (0, -1, True, "1"):
            with pytest.raises(ColormapFileError, match="Unsupported colormap schema"):
                Colormap.from_dict({"palettize": schema, "stops": ["red"]})

    def test_missing_stops(self):
        with pytest.raises(ColormapFileError, match="non-empty 'stops' list"):
            Colormap.from_dict({"palettize": 1})

    def test_empty_stops(self):
        with pytest.raises(ColormapFileError, match="non-empty 'stops' list"):
            Colormap.from_dict({"palettize": 1, "stops": []})

    def test_malformed_stop_object(self):
        with pytest.raises(ColormapFileError, match="Stop 0 must be"):
            Colormap.from_dict({"palettize": 1, "stops": [{"nope": 1}]})

    def test_unparseable_color_names_the_stop(self):
        with pytest.raises(ColormapFileError, match="Stop 0 is invalid"):
            Colormap.from_dict({"palettize": 1, "stops": ["definitely_not_a_color"]})

    def test_malformed_cut(self):
        with pytest.raises(ColormapFileError, match="two-element"):
            Colormap.from_dict({"palettize": 1, "stops": ["red"], "cut": [0.5]})

    def test_out_of_range_cut(self):
        with pytest.raises(ColormapFileError, match="Invalid colormap definition"):
            Colormap.from_dict({"palettize": 1, "stops": ["red"], "cut": [0.9, 0.1]})

    def test_bare_color_strings_are_accepted_as_stops(self):
        cmap = Colormap.from_dict({"palettize": 1, "stops": ["red", "blue"]})
        assert len(cmap) == 2
        assert cmap.get_color(0.0).lower() == "#ff0000"


class TestLoadErrors:
    def test_missing_file(self, tmp_path):
        with pytest.raises(ColormapFileError, match="Could not read colormap file"):
            Colormap.load(tmp_path / "nope.json")

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json")
        with pytest.raises(ColormapFileError, match="not valid JSON"):
            Colormap.load(path)

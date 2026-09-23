"""Tests for Colormap transforms and protocol methods."""

from __future__ import annotations

import pytest

from palettize.core import Colormap, ColorStop, sample_positions

POSITIONS = [i / 20 for i in range(21)]


class TestSamplePositions:
    def test_single_sample_is_the_midpoint(self):
        assert sample_positions(1) == [0.5]

    def test_endpoints_are_included(self):
        assert sample_positions(5) == [0.0, 0.25, 0.5, 0.75, 1.0]

    def test_zero_is_rejected(self):
        with pytest.raises(ValueError, match="at least 1"):
            sample_positions(0)


class TestReversed:
    def test_sampling_is_mirrored(self, viridis):
        reversed_map = viridis.reversed()
        for t in POSITIONS:
            assert reversed_map.get_color(t) == viridis.get_color(1 - t)

    def test_name_toggles_the_r_suffix(self, viridis):
        assert viridis.reversed().name == "viridis_r"
        assert viridis.reversed().reversed().name == "viridis"

    def test_unnamed_map_stays_unnamed(self):
        cmap = Colormap.from_list(["red", "blue"])
        assert cmap.reversed().name is None

    def test_original_is_untouched(self, viridis):
        before = viridis.get_color(0.0)
        viridis.reversed()
        assert viridis.get_color(0.0) == before

    def test_composes_with_cut(self, viridis):
        cut = viridis.cut(0.2, 0.8)
        assert cut.reversed().get_color(0.0) == cut.get_color(1.0)


class TestCut:
    def test_endpoints_map_to_the_cut_bounds(self, viridis):
        cut = viridis.cut(0.25, 0.75)
        assert cut.get_color(0.0) == viridis.get_color(0.25)
        assert cut.get_color(1.0) == viridis.get_color(0.75)

    def test_cuts_compose_relative_to_the_visible_range(self, viridis):
        composed = viridis.cut(0.5, 1.0).cut(0.0, 0.5)
        assert (composed.cut_start, composed.cut_end) == (0.5, 0.75)
        assert composed.get_color(1.0) == viridis.get_color(0.75)

    def test_full_cut_is_a_no_op(self, viridis):
        assert viridis.cut(0.0, 1.0).get_color(0.37) == viridis.get_color(0.37)

    @pytest.mark.parametrize("start,end", [(-0.1, 1.0), (0.0, 1.1), (0.8, 0.2)])
    def test_invalid_ranges_are_rejected(self, viridis, start, end):
        with pytest.raises(ValueError, match="Invalid cut range"):
            viridis.cut(start, end)


class TestResampled:
    def test_stop_count_matches_the_request(self, viridis):
        assert len(viridis.resampled(7)) == 7

    def test_endpoints_are_preserved(self, viridis):
        resampled = viridis.resampled(64)
        assert resampled.get_color(0.0) == viridis.get_color(0.0)
        assert resampled.get_color(1.0) == viridis.get_color(1.0)

    def test_a_cut_is_baked_in(self, viridis):
        resampled = viridis.cut(0.2, 0.8).resampled(32)
        assert (resampled.cut_start, resampled.cut_end) == (0.0, 1.0)
        assert resampled.get_color(0.0) == viridis.get_color(0.2)

    def test_too_few_stops_is_rejected(self, viridis):
        with pytest.raises(ValueError, match="n >= 2"):
            viridis.resampled(1)


class TestQuantized:
    def test_each_band_is_a_single_color(self, viridis):
        banded = viridis.quantized(5)
        # Sample well inside the first band; all samples must agree.
        within_band = {banded.get_color(t) for t in (0.02, 0.10, 0.18)}
        assert len(within_band) == 1

    def test_band_count_is_respected(self, viridis):
        banded = viridis.quantized(5)
        assert len({banded.get_color((i + 0.5) / 5) for i in range(5)}) == 5

    def test_adjacent_bands_differ(self, viridis):
        banded = viridis.quantized(4)
        assert banded.get_color(0.1) != banded.get_color(0.4)

    def test_single_band_is_flat(self, viridis):
        banded = viridis.quantized(1)
        assert len({banded.get_color(t) for t in POSITIONS}) == 1

    def test_zero_bands_is_rejected(self, viridis):
        with pytest.raises(ValueError, match="n >= 1"):
            viridis.quantized(0)


class TestBlend:
    def test_zero_weight_matches_the_receiver(self, viridis):
        other = Colormap.from_preset("magma")
        blended = viridis.blend(other, 0.0, n=256)
        assert blended.get_color(0.5) == viridis.get_color(0.5)

    def test_full_weight_matches_the_other_map(self, viridis):
        other = Colormap.from_preset("magma")
        blended = viridis.blend(other, 1.0, n=256)
        assert blended.get_color(0.5) == other.get_color(0.5)

    def test_midpoint_differs_from_both(self, viridis):
        other = Colormap.from_preset("magma")
        blended = viridis.blend(other, 0.5)
        assert blended.get_color(0.5) not in (
            viridis.get_color(0.5),
            other.get_color(0.5),
        )

    @pytest.mark.parametrize("t", [-0.1, 1.1])
    def test_weight_must_be_within_zero_and_one(self, viridis, t):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            viridis.blend(viridis, t)


class TestConcat:
    def test_halves_come_from_each_source(self, viridis):
        other = Colormap.from_preset("magma")
        joined = viridis.concat(other, at=0.5, n=256)
        assert joined.get_color(0.0) == viridis.get_color(0.0)
        assert joined.get_color(1.0) == other.get_color(1.0)

    def test_add_operator_is_concat(self, viridis):
        other = Colormap.from_preset("magma")
        assert (viridis + other).get_color(0.0) == viridis.concat(other).get_color(0.0)

    def test_name_combines_both_sources(self, viridis):
        assert (viridis + Colormap.from_preset("magma")).name == "viridis+magma"

    def test_adding_a_non_colormap_is_unsupported(self, viridis):
        with pytest.raises(TypeError):
            viridis + "not a colormap"

    @pytest.mark.parametrize("at", [0.0, 1.0, 1.5])
    def test_join_point_must_be_interior(self, viridis, at):
        with pytest.raises(ValueError, match="strictly between"):
            viridis.concat(viridis, at=at)


class TestProtocolMethods:
    def test_call_returns_the_same_hex_as_get_color(self, viridis):
        assert viridis(0.3) == viridis.get_color(0.3)

    def test_len_counts_stops(self, simple_colormap):
        assert len(simple_colormap) == 2

    def test_iteration_yields_stops(self, simple_colormap):
        assert [type(s) for s in simple_colormap] == [ColorStop, ColorStop]

    def test_equal_definitions_compare_equal(self):
        a = Colormap.from_list(["red", "blue"], name="x")
        b = Colormap.from_list(["red", "blue"], name="x")
        assert a == b and hash(a) == hash(b)

    def test_different_colors_compare_unequal(self):
        assert Colormap.from_list(["red", "blue"]) != Colormap.from_list(["red", "green"])

    def test_different_cut_compares_unequal(self, viridis):
        assert viridis != viridis.cut(0.1, 0.9)

    def test_comparison_with_other_types_is_not_equal(self, viridis):
        assert viridis != "viridis"

    def test_repr_summarizes_without_dumping_stops(self, viridis):
        text = repr(viridis)
        assert "viridis" in text and "stops=256" in text and "#" not in text

    def test_repr_mentions_an_active_cut(self, viridis):
        assert "cut=" in repr(viridis.cut(0.2, 0.8))


class TestBulkSampling:
    def test_colors_returns_the_requested_count(self, viridis):
        assert len(viridis.colors(11)) == 11

    def test_colors_matches_individual_sampling(self, viridis):
        assert viridis.colors(5) == [viridis.get_color(t) for t in sample_positions(5)]

    def test_typed_accessors_have_the_right_shapes(self, viridis):
        assert all(c.startswith("#") for c in viridis.hex_colors(4))
        assert all(len(c) == 3 for c in viridis.rgb_colors(4))
        assert all(len(c) == 4 for c in viridis.rgba_colors(4))
        assert all(len(c) == 3 for c in viridis.hsl_colors(4))

    def test_zero_colors_is_rejected(self, viridis):
        with pytest.raises(ValueError, match="at least 1"):
            viridis.colors(0)


class TestInterpolation:
    def test_stops_are_reproduced_exactly(self, three_stop_colormap):
        assert three_stop_colormap.get_color(0.0).lower() == "#0000ff"
        assert three_stop_colormap.get_color(0.5).lower() == "#ffff00"
        assert three_stop_colormap.get_color(1.0).lower() == "#ff0000"

    def test_positions_are_clamped(self, viridis):
        assert viridis.get_color(-5.0) == viridis.get_color(0.0)
        assert viridis.get_color(5.0) == viridis.get_color(1.0)

    def test_single_stop_is_constant(self):
        cmap = Colormap([ColorStop("green", 0.5)])
        assert len({cmap.get_color(t) for t in POSITIONS}) == 1

    def test_alpha_is_interpolated(self, alpha_colormap):
        _, _, _, alpha = alpha_colormap.get_color(1.0, output_format="rgba_tuple")
        assert alpha == 128

    def test_interpolator_is_cached_across_calls(self, viridis):
        viridis.get_color(0.1)
        first = viridis._get_interpolator()
        viridis.get_color(0.9)
        assert viridis._get_interpolator() is first

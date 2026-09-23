"""Tests for perceptual colormap analysis."""

from __future__ import annotations

import pytest
from coloraide import Color

from palettize import analysis
from palettize.core import Colormap


class TestLightness:
    def test_sequential_preset_is_monotonic(self, viridis):
        report = analysis.analyze(viridis).lightness
        assert report.shape == "sequential"
        assert report.is_monotonic
        assert report.direction == "ascending"
        assert report.turning_points == 0

    def test_reversing_flips_the_direction(self, viridis):
        assert analysis.analyze(viridis.reversed()).lightness.direction == "descending"

    def test_diverging_preset_has_one_turning_point(self):
        report = analysis.analyze(Colormap.from_preset("colorbrewer:RdBu")).lightness
        assert report.shape == "diverging"
        assert report.turning_points == 1

    def test_rainbow_preset_is_erratic(self):
        report = analysis.analyze(Colormap.from_preset("gist_rainbow")).lightness
        assert report.shape == "erratic"
        assert report.turning_points > 1
        assert report.max_reversal > 0

    def test_black_to_white_spans_the_full_range(self):
        report = analysis.analyze(Colormap.from_list(["black", "white"])).lightness
        assert report.span > 95

    def test_constant_map_has_no_span(self):
        report = analysis.analyze(Colormap.from_list(["red", "red"])).lightness
        assert report.span == pytest.approx(0.0, abs=1e-6)


class TestUniformity:
    def test_perceptual_preset_is_uniform(self):
        report = analysis.analyze(Colormap.from_preset("cividis")).uniformity
        assert report.is_uniform
        assert report.coefficient_of_variation < analysis.UNIFORMITY_GOOD_CV

    def test_jet_is_not_uniform(self):
        report = analysis.analyze(Colormap.from_preset("jet")).uniformity
        assert not report.is_uniform

    def test_constant_map_is_trivially_uniform(self):
        report = analysis.analyze(Colormap.from_list(["red", "red"])).uniformity
        assert report.mean == pytest.approx(0.0, abs=1e-6)
        assert report.is_uniform

    def test_delta_count_is_one_less_than_samples(self, viridis):
        assert len(analysis.analyze(viridis, samples=16).uniformity.deltas) == 15


class TestCVD:
    def test_all_three_deficiencies_are_reported(self, viridis):
        assert [c.key for c in analysis.analyze(viridis).cvd] == [
            "protan",
            "deutan",
            "tritan",
        ]

    def test_cividis_is_safe_for_every_deficiency(self):
        # cividis was designed specifically for CVD readability.
        report = analysis.analyze(Colormap.from_preset("cividis"))
        assert all(c.is_distinguishable for c in report.cvd)

    def test_rainbow_degrades_for_every_deficiency(self):
        report = analysis.analyze(Colormap.from_preset("gist_rainbow"))
        assert not any(c.is_distinguishable for c in report.cvd)

    def test_grayscale_is_unaffected_by_cvd(self):
        # Color vision deficiency does not touch a purely achromatic ramp.
        report = analysis.analyze(Colormap.from_list(["black", "white"]))
        assert all(c.retained_contrast > 0.95 for c in report.cvd)

    def test_verdict_is_stable_across_sample_counts(self):
        # Retention is a ratio, so it must not drift with sampling density.
        cmap = Colormap.from_preset("gist_rainbow")
        verdicts = {
            n: tuple(c.is_distinguishable for c in analysis.analyze(cmap, n).cvd)
            for n in (16, 32, 64)
        }
        assert len(set(verdicts.values())) == 1

    def test_simulation_returns_a_usable_color(self):
        simulated = analysis.simulate_cvd(Color("red"), "protan")
        assert simulated.space() == "srgb"
        assert simulated.to_string(hex=True).startswith("#")

    def test_worst_position_is_within_range(self):
        for cvd in analysis.analyze(Colormap.from_preset("jet")).cvd:
            assert 0.0 <= cvd.worst_position <= 1.0


class TestWarningsAndNotes:
    def test_well_behaved_preset_has_no_warnings(self):
        assert analysis.analyze(Colormap.from_preset("cividis")).warnings == []

    def test_jet_produces_warnings(self):
        assert analysis.analyze(Colormap.from_preset("jet")).warnings

    def test_diverging_shape_is_a_note_not_a_warning(self):
        report = analysis.analyze(Colormap.from_preset("colorbrewer:RdBu"))
        assert any("diverging" in note for note in report.notes)
        assert not any("wanders" in warning for warning in report.warnings)

    def test_low_lightness_span_is_noted(self):
        # Two colors of near-identical lightness carry no grayscale information.
        report = analysis.analyze(Colormap.from_list(["#ff0000", "#00a2ff"]))
        assert any("grayscale" in note for note in report.notes)


class TestAnalysisResult:
    def test_sample_count_is_respected(self, viridis):
        report = analysis.analyze(viridis, samples=12)
        assert report.samples == 12
        assert len(report.colors) == 12

    def test_unnamed_colormap_is_labelled_custom(self):
        assert analysis.analyze(Colormap.from_list(["red", "blue"])).name == "custom"

    def test_too_few_samples_is_rejected(self, viridis):
        with pytest.raises(ValueError, match="at least 2 samples"):
            analysis.analyze(viridis, samples=1)

    def test_to_dict_is_json_serializable(self, viridis):
        import json

        payload = json.loads(json.dumps(analysis.analyze(viridis, samples=8).to_dict()))
        assert set(payload) == {
            "name",
            "samples",
            "colors",
            "lightness",
            "uniformity",
            "cvd",
            "warnings",
            "notes",
        }
        assert set(payload["cvd"]) == {"protan", "deutan", "tritan"}


class TestSparkline:
    def test_length_matches_the_input(self):
        assert len(analysis.sparkline([1, 2, 3, 4, 5])) == 5

    def test_ascending_series_ends_higher_than_it_starts(self):
        line = analysis.sparkline([1, 2, 3, 4, 5])
        assert line[0] == "▁" and line[-1] == "█"

    def test_flat_series_uses_the_lowest_bar(self):
        assert analysis.sparkline([3, 3, 3]) == "▁▁▁"

    def test_empty_series_is_empty(self):
        assert analysis.sparkline([]) == ""

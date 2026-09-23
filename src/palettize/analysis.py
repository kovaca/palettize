"""Perceptual analysis of colormaps.

Answers the questions that decide whether a colormap is safe to publish:
does lightness increase steadily, are perceptual steps evenly sized, and does
the map survive the common forms of color vision deficiency?
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from coloraide import Color

from .core import Colormap, sample_positions

#: Color vision deficiency filters, as (key, human-readable label).
CVD_TYPES: tuple[tuple[str, str], ...] = (
    ("protan", "Protanopia (red-blind)"),
    ("deutan", "Deuteranopia (green-blind)"),
    ("tritan", "Tritanopia (blue-blind)"),
)

#: Default number of samples taken when analyzing a colormap.
DEFAULT_SAMPLES = 32

#: A colormap whose consecutive steps vary by less than this coefficient of
#: variation reads as perceptually even.
UNIFORMITY_GOOD_CV = 0.25

#: A CVD simulation that preserves at least this fraction of every original step
#: keeps the colormap readable. Expressed as a ratio rather than an absolute
#: delta-E so the verdict does not shift with the number of samples taken.
CVD_MIN_RETENTION = 0.3

#: Steps smaller than this in the original are treated as already-identical and
#: excluded from retention ratios, which would otherwise divide by ~zero.
_NEGLIGIBLE_DE = 0.1


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


@dataclass(frozen=True)
class LightnessReport:
    """How lightness behaves across the colormap."""

    values: list[float]
    """Oklab lightness (0-100) at each sample position."""

    shape: str
    """``"sequential"`` (monotonic), ``"diverging"`` (one turning point), or
    ``"erratic"`` (lightness wanders)."""

    is_monotonic: bool
    """Whether lightness only ever increases, or only ever decreases."""

    direction: str
    """``"ascending"``, ``"descending"``, or ``"non-monotonic"``."""

    span: float
    """Difference between the lightest and darkest sample."""

    max_reversal: float
    """Largest step that runs against the overall direction. 0 when monotonic."""

    turning_points: int
    """How many times lightness changes direction."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "values": [round(v, 2) for v in self.values],
            "shape": self.shape,
            "is_monotonic": self.is_monotonic,
            "direction": self.direction,
            "span": round(self.span, 2),
            "max_reversal": round(self.max_reversal, 2),
            "turning_points": self.turning_points,
        }


@dataclass(frozen=True)
class UniformityReport:
    """How evenly perceptual difference is spread along the colormap."""

    deltas: list[float]
    """Delta-E 2000 between each consecutive pair of samples."""

    mean: float
    minimum: float
    maximum: float

    coefficient_of_variation: float
    """Standard deviation over the mean. Lower is more uniform."""

    is_uniform: bool
    """Whether the coefficient of variation is within :data:`UNIFORMITY_GOOD_CV`."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean": round(self.mean, 3),
            "min": round(self.minimum, 3),
            "max": round(self.maximum, 3),
            "coefficient_of_variation": round(self.coefficient_of_variation, 3),
            "is_uniform": self.is_uniform,
        }


@dataclass(frozen=True)
class CVDReport:
    """How the colormap holds up under one form of color vision deficiency."""

    key: str
    label: str

    colors: list[str] = field(repr=False)
    """Simulated hex colors at each sample position."""

    retained_contrast: float
    """Simulated mean step size as a fraction of the original. 1.0 loses nothing."""

    worst_retention: float
    """The single worst-preserved step, as a fraction of its original size.
    This is what makes a region of the map turn to mush."""

    worst_position: float
    """Where in ``[0, 1]`` that worst-preserved step occurs."""

    is_distinguishable: bool
    """Whether every step keeps at least :data:`CVD_MIN_RETENTION` of its size."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "retained_contrast": round(self.retained_contrast, 3),
            "worst_retention": round(self.worst_retention, 3),
            "worst_position": round(self.worst_position, 3),
            "is_distinguishable": self.is_distinguishable,
        }


@dataclass(frozen=True)
class ColormapAnalysis:
    """The complete perceptual profile of a colormap."""

    name: str
    samples: int
    positions: list[float] = field(repr=False)
    colors: list[str] = field(repr=False)
    lightness: LightnessReport
    uniformity: UniformityReport
    cvd: list[CVDReport]

    @property
    def warnings(self) -> list[str]:
        """Plain-language descriptions of every problem found. Empty means clean.

        A diverging lightness profile is reported as a note rather than a
        warning: it is the intended shape for a diverging colormap.
        """
        issues: list[str] = []
        if self.lightness.shape == "erratic":
            issues.append(
                f"Lightness wanders ({self.lightness.turning_points} direction changes, "
                f"largest reversal {self.lightness.max_reversal:.1f}), so the map "
                f"implies an ordering its brightness does not follow. Features will "
                f"appear where the data has none."
            )
        if not self.uniformity.is_uniform:
            issues.append(
                f"Perceptual steps are uneven (variation "
                f"{self.uniformity.coefficient_of_variation:.2f}), so equal data "
                f"differences will not look equally different."
            )
        for report in self.cvd:
            if not report.is_distinguishable:
                issues.append(
                    f"{report.label}: near position "
                    f"{report.worst_position:.2f} the map keeps only "
                    f"{report.worst_retention:.0%} of its original contrast, so that "
                    f"region reads as a flat band."
                )
        return issues

    @property
    def notes(self) -> list[str]:
        """Observations that are worth surfacing but are not problems."""
        remarks: list[str] = []
        if self.lightness.shape == "diverging":
            remarks.append(
                "Lightness peaks in the middle and falls away on both sides — the "
                "expected shape for a diverging colormap, but wrong for sequential data."
            )
        if self.lightness.span < 20:
            remarks.append(
                f"Lightness only spans {self.lightness.span:.0f} of 100, so the map "
                f"relies on hue alone and will not survive grayscale printing."
            )
        return remarks

    def to_dict(self) -> dict[str, Any]:
        """A JSON-serializable summary of the analysis."""
        return {
            "name": self.name,
            "samples": self.samples,
            "colors": self.colors,
            "lightness": self.lightness.to_dict(),
            "uniformity": self.uniformity.to_dict(),
            "cvd": {report.key: report.to_dict() for report in self.cvd},
            "warnings": self.warnings,
            "notes": self.notes,
        }


def _analyze_lightness(colors: list[Color]) -> LightnessReport:
    values = [c.convert("oklab")["lightness"] * 100 for c in colors]
    diffs = [b - a for a, b in pairwise(values)]

    # Ignore steps too small to see; float noise would otherwise read as a
    # direction change and make every smooth colormap look erratic.
    significant = [d for d in diffs if abs(d) > 0.5]
    turning_points = sum(1 for a, b in pairwise(significant) if (a > 0) != (b > 0))

    is_monotonic = turning_points == 0
    if is_monotonic:
        direction = "ascending" if values[-1] >= values[0] else "descending"
        max_reversal = 0.0
    else:
        direction = "non-monotonic"
        going_up = values[-1] >= values[0]
        max_reversal = max(max(-d if going_up else d for d in diffs), 0.0)

    if is_monotonic:
        shape = "sequential"
    elif turning_points == 1:
        shape = "diverging"
    else:
        shape = "erratic"

    return LightnessReport(
        values=values,
        shape=shape,
        is_monotonic=is_monotonic,
        direction=direction,
        span=max(values) - min(values),
        max_reversal=max_reversal,
        turning_points=turning_points,
    )


def _consecutive_deltas(colors: list[Color]) -> list[float]:
    """Delta-E 2000 between each consecutive pair of colors."""
    return [a.delta_e(b, method="2000") for a, b in pairwise(colors)]


def _analyze_uniformity(colors: list[Color]) -> UniformityReport:
    deltas = _consecutive_deltas(colors)
    mean = _mean(deltas)
    # Constant colormaps have zero spread, which is trivially uniform.
    cv = (statistics.pstdev(deltas) / mean) if mean > 0 else 0.0
    return UniformityReport(
        deltas=deltas,
        mean=mean,
        minimum=min(deltas) if deltas else 0.0,
        maximum=max(deltas) if deltas else 0.0,
        coefficient_of_variation=cv,
        is_uniform=cv <= UNIFORMITY_GOOD_CV,
    )


def simulate_cvd(color: Color, kind: str, severity: float = 1.0) -> Color:
    """Return ``color`` as seen with the given color vision deficiency.

    Args:
        color: The color to transform.
        kind: One of ``"protan"``, ``"deutan"``, ``"tritan"``.
        severity: 0.0 (unaffected) to 1.0 (full dichromacy).
    """
    return color.filter(kind, severity, space="srgb-linear", out_space="srgb")


def _analyze_cvd(
    colors: list[Color], baseline: list[float], positions: list[float]
) -> list[CVDReport]:
    """Compare each CVD simulation against the original step sizes.

    Retention is measured per step as a *ratio* to the original, which makes the
    verdict independent of how many samples were taken.
    """
    baseline_mean = _mean(baseline)
    reports: list[CVDReport] = []

    for key, label in CVD_TYPES:
        simulated = [simulate_cvd(c, key) for c in colors]
        deltas = _consecutive_deltas(simulated)

        worst_retention = 1.0
        worst_position = 0.0
        for i, (original, seen) in enumerate(zip(baseline, deltas, strict=True)):
            if original < _NEGLIGIBLE_DE:
                continue
            retention = seen / original
            if retention < worst_retention:
                worst_retention = retention
                # Report the midpoint of the affected step.
                worst_position = (positions[i] + positions[i + 1]) / 2

        mean = _mean(deltas)
        reports.append(
            CVDReport(
                key=key,
                label=label,
                colors=[c.to_string(hex=True, fit="clip") for c in simulated],
                retained_contrast=(mean / baseline_mean) if baseline_mean > 0 else 1.0,
                worst_retention=worst_retention,
                worst_position=worst_position,
                is_distinguishable=worst_retention >= CVD_MIN_RETENTION,
            )
        )
    return reports


def analyze(colormap: Colormap, samples: int = DEFAULT_SAMPLES) -> ColormapAnalysis:
    """Profile a colormap's lightness, perceptual uniformity, and CVD safety.

    Args:
        colormap: The colormap to analyze.
        samples: Number of evenly spaced samples to take. More samples give a
            finer picture but exaggerate small local wobbles.

    Returns:
        A :class:`ColormapAnalysis` whose ``warnings`` list is empty for a
        colormap with no detected problems.
    """
    if samples < 2:
        raise ValueError("analyze() requires at least 2 samples.")

    positions = sample_positions(samples)
    colors = [colormap.get_color_object(p).convert("srgb") for p in positions]

    uniformity = _analyze_uniformity(colors)
    return ColormapAnalysis(
        name=colormap.name or "custom",
        samples=samples,
        positions=positions,
        colors=[c.to_string(hex=True, fit="clip") for c in colors],
        lightness=_analyze_lightness(colors),
        uniformity=uniformity,
        cvd=_analyze_cvd(colors, uniformity.deltas, positions),
    )


def sparkline(values: list[float], height: int = 8) -> str:
    """Render values as a one-line Unicode bar chart.

    Args:
        values: The series to plot.
        height: Number of distinct bar heights to use (max 8).
    """
    blocks = "▁▂▃▄▅▆▇█"[: max(1, min(8, height))]
    if not values:
        return ""
    low, high = min(values), max(values)
    span = high - low
    if span == 0:
        return blocks[0] * len(values)
    return "".join(
        blocks[min(len(blocks) - 1, int((v - low) / span * len(blocks)))] for v in values
    )

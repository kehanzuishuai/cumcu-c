"""Reusable publication layer for CUMCM C-problem paper figures.

The module adapts useful figures4papers ideas to A4 mathematical-modeling
papers: semantic colors, restrained geometry, shared styling, vector export,
tail-risk evidence, evidence-rich composition, categorical-structure and
relationship candidates, full-span composition bounds, portfolio review, and
lightweight machine checks.
Visual inspection of the rendered A4 preview is still mandatory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.text import Text


SEMANTIC_COLORS = {
    "primary": "#0F4D92",
    "secondary": "#3775BA",
    "comparison": "#E3A06A",
    "improvement": "#7FAE79",
    "risk": "#B64342",
    "baseline": "#767676",
    "neutral": "#CFCECE",
    "uncertainty": "#DCE8F3",
    "risk_tail": "#F2D7D5",
    "grid": "#D9D9D9",
    "text": "#262626",
}

A4_FULL_WIDTH_IN = 6.6
A4_HALF_WIDTH_IN = 3.2
MIN_FINAL_FONT_PT = 7.5
SUPPORTED_FORMATS = {"pdf", "png", "svg"}
FIGURE_DECISION_PRIORITY = (
    "evidence_match",
    "information_expression",
    "readability",
    "portfolio_diversity",
    "advanced_appearance",
)


@dataclass(frozen=True)
class FigureStyle:
    base_font_size: float = 8.5
    axes_label_size: float = 9.5
    legend_size: float = 8.5
    axes_linewidth: float = 0.8
    main_linewidth: float = 1.7
    grid_linewidth: float = 0.55
    png_dpi: int = 400


@dataclass(frozen=True)
class DensityGateResult:
    """Deterministic result from the post-selection information-density gate."""

    status: str
    issues: tuple[str, ...]
    recommendations: tuple[str, ...]
    metrics: Mapping[str, float]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass(frozen=True)
class EvidenceRichnessGateResult:
    """Decision on whether complementary evidence should share a figure."""

    status: str
    composition: str
    issues: tuple[str, ...]
    recommendations: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    metrics: Mapping[str, float]

    @property
    def passed(self) -> bool:
        return self.status in {"PASS", "KEEP_SEPARATE"}


@dataclass(frozen=True)
class FigurePortfolioGateResult:
    """Whole-paper review of repeated chart families."""

    status: str
    issues: tuple[str, ...]
    recommendations: tuple[str, ...]
    families_to_review: tuple[str, ...]
    metrics: Mapping[str, float]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass(frozen=True)
class AdvancedFigureCandidateGateResult:
    """Optional advanced-chart candidates justified by evidence structure."""

    status: str
    candidates: tuple[str, ...]
    issues: tuple[str, ...]
    recommendations: tuple[str, ...]
    metrics: Mapping[str, float]

    @property
    def passed(self) -> bool:
        return self.status in {"KEEP_STANDARD", "CONSIDER_ADVANCED"}


def apply_publication_style(style: FigureStyle | None = None) -> None:
    """Apply a portable, restrained A4 publication style."""

    style = style or FigureStyle()
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": [
                "Times New Roman",
                "SimSun",
                "STSong",
                "Songti SC",
                "Noto Serif CJK SC",
                "DejaVu Serif",
            ],
            "font.sans-serif": [
                "Arial",
                "Microsoft YaHei",
                "Noto Sans CJK SC",
                "DejaVu Sans",
            ],
            "mathtext.fontset": "stix",
            "axes.unicode_minus": False,
            "font.size": style.base_font_size,
            "axes.labelsize": style.axes_label_size,
            "axes.titlesize": style.axes_label_size,
            "xtick.labelsize": style.base_font_size,
            "ytick.labelsize": style.base_font_size,
            "legend.fontsize": style.legend_size,
            "axes.linewidth": style.axes_linewidth,
            "lines.linewidth": style.main_linewidth,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.transparent": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def create_subplots(
    nrows: int = 1,
    ncols: int = 1,
    *,
    width: str | float = "full",
    height: float = 3.6,
    sharex: bool = False,
    sharey: bool = False,
    **kwargs,
) -> tuple[Figure, np.ndarray]:
    """Create constrained-layout subplots sized for final A4 placement."""

    if width == "full":
        width_in = A4_FULL_WIDTH_IN
    elif width == "half":
        width_in = A4_HALF_WIDTH_IN
    elif isinstance(width, (int, float)) and width > 0:
        width_in = float(width)
    else:
        raise ValueError("width must be 'full', 'half', or a positive number")
    if height <= 0:
        raise ValueError("height must be positive")

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(width_in, height),
        sharex=sharex,
        sharey=sharey,
        layout="constrained",
        **kwargs,
    )
    return fig, np.atleast_1d(axes).reshape(-1)


def style_axis(ax: Axes, *, grid: bool | str = False, box: bool = False) -> None:
    """Unify spines, ticks, and optional major grid for one axis."""

    for name, spine in ax.spines.items():
        spine.set_visible(box or name in {"left", "bottom"})
        spine.set_color(SEMANTIC_COLORS["baseline"])
        spine.set_linewidth(0.8)
    ax.tick_params(
        axis="both",
        which="major",
        direction="out",
        length=3.0,
        width=0.7,
        color=SEMANTIC_COLORS["baseline"],
        labelcolor=SEMANTIC_COLORS["text"],
    )
    ax.grid(False)
    if grid:
        axis = "both" if grid is True else str(grid)
        if axis not in {"x", "y", "both"}:
            raise ValueError("grid must be False, True, 'x', 'y', or 'both'")
        ax.grid(
            True,
            axis=axis,
            which="major",
            color=SEMANTIC_COLORS["grid"],
            linewidth=0.55,
            alpha=0.5,
        )
        ax.set_axisbelow(True)


def bar_width(series_count: int = 1) -> float:
    """Return restrained bar width; grouped clusters occupy at most 0.72."""

    if series_count < 1:
        raise ValueError("series_count must be at least 1")
    if series_count == 1:
        return 0.52
    return min(0.34, 0.72 / series_count)


def grouped_positions(
    category_count: int, series_count: int
) -> tuple[list[np.ndarray], float]:
    """Return centered positions and width for grouped bars."""

    if category_count < 1:
        raise ValueError("category_count must be at least 1")
    width = bar_width(series_count)
    centers = np.arange(category_count, dtype=float)
    offsets = (np.arange(series_count) - (series_count - 1) / 2) * width
    return [centers + offset for offset in offsets], width


def add_panel_labels(
    axes: Sequence[Axes], labels: Sequence[str] | None = None
) -> None:
    """Add restrained (a), (b), ... labels in a consistent position."""

    labels = labels or [f"({chr(97 + i)})" for i in range(len(axes))]
    if len(labels) != len(axes):
        raise ValueError("labels must match axes length")
    for ax, label in zip(axes, labels):
        ax.text(
            -0.10,
            1.02,
            label,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9.0,
            fontweight="bold",
            color=SEMANTIC_COLORS["text"],
        )


def _finite_1d(values: Iterable[float], *, name: str) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional sequence")
    array = array[np.isfinite(array)]
    if array.size == 0:
        raise ValueError(f"{name} contains no finite values")
    return array


def _interval_array(intervals: Iterable[Sequence[float]]) -> np.ndarray:
    array = np.asarray(list(intervals), dtype=float)
    if array.ndim != 2 or array.shape[1] != 2 or array.shape[0] == 0:
        raise ValueError("intervals must be a non-empty sequence of (lower, upper)")
    if not np.all(np.isfinite(array)):
        raise ValueError("intervals must contain only finite values")
    if np.any(array[:, 1] < array[:, 0]):
        raise ValueError("each interval must satisfy lower <= upper")
    return array


def _validated_limits(limits: Sequence[float], *, name: str) -> tuple[float, float]:
    array = np.asarray(limits, dtype=float)
    if array.shape != (2,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain two finite values")
    lower, upper = float(array[0]), float(array[1])
    if upper <= lower:
        raise ValueError(f"{name} must satisfy lower < upper")
    return lower, upper


def _validated_axis_limits(
    limits: Sequence[float], *, name: str
) -> tuple[float, float]:
    """Validate displayed axis limits while preserving an inverted direction."""

    array = np.asarray(limits, dtype=float)
    if array.shape != (2,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain two finite values")
    start, end = float(array[0]), float(array[1])
    if end == start:
        raise ValueError(f"{name} must have non-zero span")
    return start, end


def visual_information_density_gate(
    chart_kind: str,
    *,
    x: Iterable[float] | None = None,
    samples: Iterable[float] | None = None,
    intervals: Iterable[Sequence[float]] | None = None,
    axis_limits: Sequence[float] | None = None,
    y_limits: Sequence[float] | None = None,
    annotated_points: Iterable[Sequence[float]] | None = None,
    alpha: float = 0.05,
    summary_count: int | None = None,
    summary_only: bool = False,
) -> DensityGateResult:
    """Check whether a theoretically valid chart carries visible evidence.

    The gate runs after chart selection. It may request new model evaluations,
    a tighter scale, or a different chart type, but it never synthesizes new
    response values from interpolation.
    """

    kind = str(chart_kind).strip().lower().replace("-", "_")
    if not kind:
        raise ValueError("chart_kind cannot be empty")
    if summary_count is not None and summary_count < 0:
        raise ValueError("summary_count cannot be negative")

    continuous_kinds = {
        "continuous_curve",
        "parameter_sweep",
        "risk_frontier",
        "sensitivity",
    }
    distribution_kinds = {"distribution", "histogram", "kde", "tail_risk"}
    interval_kinds = {
        "confidence_interval",
        "forest",
        "interval",
        "paired_diff",
    }
    summary_kinds = {"lollipop", "summary", "summary_points"}
    priority = {"PASS": 0, "RESCALE": 1, "RESAMPLE": 2, "RECHART": 3}

    status = "PASS"
    issues: list[str] = []
    recommendations: list[str] = []
    metrics: dict[str, float] = {}

    def flag(action: str, issue: str, recommendation: str) -> None:
        nonlocal status
        if issue not in issues:
            issues.append(issue)
            recommendations.append(recommendation)
        if priority[action] > priority[status]:
            status = action

    x_values: np.ndarray | None = None
    if x is not None:
        x_values = _finite_1d(x, name="x")
        metrics["x_point_count"] = float(x_values.size)
        metrics["unique_x_count"] = float(np.unique(x_values).size)

    x_bounds: tuple[float, float] | None = None
    if axis_limits is not None:
        x_bounds = _validated_limits(axis_limits, name="axis_limits")
        metrics["axis_span"] = x_bounds[1] - x_bounds[0]

    if kind in continuous_kinds:
        if x_values is None:
            raise ValueError(f"x is required for chart_kind={kind!r}")
        unique_x = np.unique(x_values)
        unique_count = int(unique_x.size)
        if unique_count < 5:
            flag(
                "RESAMPLE",
                "CONTINUOUS_CURVE_TOO_SPARSE",
                "Re-run the model at 9-21 distinct parameter values; do not interpolate outcomes.",
            )
        elif unique_count < 9:
            flag(
                "RESAMPLE",
                "CONTINUOUS_CURVE_LOW_DENSITY",
                "Add real model evaluations until the trend has about 9-21 support points.",
            )
        if unique_count >= 2:
            x_span = float(np.ptp(unique_x))
            gap_ratio = (
                float(np.max(np.diff(unique_x)) / x_span) if x_span > 0 else 1.0
            )
            metrics["max_gap_ratio"] = gap_ratio
            if gap_ratio > 0.35:
                flag(
                    "RESAMPLE",
                    "CONTINUOUS_CURVE_LARGE_GAP",
                    "Densify real evaluations around large gaps and any regime switch.",
                )

    if kind in distribution_kinds:
        if summary_only or samples is None:
            count = 0 if summary_count is None else summary_count
            metrics["summary_count"] = float(count)
            flag(
                "RECHART",
                "SUMMARY_VALUES_ARE_NOT_A_DISTRIBUTION",
                "Use the underlying Monte Carlo/bootstrap samples for a histogram or ECDF with VaR/CVaR tail; otherwise rename and use a summary table or forest plot.",
            )
        else:
            sample_values = _finite_1d(samples, name="samples")
            sample_count = int(sample_values.size)
            metrics["sample_count"] = float(sample_count)
            if sample_count < 30:
                flag(
                    "RESAMPLE",
                    "DISTRIBUTION_SAMPLE_TOO_SMALL",
                    "Increase real samples before estimating distribution shape; do not draw KDE from fewer than 30 observations.",
                )
            elif kind == "kde" and sample_count < 200:
                flag(
                    "RESAMPLE",
                    "DISTRIBUTION_LOW_DENSITY_FOR_KDE",
                    "Prefer ECDF or obtain at least about 200 real samples before using KDE as shape evidence.",
                )
            if kind == "tail_risk":
                if not 0 < alpha < 0.5:
                    raise ValueError("alpha must be between 0 and 0.5")
                tail_count = int(np.floor(alpha * sample_count))
                metrics["expected_tail_count"] = float(tail_count)
                if tail_count < 20:
                    flag(
                        "RESAMPLE",
                        "TAIL_SAMPLE_TOO_SMALL_FOR_CVAR",
                        "Increase real simulations so the lower-tail region contains at least about 20 observations.",
                    )

    interval_values: np.ndarray | None = None
    if kind in interval_kinds:
        if intervals is None:
            raise ValueError(f"intervals are required for chart_kind={kind!r}")
        interval_values = _interval_array(intervals)
        widths = interval_values[:, 1] - interval_values[:, 0]
        median_width = float(np.median(widths))
        envelope_width = float(interval_values[:, 1].max() - interval_values[:, 0].min())
        metrics["median_interval_width"] = median_width
        metrics["interval_envelope_width"] = envelope_width
        if x_bounds is not None:
            axis_span = x_bounds[1] - x_bounds[0]
            width_ratio = median_width / axis_span
            envelope_ratio = envelope_width / axis_span
            metrics["median_interval_axis_ratio"] = width_ratio
            metrics["interval_envelope_axis_ratio"] = envelope_ratio
            if width_ratio < 0.05 or envelope_ratio < 0.25:
                flag(
                    "RESCALE",
                    "INTERVALS_INVISIBLE_AT_CURRENT_SCALE",
                    "Tighten the numeric axis around the interval envelope with honest padding; state when a reference value lies outside the zoomed view.",
                )

    if x_values is not None and x_bounds is not None:
        data_span = float(np.ptp(x_values))
        occupancy = data_span / (x_bounds[1] - x_bounds[0])
        metrics["data_axis_occupancy"] = occupancy
        if occupancy < 0.25:
            flag(
                "RESCALE",
                "DATA_OCCUPIES_TOO_LITTLE_AXIS",
                "Tighten the axis to the data envelope with explicit padding or provide overview plus zoom.",
            )

    if kind in summary_kinds and summary_only and 0 < (summary_count or 0) <= 5:
        metrics["summary_count"] = float(summary_count or 0)
        flag(
            "RECHART",
            "FEW_SUMMARIES_WEAK_AS_STANDALONE_FIGURE",
            "Use a compact table, interval comparison, or supporting text unless the summaries encode a genuine ordered structure.",
        )

    if annotated_points is not None:
        if x_bounds is None or y_limits is None:
            raise ValueError(
                "axis_limits and y_limits are required when annotated_points are checked"
            )
        y_bounds = _validated_limits(y_limits, name="y_limits")
        points = np.asarray(list(annotated_points), dtype=float)
        if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] == 0:
            raise ValueError("annotated_points must be a non-empty sequence of (x, y)")
        if not np.all(np.isfinite(points)):
            raise ValueError("annotated_points must contain only finite values")
        x_norm = (points[:, 0] - x_bounds[0]) / (x_bounds[1] - x_bounds[0])
        y_norm = (points[:, 1] - y_bounds[0]) / (y_bounds[1] - y_bounds[0])
        edge_distance = float(
            np.min(np.concatenate((x_norm, 1 - x_norm, y_norm, 1 - y_norm)))
        )
        metrics["annotation_min_edge_distance"] = edge_distance
        if edge_distance < 0.06:
            flag(
                "RESCALE",
                "ANNOTATION_NEAR_AXIS_BOUNDARY",
                "Add local padding or place the label inward with boundary-aware alignment.",
            )

    return DensityGateResult(
        status=status,
        issues=tuple(issues),
        recommendations=tuple(recommendations),
        metrics=metrics,
    )


def _normalized_labels(values: Iterable[str], *, name: str) -> tuple[str, ...]:
    labels = tuple(dict.fromkeys(str(value).strip().lower() for value in values))
    if not labels or any(not label for label in labels):
        raise ValueError(f"{name} must contain non-empty labels")
    return labels


def evidence_richness_gate(
    evidence_roles: Iterable[str],
    *,
    current_layers: Iterable[str] | None = None,
    relationship: str = "independent",
    same_claim: bool = True,
    same_object: bool = True,
    shared_coordinate: bool = True,
) -> EvidenceRichnessGateResult:
    """Decide whether evidence warrants a layered or multi-panel figure.

    ``relationship`` must be declared from the claim and data semantics. Merely
    having several columns does not make evidence complementary. The function
    never invents evidence or changes chart type for decorative variety.
    """

    roles = _normalized_labels(evidence_roles, name="evidence_roles")
    layers = (
        _normalized_labels(current_layers, name="current_layers")
        if current_layers is not None
        else ()
    )
    relation = str(relationship).strip().lower()
    if relation not in {"complementary", "independent", "redundant"}:
        raise ValueError(
            "relationship must be 'complementary', 'independent', or 'redundant'"
        )

    role_set = set(roles)
    layer_set = set(layers)
    missing = tuple(role for role in roles if role not in layer_set)
    metrics = {
        "evidence_role_count": float(len(roles)),
        "current_layer_count": float(len(layers)),
        "missing_evidence_count": float(len(missing)),
    }

    if len(roles) == 1:
        return EvidenceRichnessGateResult(
            status="PASS",
            composition="single",
            issues=(),
            recommendations=(
                "Keep the simplest chart that directly encodes the single evidence role.",
            ),
            missing_evidence=missing,
            metrics=metrics,
        )

    if relation != "complementary" or not same_claim or not same_object:
        reasons: list[str] = []
        if relation != "complementary":
            reasons.append("EVIDENCE_NOT_COMPLEMENTARY")
        if not same_claim:
            reasons.append("MULTIPLE_PRIMARY_CLAIMS")
        if not same_object:
            reasons.append("DIFFERENT_EVIDENCE_OBJECTS")
        return EvidenceRichnessGateResult(
            status="KEEP_SEPARATE",
            composition="separate",
            issues=tuple(reasons),
            recommendations=(
                "Do not create a composite figure; keep, simplify, tabulate, or remove each item according to its own claim.",
            ),
            missing_evidence=(),
            metrics=metrics,
        )

    composition = "layer" if shared_coordinate else "panel"
    if not missing and role_set.issubset(layer_set):
        return EvidenceRichnessGateResult(
            status="PASS",
            composition=composition,
            issues=(),
            recommendations=(
                "Retain the composite only while every layer helps verify the same claim.",
            ),
            missing_evidence=(),
            metrics=metrics,
        )

    status = "COMPOSE_LAYER" if shared_coordinate else "COMPOSE_PANEL"
    action = (
        "Add the missing evidence as restrained layers on the shared coordinate."
        if shared_coordinate
        else "Use aligned panels with shared semantics because the evidence needs different encodings or scales."
    )
    return EvidenceRichnessGateResult(
        status=status,
        composition=composition,
        issues=("COMPLEMENTARY_EVIDENCE_NOT_YET_COMPOSED",),
        recommendations=(
            action,
            "Re-run the information-density and A4 visual gates after composition.",
        ),
        missing_evidence=missing,
        metrics=metrics,
    )


def _portfolio_family(chart_family: str) -> str:
    family = str(chart_family).strip().lower().replace("-", "_")
    if family in {"lollipop", "lollipop_plot"}:
        return "dot"
    if family in {
        "corrgram",
        "pairwise_relationship_matrix",
        "corrgram_pairwise_relationship_matrix",
    }:
        return "pairwise_matrix"
    if family in {"chord", "chord_diagram"}:
        return "network"
    if family in {"upset", "upset_plot"}:
        return "set_intersection"
    if "line" in family or family in {"curve", "trend"}:
        return "line"
    if "bar" in family or family in {"column", "columns"}:
        return "bar"
    if "heat" in family or "matrix" in family:
        return "heatmap"
    return family


def figure_portfolio_gate(
    figures: Sequence[Mapping[str, object]],
    *,
    min_repeat: int = 3,
    dominant_share: float = 0.5,
) -> FigurePortfolioGateResult:
    """Review repeated chart families without imposing decorative diversity.

    Each item needs ``figure_id``, ``chart_family`` and ``evidence_kind``;
    ``series_count`` defaults to one. Two adjacent multi-series line/bar figures
    trigger a structural review even when their evidence labels match.
    Set ``selection_confirmed=True`` only after rechecking Claim -> Evidence ->
    Chart Type. Repetition is accepted when the evidence structure genuinely
    repeats; mixed evidence forced into one dominant family receives REVIEW.
    This post-selection audit never promotes heatmaps or penalizes basic charts.
    """

    if min_repeat < 2:
        raise ValueError("min_repeat must be at least 2")
    if not 0 < dominant_share <= 1:
        raise ValueError("dominant_share must be in (0, 1]")

    normalized: list[tuple[str, str, str, bool, int]] = []
    for index, item in enumerate(figures):
        if not isinstance(item, Mapping):
            raise ValueError("each figure must be a mapping")
        figure_id = str(item.get("figure_id", f"figure_{index + 1}")).strip()
        family = _portfolio_family(str(item.get("chart_family", "")))
        evidence = str(item.get("evidence_kind", "")).strip().lower()
        if not figure_id or not family or not evidence:
            raise ValueError(
                "each figure needs non-empty figure_id, chart_family, and evidence_kind"
            )
        confirmed = bool(item.get("selection_confirmed", False))
        series_count = int(item.get("series_count", 1))
        if series_count < 1:
            raise ValueError("series_count must be at least 1")
        normalized.append((figure_id, family, evidence, confirmed, series_count))

    total = len(normalized)
    if total == 0:
        return FigurePortfolioGateResult(
            status="PASS",
            issues=(),
            recommendations=(),
            families_to_review=(),
            metrics={"figure_count": 0.0},
        )

    families: dict[str, list[tuple[str, str, str, bool, int]]] = {}
    for item in normalized:
        families.setdefault(item[1], []).append(item)

    max_run = 1
    run_length = 1
    for previous, current in zip(normalized, normalized[1:]):
        run_length = run_length + 1 if previous[1] == current[1] else 1
        max_run = max(max_run, run_length)

    review: set[str] = set()
    issues: list[str] = []
    recommendations: list[str] = []
    for family, items in families.items():
        count = len(items)
        share = count / total
        evidence_kinds = {item[2] for item in items}
        unconfirmed = any(not item[3] for item in items)
        family_has_long_run = False
        run = 0
        for item in normalized:
            run = run + 1 if item[1] == family else 0
            family_has_long_run = family_has_long_run or run >= min_repeat
        repeated = count >= min_repeat and (
            share >= dominant_share or family_has_long_run
        )
        if repeated and len(evidence_kinds) > 1 and unconfirmed:
            review.add(family)

    heatmap_sequence_review = False
    max_heatmap_run = 0
    heatmap_run = 0
    for item in normalized:
        heatmap_run = heatmap_run + 1 if item[1] == "heatmap" else 0
        max_heatmap_run = max(max_heatmap_run, heatmap_run)
    for previous, current in zip(normalized, normalized[1:]):
        consecutive_mixed_heatmaps = (
            previous[1] == current[1] == "heatmap"
            and previous[2] != current[2]
            and (not previous[3] or not current[3])
        )
        if consecutive_mixed_heatmaps:
            heatmap_sequence_review = True
            review.add("heatmap")

    if review:
        issues.append("CHART_FAMILY_REPEATED_ACROSS_MIXED_EVIDENCE")
        recommendations.append(
            "Recheck the flagged figures against Claim -> Evidence -> Chart Type; retain a repeated type when justified, and change it only when the evidence structure calls for another encoding."
        )
        if "heatmap" in review:
            issues.append("HEATMAP_OVERUSE_NEEDS_EVIDENCE_RECHECK")
            if heatmap_sequence_review:
                issues.append("CONSECUTIVE_HEATMAPS_CROSS_MIXED_EVIDENCE")
            recommendations.append(
                "A heatmap is not a default replacement for repeated line or bar charts. Keep it only for a genuine two-axis matrix whose cellwise pattern is the primary evidence; otherwise restore the evidence-matched line, bar, dot, interval, distribution, or small-multiple view."
            )

    similar_multi_series: set[str] = set()
    max_multi_series_run = 0
    current_multi_series_run = 0
    previous_family: str | None = None
    for item in normalized:
        family = item[1]
        is_multi_series = family in {"line", "bar"} and item[4] >= 2
        if is_multi_series and family == previous_family:
            current_multi_series_run += 1
        elif is_multi_series:
            current_multi_series_run = 1
        else:
            current_multi_series_run = 0
        previous_family = family if is_multi_series else None
        max_multi_series_run = max(max_multi_series_run, current_multi_series_run)

    for previous, current in zip(normalized, normalized[1:]):
        same_multi_series_family = (
            previous[1] == current[1]
            and previous[1] in {"line", "bar"}
            and previous[4] >= 2
            and current[4] >= 2
        )
        if same_multi_series_family and (not previous[3] or not current[3]):
            similar_multi_series.add(previous[1])

    if similar_multi_series:
        review.update(similar_multi_series)
        issues.append("SIMILAR_MULTI_SERIES_SEQUENCE_NEEDS_ALTERNATIVE_CHECK")
        recommendations.append(
            "For consecutive multi-series line/bar figures, compare equal-status alternatives: keep line for trajectories, bar/dot for discrete magnitudes, small multiples for overlapping series, heatmap or bubble matrix only for a genuine two-axis matrix, and distribution only for real samples. Do not replace with heatmap merely to vary the portfolio."
        )

    max_share = max(len(items) / total for items in families.values())
    metrics = {
        "figure_count": float(total),
        "chart_family_count": float(len(families)),
        "max_family_share": float(max_share),
        "max_consecutive_family_repeat": float(max_run),
        "max_consecutive_multi_series_repeat": float(max_multi_series_run),
        "max_consecutive_heatmap_repeat": float(max_heatmap_run),
    }
    if not review:
        return FigurePortfolioGateResult(
            status="PASS",
            issues=(),
            recommendations=(
                "Keep repeated line, bar, dot, heatmap, or other families when their evidence structures genuinely repeat; portfolio diversity is only a late diagnostic.",
            ),
            families_to_review=(),
            metrics=metrics,
        )

    return FigurePortfolioGateResult(
        status="REVIEW",
        issues=tuple(issues),
        recommendations=tuple(recommendations),
        families_to_review=tuple(sorted(review)),
        metrics=metrics,
    )


def advanced_figure_candidate_gate(
    evidence_kind: str,
    *,
    material_gain: bool = False,
    readability_gain: bool = False,
    observations: int = 0,
    groups: int = 0,
    dimensions: int = 0,
    set_count: int = 0,
    time_points: int = 0,
    compositional_parts: int = 0,
    categorical_dimensions: int = 0,
    flow_stages: int = 0,
    has_edges: bool = False,
    paired: bool = False,
    paired_observations_available: bool = False,
    intersection_membership_available: bool = False,
    ordered_categories: bool = False,
    signed_values_available: bool = False,
    meaningful_zero: bool = False,
    shap_available: bool = False,
    contingency_table: bool = False,
    standardized_residuals_available: bool = False,
    has_flow_weights: bool = False,
    has_total_and_composition: bool = False,
    composition_closes: bool = False,
    continuous_inputs: int = 0,
    continuous_response: bool = False,
    response_grid: bool = False,
    readable_at_final_size: bool | None = None,
) -> AdvancedFigureCandidateGateResult:
    """Check every chart, but activate advanced candidates only on real gain.

    Evidence compatibility is evaluated first, followed by information gain and
    final-size readability. Portfolio variety and advanced appearance never
    override those criteria.
    """

    kind = str(evidence_kind).strip().lower().replace("-", "_")
    if not kind:
        raise ValueError("evidence_kind cannot be empty")
    aliases = {
        "distribution_comparison": "grouped_distribution",
        "multi_group_distribution": "grouped_distribution",
        "category_time_matrix": "categorical_matrix",
        "object_time_matrix": "categorical_matrix",
        "dense_scatter": "dense_bivariate",
        "joint_distribution": "dense_bivariate",
        "multi_metric_profile": "multivariate_profile",
        "solution_profile": "multivariate_profile",
        "network": "relational_network",
        "graph_structure": "relational_network",
        "before_after": "paired_change",
        "baseline_improved": "paired_change",
        "ranking_over_time": "rank_trajectory",
        "rank_over_time": "rank_trajectory",
        "three_part_composition": "composition",
        "mixture": "composition",
        "contingency_table": "categorical_association",
        "cross_tab": "categorical_association",
        "categorical_cross_tab": "categorical_association",
        "association_residuals": "residual_contribution",
        "standardized_residuals": "residual_contribution",
        "category_mapping": "categorical_flow",
        "category_transition": "categorical_flow",
        "stage_flow": "categorical_flow",
        "parallel_sets": "categorical_flow",
        "total_plus_composition": "total_composition",
        "magnitude_composition": "total_composition",
        "marimekko": "total_composition",
        "upset": "set_intersection",
        "multi_set_intersection": "set_intersection",
        "feature_selection_overlap": "set_intersection",
        "solution_overlap": "set_intersection",
        "corrgram": "pairwise_relationships",
        "pairwise_relationship_matrix": "pairwise_relationships",
        "multi_variable_relationships": "pairwise_relationships",
        "correlation_structure": "pairwise_relationships",
        "chord": "weighted_category_relations",
        "chord_diagram": "weighted_category_relations",
        "category_relations": "weighted_category_relations",
        "regional_flow_relations": "weighted_category_relations",
        "lollipop": "ordered_category_magnitudes",
        "ranked_categories": "ordered_category_magnitudes",
        "variable_importance": "ordered_category_magnitudes",
        "sensitivity_ranking": "ordered_category_magnitudes",
        "diverging_bar": "signed_category_effects",
        "bidirectional_bar": "signed_category_effects",
        "positive_negative_change": "signed_category_effects",
        "contribution_decomposition": "signed_category_effects",
        "model_explanation": "shap_explanation",
        "two_parameter_response": "response_surface",
        "parameter_response_surface": "response_surface",
    }
    kind = aliases.get(kind, kind)
    counts = {
        "observations": observations,
        "groups": groups,
        "dimensions": dimensions,
        "set_count": set_count,
        "time_points": time_points,
        "compositional_parts": compositional_parts,
        "categorical_dimensions": categorical_dimensions,
        "flow_stages": flow_stages,
        "continuous_inputs": continuous_inputs,
    }
    if any(int(value) < 0 for value in counts.values()):
        raise ValueError("numeric evidence descriptors cannot be negative")
    metrics = {key: float(value) for key, value in counts.items()}
    metrics.update(
        {
            "advanced_check_performed": 1.0,
            "material_gain": float(bool(material_gain)),
            "extra_information_dimension_confirmed": float(bool(material_gain)),
            "readability_gain": float(bool(readability_gain)),
            "contingency_table": float(bool(contingency_table)),
            "standardized_residuals_available": float(
                bool(standardized_residuals_available)
            ),
            "has_flow_weights": float(bool(has_flow_weights)),
            "has_total_and_composition": float(
                bool(has_total_and_composition)
            ),
            "composition_closes": float(bool(composition_closes)),
            "readable_at_final_size": (
                -1.0
                if readable_at_final_size is None
                else float(readable_at_final_size)
            ),
        }
    )

    candidates: list[str] = []
    issues: list[str] = []
    recommendations: list[str] = []

    if kind == "grouped_distribution":
        if observations >= 20 and groups >= 2:
            candidates.append("raincloud")
        if observations >= 30 and groups >= 3:
            candidates.append("ridgeline")
    elif kind == "categorical_matrix":
        candidates.append("bubble_matrix")
    elif kind == "dense_bivariate":
        if observations >= 200:
            candidates.append("hexbin")
        if observations >= 300:
            candidates.append("2d_kde_contour")
    elif kind == "multivariate_profile":
        if 4 <= dimensions <= 10:
            candidates.append("parallel_coordinates")
    elif kind == "relational_network":
        if has_edges:
            candidates.append("network_graph")
    elif kind == "paired_change":
        if paired:
            candidates.append("slope_dumbbell")
    elif kind == "rank_trajectory":
        if time_points >= 3:
            candidates.append("bump_chart")
    elif kind == "composition":
        if compositional_parts == 3:
            candidates.append("ternary")
    elif kind == "categorical_association":
        valid_table = categorical_dimensions == 2 and contingency_table
        if valid_table:
            candidates.append("mosaic_association_plot")
            if standardized_residuals_available:
                candidates.append("standardized_residual_bubble_plot")
            recommendations.append(
                "Use a mosaic/association view only when joint proportions and marginal structure add a real dimension beyond separate bars or a count heatmap."
            )
    elif kind == "residual_contribution":
        valid_residuals = (
            categorical_dimensions == 2
            and contingency_table
            and standardized_residuals_available
        )
        if valid_residuals:
            candidates.append("standardized_residual_bubble_plot")
            recommendations.append(
                "Encode standardized-residual sign and magnitude only when they are computed from the contingency model and are part of the claim."
            )
    elif kind == "categorical_flow":
        if flow_stages >= 2 and has_flow_weights:
            candidates.append("parallel_sets_alluvial")
            recommendations.append(
                "Use band continuity only for observed category mappings or transitions with real flow weights; otherwise keep aligned bars, dots, or a matrix."
            )
    elif kind == "total_composition":
        valid_marimekko = (
            compositional_parts >= 2
            and has_total_and_composition
            and composition_closes
        )
        if valid_marimekko:
            candidates.append("marimekko")
            recommendations.append(
                "Use width for group total and height for within-group composition only when both dimensions are required by the same claim."
            )
    elif kind == "set_intersection":
        valid_intersections = (
            3 <= set_count <= 12 and intersection_membership_available
        )
        if valid_intersections:
            candidates.append("upset_plot")
            recommendations.append(
                "Use UpSet only for real multi-set memberships and intersection sizes; keep Venn or a table for two sets or a very simple three-set overlap."
            )
    elif kind == "pairwise_relationships":
        valid_pairs = (
            4 <= dimensions <= 8
            and observations >= 30
            and paired_observations_available
        )
        if valid_pairs:
            candidates.append("corrgram_pairwise_relationship_matrix")
            recommendations.append(
                "Use aligned diagonal distributions, bivariate panels, and correlation summaries from the same paired rows; keep a correlation heatmap when cellwise coefficients alone answer the claim."
            )
    elif kind == "weighted_category_relations":
        valid_chord = (
            3 <= groups <= 12 and has_edges and has_flow_weights
        )
        if valid_chord:
            candidates.append("chord_diagram")
            recommendations.append(
                "Use a chord diagram only when weighted shared relations are the claim and the sector/ribbon count remains readable; prefer a matrix, network, or alluvial view for dense, path-oriented, or staged relations."
            )
    elif kind == "ordered_category_magnitudes":
        if 10 <= groups <= 30 and ordered_categories:
            candidates.append("lollipop_plot")
            recommendations.append(
                "Treat lollipop as a restrained dot-based alternative for an ordered 10–30 category comparison, not as an advancedness target; keep bars or dots when stems do not reduce visual weight or label crowding."
            )
    elif kind == "signed_category_effects":
        valid_diverging = (
            2 <= groups <= 30
            and signed_values_available
            and meaningful_zero
        )
        if valid_diverging:
            candidates.append("bidirectional_diverging_bar")
            recommendations.append(
                "Use a centered zero line only when sign has a real directional meaning; keep grouped bars or dumbbells for unrelated absolute measures."
            )
    elif kind == "shap_explanation":
        if shap_available:
            candidates.extend(("shap_beeswarm", "shap_dependence", "shap_waterfall"))
    elif kind == "response_surface":
        valid_surface = (
            continuous_inputs == 2 and continuous_response and response_grid
        )
        if valid_surface:
            candidates.append("3d_response_surface")
            recommendations.append(
                "Compare against an evidence-matched 2D contour or matrix view; use the 3D surface only when ridge, saddle, or interaction geometry adds information and remains readable in a static A4 figure."
            )
        else:
            issues.append(
                "THREE_D_RESPONSE_SURFACE_REQUIRES_TWO_CONTINUOUS_INPUTS_AND_CONTINUOUS_GRIDDED_RESPONSE"
            )
            recommendations.append(
                "Reject 3D and use the standard chart matched to the actual evidence."
            )
            return AdvancedFigureCandidateGateResult(
                status="REJECT_ADVANCED",
                candidates=(),
                issues=tuple(issues),
                recommendations=tuple(recommendations),
                metrics=metrics,
            )

    if not candidates:
        return AdvancedFigureCandidateGateResult(
            status="KEEP_STANDARD",
            candidates=(),
            issues=("EVIDENCE_STRUCTURE_DOES_NOT_SUPPORT_ADVANCED_CANDIDATE",),
            recommendations=(
                "Keep the standard chart selected by Claim -> Evidence -> Chart Type.",
            ),
            metrics=metrics,
        )
    gain_confirmed = (
        bool(readability_gain)
        if kind == "ordered_category_magnitudes"
        else bool(material_gain)
    )
    metrics["candidate_gain_confirmed"] = float(gain_confirmed)
    if not gain_confirmed:
        return AdvancedFigureCandidateGateResult(
            status="KEEP_STANDARD",
            candidates=tuple(candidates),
            issues=("NO_MATERIAL_INFORMATION_OR_STRUCTURE_GAIN",),
            recommendations=(
                "Keep the standard chart unless the candidate adds a real, claim-relevant information dimension; lollipop alone may instead qualify through a confirmed reduction in reading burden.",
            ),
            metrics=metrics,
        )
    if readable_at_final_size is not True:
        issue = (
            "ADVANCED_CANDIDATE_READABILITY_NOT_CONFIRMED"
            if readable_at_final_size is None
            else "ADVANCED_CANDIDATE_FAILS_FINAL_SIZE_READABILITY"
        )
        return AdvancedFigureCandidateGateResult(
            status="KEEP_STANDARD",
            candidates=tuple(candidates),
            issues=(issue,),
            recommendations=(
                "Keep the evidence-matched standard chart until the advanced candidate is explicitly confirmed readable at final A4 size.",
            ),
            metrics=metrics,
        )
    if not recommendations:
        recommendations.append(
            "Compare the candidate with the standard chart at final A4 size and retain it only if the claim becomes easier to verify."
        )
    elif kind != "response_surface":
        recommendations.append(
            "Compare the candidate with the evidence-matched standard chart at final A4 size; choose KEEP_STANDARD if verification is not faster or more informative."
        )
    return AdvancedFigureCandidateGateResult(
        status="CONSIDER_ADVANCED",
        candidates=tuple(candidates),
        issues=(),
        recommendations=tuple(recommendations),
        metrics=metrics,
    )


def suggest_sampling_grid(
    existing_x: Iterable[float], *, target_points: int = 9, max_points: int = 21
) -> np.ndarray:
    """Suggest parameter positions only; response values must be recomputed."""

    values = np.unique(_finite_1d(existing_x, name="existing_x"))
    if values.size < 2 or float(np.ptp(values)) <= 0:
        raise ValueError("existing_x must contain at least two distinct values")
    if not 5 <= target_points <= max_points <= 21:
        raise ValueError("require 5 <= target_points <= max_points <= 21")
    if values.size >= target_points:
        return values.copy()
    return np.linspace(float(values.min()), float(values.max()), target_points)


def suggest_interval_xlim(
    intervals: Iterable[Sequence[float]],
    *,
    estimates: Iterable[float] | None = None,
    pad_fraction: float = 0.15,
) -> tuple[float, float]:
    """Return a focused numeric range around an interval envelope."""

    values = _interval_array(intervals)
    lower = float(values[:, 0].min())
    upper = float(values[:, 1].max())
    if estimates is not None:
        centers = _finite_1d(estimates, name="estimates")
        lower = min(lower, float(centers.min()))
        upper = max(upper, float(centers.max()))
    if not 0.05 <= pad_fraction <= 0.5:
        raise ValueError("pad_fraction must be between 0.05 and 0.5")
    span = upper - lower
    if span <= 0:
        magnitude = max(abs(lower), 1.0)
        span = 0.02 * magnitude
    pad = max(span * pad_fraction, np.finfo(float).eps)
    return lower - pad, upper + pad


def focus_interval_axis(
    ax: Axes,
    intervals: Iterable[Sequence[float]],
    *,
    estimates: Iterable[float] | None = None,
    pad_fraction: float = 0.15,
    reference_value: float | None = 0.0,
    reference_label: str = "零基准",
    annotate_off_axis: bool = True,
) -> tuple[float, float]:
    """Focus an interval/forest axis and disclose an off-view reference value."""

    limits = suggest_interval_xlim(
        intervals, estimates=estimates, pad_fraction=pad_fraction
    )
    ax.set_xlim(*limits)
    if reference_value is None:
        return limits
    reference = float(reference_value)
    if limits[0] <= reference <= limits[1]:
        ax.axvline(
            reference,
            color=SEMANTIC_COLORS["baseline"],
            linewidth=0.9,
            linestyle="--",
            zorder=0,
        )
    elif annotate_off_axis:
        side = "左侧" if reference < limits[0] else "右侧"
        horizontal = "left" if side == "左侧" else "right"
        x_position = 0.01 if side == "左侧" else 0.99
        ax.text(
            x_position,
            0.98,
            f"{reference_label} {reference:g} 位于图外{side}",
            transform=ax.transAxes,
            ha=horizontal,
            va="top",
            color=SEMANTIC_COLORS["baseline"],
            fontsize=7.5,
        )
    return limits


def annotate_point_safely(
    ax: Axes,
    x: float,
    y: float,
    text: str,
    *,
    offset_points: float = 7.0,
    arrow: bool = False,
    **kwargs,
):
    """Place a point label inward when the point is near an axis boundary."""

    x_bounds = _validated_axis_limits(ax.get_xlim(), name="x limits")
    y_bounds = _validated_axis_limits(ax.get_ylim(), name="y limits")
    x_norm = (float(x) - x_bounds[0]) / (x_bounds[1] - x_bounds[0])
    y_norm = (float(y) - y_bounds[0]) / (y_bounds[1] - y_bounds[0])

    if x_norm <= 0.12:
        dx, horizontal = offset_points, "left"
    elif x_norm >= 0.88:
        dx, horizontal = -offset_points, "right"
    else:
        dx, horizontal = 0.0, "center"
    if y_norm <= 0.18:
        dy, vertical = offset_points, "bottom"
    elif y_norm >= 0.82:
        dy, vertical = -offset_points, "top"
    else:
        dy, vertical = offset_points, "bottom"

    annotation_kwargs = {
        "xytext": (dx, dy),
        "textcoords": "offset points",
        "ha": horizontal,
        "va": vertical,
        "color": SEMANTIC_COLORS["text"],
        "clip_on": False,
    }
    if arrow:
        annotation_kwargs["arrowprops"] = {
            "arrowstyle": "-",
            "color": SEMANTIC_COLORS["baseline"],
            "linewidth": 0.7,
        }
    annotation_kwargs.update(kwargs)
    return ax.annotate(text, xy=(x, y), **annotation_kwargs)


def _gaussian_kde(samples: np.ndarray, grid: np.ndarray) -> np.ndarray:
    std = float(np.std(samples, ddof=1))
    if not np.isfinite(std) or std <= 0:
        return np.zeros_like(grid)
    bandwidth = max(1.06 * std * samples.size ** (-1 / 5), np.finfo(float).eps)
    scaled = (grid[:, None] - samples[None, :]) / bandwidth
    return np.exp(-0.5 * scaled**2).mean(axis=1) / (
        bandwidth * np.sqrt(2 * np.pi)
    )


def plot_tail_risk_distribution(
    ax: Axes,
    samples: Iterable[float],
    *,
    alpha: float = 0.05,
    bins: str | int | Sequence[float] = "fd",
    xlabel: str = "收益",
    show_kde: bool = True,
    labels: Mapping[str, str] | None = None,
) -> dict[str, float]:
    """Plot empirical lower-tail evidence with mean, VaR, and CVaR."""

    values = _finite_1d(samples, name="samples")
    if values.size < 20:
        raise ValueError("tail-risk distribution needs at least 20 finite samples")
    if not 0 < alpha < 0.5:
        raise ValueError("alpha must be between 0 and 0.5")

    mean_value = float(np.mean(values))
    var_value = float(np.quantile(values, alpha))
    tail = values[values <= var_value]
    cvar_value = float(np.mean(tail))
    text = {
        "samples": "经验样本",
        "kde": "KDE",
        "mean": "均值",
        "var": "VaR",
        "cvar": "CVaR",
        "density": "概率密度",
    }
    if labels:
        text.update(labels)

    counts, edges, patches = ax.hist(
        values,
        bins=bins,
        density=True,
        color=SEMANTIC_COLORS["neutral"],
        alpha=0.55,
        edgecolor="none",
        label="_nolegend_",
    )
    if patches:
        patches[-1].set_label(text["samples"])
    for left, right, patch in zip(edges[:-1], edges[1:], patches):
        if left < var_value:
            patch.set_facecolor(SEMANTIC_COLORS["risk_tail"])
            patch.set_alpha(0.9 if right <= var_value else 0.65)

    if show_kde and np.std(values) > 0:
        padding = 0.06 * (values.max() - values.min())
        grid = np.linspace(values.min() - padding, values.max() + padding, 512)
        density = _gaussian_kde(values, grid)
        ax.plot(
            grid,
            density,
            color=SEMANTIC_COLORS["primary"],
            linewidth=1.7,
            label=text["kde"],
        )
        mask = grid <= var_value
        ax.fill_between(
            grid[mask],
            0,
            density[mask],
            color=SEMANTIC_COLORS["risk"],
            alpha=0.18,
            linewidth=0,
        )

    ax.axvline(
        mean_value,
        color=SEMANTIC_COLORS["baseline"],
        linewidth=1.1,
        linestyle="--",
        label=f"{text['mean']} = {mean_value:.2f}",
    )
    ax.axvline(
        var_value,
        color=SEMANTIC_COLORS["risk"],
        linewidth=1.3,
        linestyle="--",
        label=f"{text['var']} {alpha:.0%} = {var_value:.2f}",
    )
    ax.axvline(
        cvar_value,
        color=SEMANTIC_COLORS["risk"],
        linewidth=1.1,
        linestyle=":",
        label=f"{text['cvar']} {alpha:.0%} = {cvar_value:.2f}",
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(text["density"])
    style_axis(ax, grid="y")
    ax.legend(loc="best")
    return {"mean": mean_value, "var": var_value, "cvar": cvar_value}


def plot_risk_interval_comparison(
    ax: Axes,
    names: Sequence[str],
    means: Iterable[float],
    lower_quantiles: Iterable[float],
    cvars: Iterable[float],
    *,
    xlabel: str = "收益",
    labels: Mapping[str, str] | None = None,
) -> None:
    """Plot summary risk indicators without falsely calling them a distribution."""

    mean_values = _finite_1d(means, name="means")
    quantile_values = _finite_1d(lower_quantiles, name="lower_quantiles")
    cvar_values = _finite_1d(cvars, name="cvars")
    size = len(names)
    if not (mean_values.size == quantile_values.size == cvar_values.size == size):
        raise ValueError("names and all numeric sequences must have equal length")
    text = {"mean": "均值", "quantile": "下分位数", "cvar": "CVaR"}
    if labels:
        text.update(labels)

    y = np.arange(size)
    left = np.minimum(quantile_values, cvar_values)
    for yi, lo, hi in zip(y, left, mean_values):
        ax.hlines(yi, lo, hi, color=SEMANTIC_COLORS["baseline"], linewidth=1.0)
    ax.scatter(
        mean_values,
        y,
        s=28,
        color=SEMANTIC_COLORS["primary"],
        label=text["mean"],
        zorder=3,
    )
    ax.scatter(
        quantile_values,
        y,
        s=28,
        marker="D",
        color=SEMANTIC_COLORS["risk"],
        label=text["quantile"],
        zorder=3,
    )
    ax.scatter(
        cvar_values,
        y,
        s=32,
        marker="x",
        linewidth=1.2,
        color=SEMANTIC_COLORS["risk"],
        label=text["cvar"],
        zorder=3,
    )
    ax.set_yticks(y, labels=list(names))
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    style_axis(ax, grid="x")
    ax.legend(loc="best")


def _full_span_chart_kind(chart_kind: str) -> str:
    raw = str(chart_kind).strip().lower().replace("-", " ").replace("%", " percent ")
    kind = "_".join(raw.split())
    aliases = {
        "mekko": "marimekko",
        "mosaic_bar": "marimekko",
        "100_percent_stacked": "100_percent_stacked_bar",
        "100_percent_stacked_bar": "100_percent_stacked_bar",
        "percent_stacked_bar": "100_percent_stacked_bar",
    }
    normalized = aliases.get(kind, kind)
    if normalized not in {"marimekko", "100_percent_stacked_bar"}:
        raise ValueError(
            "chart_kind must be 'marimekko' or '100_percent_stacked_bar'"
        )
    return normalized


def lock_full_span_composition_axis(
    ax: Axes,
    *,
    chart_kind: str = "100_percent_stacked_bar",
    orientation: str = "vertical",
    percent_max: float = 100.0,
    total_bounds: Sequence[float] | None = None,
) -> Mapping[str, tuple[float, float]]:
    """Lock theoretical composition bounds and remove autoscale whitespace.

    ``total_bounds`` is required for Marimekko because its second axis encodes
    real group totals. Labels should be placed with annotations after this call,
    never by expanding these limits.
    """

    kind = _full_span_chart_kind(chart_kind)
    direction = str(orientation).strip().lower()
    if direction not in {"vertical", "horizontal"}:
        raise ValueError("orientation must be 'vertical' or 'horizontal'")
    cap = float(percent_max)
    if not np.isfinite(cap) or cap <= 0:
        raise ValueError("percent_max must be a positive finite value")

    if direction == "vertical":
        ax.margins(y=0)
        ax.set_ylim(0.0, cap)
    else:
        ax.margins(x=0)
        ax.set_xlim(0.0, cap)

    normalized_total: tuple[float, float] | None = None
    if kind == "marimekko":
        if total_bounds is None:
            raise ValueError("total_bounds are required for a Marimekko axis")
        normalized_total = _validated_limits(total_bounds, name="total_bounds")
        if direction == "vertical":
            ax.margins(x=0)
            ax.set_xlim(*normalized_total)
        else:
            ax.margins(y=0)
            ax.set_ylim(*normalized_total)

    spec = {
        "chart_kind": kind,
        "orientation": direction,
        "percent_max": cap,
        "total_bounds": normalized_total,
    }
    setattr(ax, "_cumcm_full_span_composition_spec", spec)
    return {
        "x": tuple(float(value) for value in ax.get_xlim()),
        "y": tuple(float(value) for value in ax.get_ylim()),
    }


def annotate_composition_boundary(
    ax: Axes,
    position: float,
    text: str,
    *,
    edge: str = "top",
    offset_points: float = 5.0,
    **kwargs,
):
    """Annotate inward from a full-span boundary without changing axis limits."""

    side = str(edge).strip().lower()
    if side not in {"top", "bottom", "left", "right"}:
        raise ValueError("edge must be 'top', 'bottom', 'left', or 'right'")
    x_bounds = _validated_axis_limits(ax.get_xlim(), name="x limits")
    y_bounds = _validated_axis_limits(ax.get_ylim(), name="y limits")
    offset = abs(float(offset_points))
    if side == "top":
        xy = (float(position), y_bounds[1])
        xytext, horizontal, vertical = (0.0, -offset), "center", "top"
    elif side == "bottom":
        xy = (float(position), y_bounds[0])
        xytext, horizontal, vertical = (0.0, offset), "center", "bottom"
    elif side == "left":
        xy = (x_bounds[0], float(position))
        xytext, horizontal, vertical = (offset, 0.0), "left", "center"
    else:
        xy = (x_bounds[1], float(position))
        xytext, horizontal, vertical = (-offset, 0.0), "right", "center"

    annotation_kwargs = {
        "xytext": xytext,
        "textcoords": "offset points",
        "ha": horizontal,
        "va": vertical,
        "color": SEMANTIC_COLORS["text"],
        "annotation_clip": False,
        "clip_on": False,
    }
    annotation_kwargs.update(kwargs)
    return ax.annotate(text, xy=xy, **annotation_kwargs)


def audit_full_span_composition_axis(
    ax: Axes,
    *,
    chart_kind: str = "100_percent_stacked_bar",
    orientation: str = "vertical",
    percent_max: float = 100.0,
    total_bounds: Sequence[float] | None = None,
    atol: float = 1e-9,
) -> list[str]:
    """Return QA issues when a theoretical 100% boundary is not flush."""

    kind = _full_span_chart_kind(chart_kind)
    direction = str(orientation).strip().lower()
    if direction not in {"vertical", "horizontal"}:
        raise ValueError("orientation must be 'vertical' or 'horizontal'")
    cap = float(percent_max)
    if not np.isfinite(cap) or cap <= 0:
        raise ValueError("percent_max must be a positive finite value")
    if atol < 0:
        raise ValueError("atol cannot be negative")

    x_margin, y_margin = ax.margins()
    percent_limits = ax.get_ylim() if direction == "vertical" else ax.get_xlim()
    percent_margin = y_margin if direction == "vertical" else x_margin
    issues: list[str] = []
    if not np.allclose(percent_limits, (0.0, cap), rtol=0.0, atol=atol):
        issues.append("FULL_SPAN_COMPOSITION_PERCENT_AXIS_NOT_LOCKED")
    if not np.isclose(percent_margin, 0.0, rtol=0.0, atol=atol):
        issues.append("FULL_SPAN_COMPOSITION_PERCENT_MARGIN_NOT_ZERO")

    if kind == "marimekko":
        if total_bounds is None:
            raise ValueError("total_bounds are required for Marimekko QA")
        expected_total = _validated_limits(total_bounds, name="total_bounds")
        total_limits = ax.get_xlim() if direction == "vertical" else ax.get_ylim()
        total_margin = x_margin if direction == "vertical" else y_margin
        if not np.allclose(
            total_limits, expected_total, rtol=0.0, atol=atol
        ):
            issues.append("MARIMEKKO_TOTAL_AXIS_NOT_LOCKED")
        if not np.isclose(total_margin, 0.0, rtol=0.0, atol=atol):
            issues.append("MARIMEKKO_TOTAL_MARGIN_NOT_ZERO")
    return issues


def audit_figure(
    fig: Figure, *, min_font_size: float = MIN_FINAL_FONT_PT
) -> list[str]:
    """Return machine-detectable warnings; never replaces visual inspection."""

    issues: list[str] = []
    for item in fig.findobj(match=Text):
        if item.get_visible() and item.get_text().strip():
            if item.get_fontsize() < min_font_size:
                issues.append(
                    f"TEXT_TOO_SMALL:{item.get_text()!r}:{item.get_fontsize():.1f}pt"
                )
    if len(fig.axes) > 6:
        issues.append(f"TOO_MANY_PANELS:{len(fig.axes)}")
    for ax_index, ax in enumerate(fig.axes):
        legend = ax.get_legend()
        if legend and len(legend.get_texts()) > 6:
            issues.append(
                f"LEGEND_TOO_DENSE:axis={ax_index}:items={len(legend.get_texts())}"
            )
        for line in ax.lines:
            if line.get_linewidth() > 3.0:
                issues.append(
                    f"LINE_TOO_HEAVY:axis={ax_index}:lw={line.get_linewidth():.1f}"
                )
        full_span_spec = getattr(ax, "_cumcm_full_span_composition_spec", None)
        if full_span_spec:
            for issue in audit_full_span_composition_axis(ax, **full_span_spec):
                issues.append(f"{issue}:axis={ax_index}")
    return issues


def finalize_figure(
    fig: Figure,
    output_stem: str | Path,
    *,
    formats: Sequence[str] = ("pdf", "png"),
    dpi: int = 400,
    close: bool = False,
) -> tuple[Path, ...]:
    """Export vector + raster outputs with stable publication settings."""

    if dpi < 300:
        raise ValueError("publication PNG dpi must be at least 300")
    normalized = tuple(str(fmt).lower().lstrip(".") for fmt in formats)
    invalid = set(normalized) - SUPPORTED_FORMATS
    if invalid:
        raise ValueError(f"unsupported formats: {sorted(invalid)}")
    if not normalized:
        raise ValueError("formats cannot be empty")

    base = Path(output_stem)
    if base.suffix.lower().lstrip(".") in SUPPORTED_FORMATS:
        base = base.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()

    saved: list[Path] = []
    for fmt in normalized:
        path = base.with_suffix(f".{fmt}")
        kwargs = {
            "format": fmt,
            "bbox_inches": "tight",
            "pad_inches": 0.04,
            "facecolor": "white",
            "transparent": False,
        }
        if fmt == "png":
            kwargs["dpi"] = dpi
        fig.savefig(path, **kwargs)
        saved.append(path)
    if close:
        plt.close(fig)
    return tuple(saved)


__all__ = [
    "A4_FULL_WIDTH_IN",
    "A4_HALF_WIDTH_IN",
    "AdvancedFigureCandidateGateResult",
    "DensityGateResult",
    "EvidenceRichnessGateResult",
    "FIGURE_DECISION_PRIORITY",
    "FigureStyle",
    "FigurePortfolioGateResult",
    "SEMANTIC_COLORS",
    "add_panel_labels",
    "annotate_composition_boundary",
    "annotate_point_safely",
    "advanced_figure_candidate_gate",
    "apply_publication_style",
    "audit_figure",
    "audit_full_span_composition_axis",
    "bar_width",
    "create_subplots",
    "evidence_richness_gate",
    "finalize_figure",
    "focus_interval_axis",
    "figure_portfolio_gate",
    "grouped_positions",
    "lock_full_span_composition_axis",
    "plot_risk_interval_comparison",
    "plot_tail_risk_distribution",
    "style_axis",
    "suggest_interval_xlim",
    "suggest_sampling_grid",
    "visual_information_density_gate",
]

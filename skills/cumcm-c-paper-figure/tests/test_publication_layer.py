from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np

from cumcm_figure_style import (
    FIGURE_DECISION_PRIORITY,
    SEMANTIC_COLORS,
    advanced_figure_candidate_gate,
    annotate_composition_boundary,
    annotate_point_safely,
    apply_publication_style,
    audit_figure,
    audit_full_span_composition_axis,
    bar_width,
    create_subplots,
    evidence_richness_gate,
    finalize_figure,
    figure_portfolio_gate,
    focus_interval_axis,
    grouped_positions,
    lock_full_span_composition_axis,
    plot_risk_interval_comparison,
    plot_tail_risk_distribution,
    suggest_interval_xlim,
    suggest_sampling_grid,
    visual_information_density_gate,
)
from render_a4_preview import render_a4_preview


class PublicationLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        apply_publication_style()

    def tearDown(self) -> None:
        plt.close("all")

    def test_semantic_palette_has_stable_roles(self) -> None:
        expected = {
            "primary",
            "secondary",
            "comparison",
            "improvement",
            "risk",
            "baseline",
            "neutral",
            "uncertainty",
            "risk_tail",
        }
        self.assertTrue(expected.issubset(SEMANTIC_COLORS))
        self.assertEqual(len({SEMANTIC_COLORS[key] for key in expected}), len(expected))

    def test_figure_decision_priority_is_evidence_first(self) -> None:
        self.assertEqual(
            FIGURE_DECISION_PRIORITY,
            (
                "evidence_match",
                "information_expression",
                "readability",
                "portfolio_diversity",
                "advanced_appearance",
            ),
        )

    def test_bar_geometry_is_restrained(self) -> None:
        self.assertGreaterEqual(bar_width(1), 0.45)
        self.assertLessEqual(bar_width(1), 0.60)
        for series_count in (2, 3, 4, 5):
            positions, width = grouped_positions(4, series_count)
            self.assertLess(width, bar_width(1))
            self.assertLessEqual(width * series_count, 0.72 + 1e-12)
            self.assertEqual(len(positions), series_count)

    def test_tail_risk_uses_samples_and_returns_consistent_stats(self) -> None:
        rng = np.random.default_rng(20260828)
        samples = np.concatenate(
            [rng.normal(105, 9, 900), rng.normal(72, 8, 100)]
        )
        fig, axes = create_subplots(width="full", height=3.5)
        stats = plot_tail_risk_distribution(
            axes[0],
            samples,
            alpha=0.05,
            xlabel="Profit",
            labels={
                "samples": "Samples",
                "mean": "Mean",
                "density": "Density",
            },
        )
        expected_var = float(np.quantile(samples, 0.05))
        expected_cvar = float(samples[samples <= expected_var].mean())
        self.assertAlmostEqual(stats["var"], expected_var)
        self.assertAlmostEqual(stats["cvar"], expected_cvar)
        self.assertLess(stats["cvar"], stats["var"])
        with tempfile.TemporaryDirectory() as tmp:
            saved = finalize_figure(fig, Path(tmp) / "tail_risk", close=False)
            self.assertEqual({path.suffix for path in saved}, {".pdf", ".png"})

    def test_tail_risk_rejects_summary_sized_input(self) -> None:
        fig, axes = create_subplots()
        with self.assertRaises(ValueError):
            plot_tail_risk_distribution(axes[0], [100, 80, 70])

    def test_summary_risk_uses_interval_comparison(self) -> None:
        fig, axes = create_subplots(width="full", height=2.8)
        plot_risk_interval_comparison(
            axes[0],
            ["Plan A", "Plan B"],
            [105, 101],
            [82, 87],
            [76, 80],
        )
        self.assertGreaterEqual(len(axes[0].collections), 5)

    def test_fig6_sparse_frontier_requests_real_resampling(self) -> None:
        result = visual_information_density_gate(
            "risk_frontier",
            x=[0.0, 0.2, 0.4],
            axis_limits=(0.0, 0.4),
            y_limits=(3998.0, 4079.0),
            annotated_points=[(0.4, 4001.44)],
        )
        self.assertEqual(result.status, "RESAMPLE")
        self.assertIn("CONTINUOUS_CURVE_TOO_SPARSE", result.issues)
        self.assertIn("ANNOTATION_NEAR_AXIS_BOUNDARY", result.issues)
        self.assertEqual(result.metrics["unique_x_count"], 3.0)

        grid = suggest_sampling_grid([0.0, 0.2, 0.4], target_points=9)
        np.testing.assert_allclose(grid, np.arange(0.0, 0.401, 0.05))
        self.assertEqual(grid.ndim, 1)

    def test_dense_frontier_passes_density_gate(self) -> None:
        result = visual_information_density_gate(
            "risk_frontier",
            x=np.linspace(0.0, 0.4, 9),
            axis_limits=(0.0, 0.4),
        )
        self.assertTrue(result.passed)

    def test_complementary_distribution_evidence_composes_as_layers(self) -> None:
        result = evidence_richness_gate(
            ["empirical_distribution", "kde", "var_threshold", "risk_region"],
            current_layers=["empirical_distribution"],
            relationship="complementary",
            same_claim=True,
            same_object=True,
            shared_coordinate=True,
        )
        self.assertEqual(result.status, "COMPOSE_LAYER")
        self.assertEqual(result.composition, "layer")
        self.assertEqual(
            result.missing_evidence,
            ("kde", "var_threshold", "risk_region"),
        )

    def test_complementary_different_scales_use_aligned_panels(self) -> None:
        result = evidence_richness_gate(
            ["prediction_trace", "residual_diagnostics"],
            current_layers=["prediction_trace"],
            relationship="complementary",
            shared_coordinate=False,
        )
        self.assertEqual(result.status, "COMPOSE_PANEL")
        self.assertEqual(result.composition, "panel")

    def test_independent_evidence_is_not_forced_into_composite(self) -> None:
        result = evidence_richness_gate(
            ["ranking", "model_runtime"],
            relationship="independent",
        )
        self.assertEqual(result.status, "KEEP_SEPARATE")
        self.assertTrue(result.passed)

    def test_portfolio_reviews_mixed_evidence_but_allows_justified_repeat(self) -> None:
        mixed = [
            {"figure_id": "fig1", "chart_family": "line", "evidence_kind": "time_series"},
            {"figure_id": "fig2", "chart_family": "line", "evidence_kind": "parameter_sweep"},
            {"figure_id": "fig3", "chart_family": "line", "evidence_kind": "summary_metrics"},
            {"figure_id": "fig4", "chart_family": "heatmap", "evidence_kind": "correlation_matrix"},
            {"figure_id": "fig5", "chart_family": "interval", "evidence_kind": "effect_interval"},
        ]
        review = figure_portfolio_gate(mixed)
        self.assertEqual(review.status, "REVIEW")
        self.assertEqual(review.families_to_review, ("line",))

        repeated_but_justified = [
            {"figure_id": "fig1", "chart_family": "line", "evidence_kind": "time_series"},
            {"figure_id": "fig2", "chart_family": "line", "evidence_kind": "time_series"},
            {"figure_id": "fig3", "chart_family": "line", "evidence_kind": "time_series"},
            {"figure_id": "fig4", "chart_family": "heatmap", "evidence_kind": "correlation_matrix"},
        ]
        self.assertTrue(figure_portfolio_gate(repeated_but_justified).passed)

        for item in mixed[:3]:
            item["selection_confirmed"] = True
        self.assertTrue(figure_portfolio_gate(mixed).passed)

    def test_portfolio_rechecks_adjacent_multi_series_charts_without_forcing_change(self) -> None:
        figures_8_and_9 = [
            {
                "figure_id": "fig8",
                "chart_family": "multi_series_line",
                "evidence_kind": "replenishment_time_series",
                "series_count": 6,
            },
            {
                "figure_id": "fig9",
                "chart_family": "multi_series_line",
                "evidence_kind": "category_date_pricing_matrix",
                "series_count": 6,
            },
        ]
        review = figure_portfolio_gate(figures_8_and_9)
        self.assertEqual(review.status, "REVIEW")
        self.assertIn(
            "SIMILAR_MULTI_SERIES_SEQUENCE_NEEDS_ALTERNATIVE_CHECK",
            review.issues,
        )
        self.assertEqual(review.families_to_review, ("line",))

        figures_8_and_9[1]["chart_family"] = "heatmap"
        figures_8_and_9[1]["series_count"] = 1
        self.assertTrue(figure_portfolio_gate(figures_8_and_9).passed)

        repeated_but_confirmed = [
            {**item, "chart_family": "multi_series_line", "series_count": 6,
             "selection_confirmed": True}
            for item in figures_8_and_9
        ]
        self.assertTrue(figure_portfolio_gate(repeated_but_confirmed).passed)

        repeated_bars = [
            {"figure_id": "fig4", "chart_family": "grouped_bar",
             "evidence_kind": "category_totals", "series_count": 3},
            {"figure_id": "fig5", "chart_family": "grouped_bar",
             "evidence_kind": "paired_change", "series_count": 3},
        ]
        self.assertEqual(figure_portfolio_gate(repeated_bars).status, "REVIEW")

    def test_portfolio_also_reviews_heatmap_overuse(self) -> None:
        heatmap_everywhere = [
            {"figure_id": "fig1", "chart_family": "heatmap",
             "evidence_kind": "time_series"},
            {"figure_id": "fig2", "chart_family": "heatmap",
             "evidence_kind": "category_totals"},
            {"figure_id": "fig3", "chart_family": "heatmap",
             "evidence_kind": "effect_intervals"},
            {"figure_id": "fig4", "chart_family": "dot",
             "evidence_kind": "point_estimates"},
        ]
        review = figure_portfolio_gate(heatmap_everywhere)
        self.assertEqual(review.status, "REVIEW")
        self.assertIn("heatmap", review.families_to_review)
        self.assertIn("HEATMAP_OVERUSE_NEEDS_EVIDENCE_RECHECK", review.issues)

        for item in heatmap_everywhere[:3]:
            item["selection_confirmed"] = True
        self.assertTrue(figure_portfolio_gate(heatmap_everywhere).passed)

        two_mixed_heatmaps = heatmap_everywhere[:2] + [heatmap_everywhere[3]]
        for item in two_mixed_heatmaps[:2]:
            item["selection_confirmed"] = False
        review_two = figure_portfolio_gate(two_mixed_heatmaps)
        self.assertEqual(review_two.status, "REVIEW")
        self.assertIn(
            "CONSECUTIVE_HEATMAPS_CROSS_MIXED_EVIDENCE", review_two.issues
        )

        justified_heatmaps = [
            {"figure_id": f"matrix_{index}", "chart_family": "heatmap",
             "evidence_kind": "category_time_matrix"}
            for index in range(3)
        ]
        self.assertTrue(figure_portfolio_gate(justified_heatmaps).passed)

    def test_portfolio_does_not_penalize_evidence_matched_basic_charts(self) -> None:
        for family, evidence in (
            ("line", "time_series"),
            ("bar", "category_totals"),
            ("dot", "point_estimates"),
        ):
            figures = [
                {"figure_id": f"{family}_{index}", "chart_family": family,
                 "evidence_kind": evidence}
                for index in range(3)
            ]
            with self.subTest(family=family):
                self.assertTrue(figure_portfolio_gate(figures).passed)

    def test_advanced_candidate_gate_routes_supported_evidence_structures(self) -> None:
        cases = [
            (
                "grouped_distribution",
                {"observations": 60, "groups": 4},
                {"raincloud", "ridgeline"},
            ),
            ("categorical_matrix", {}, {"bubble_matrix"}),
            (
                "dense_bivariate",
                {"observations": 500},
                {"hexbin", "2d_kde_contour"},
            ),
            ("multivariate_profile", {"dimensions": 6}, {"parallel_coordinates"}),
            ("relational_network", {"has_edges": True}, {"network_graph"}),
            ("paired_change", {"paired": True}, {"slope_dumbbell"}),
            ("rank_trajectory", {"time_points": 5}, {"bump_chart"}),
            ("composition", {"compositional_parts": 3}, {"ternary"}),
            (
                "categorical_association",
                {
                    "categorical_dimensions": 2,
                    "contingency_table": True,
                    "standardized_residuals_available": True,
                },
                {"mosaic_association_plot", "standardized_residual_bubble_plot"},
            ),
            (
                "residual_contribution",
                {
                    "categorical_dimensions": 2,
                    "contingency_table": True,
                    "standardized_residuals_available": True,
                },
                {"standardized_residual_bubble_plot"},
            ),
            (
                "categorical_flow",
                {"flow_stages": 3, "has_flow_weights": True},
                {"parallel_sets_alluvial"},
            ),
            (
                "total_composition",
                {
                    "compositional_parts": 4,
                    "has_total_and_composition": True,
                    "composition_closes": True,
                },
                {"marimekko"},
            ),
            (
                "set_intersection",
                {
                    "set_count": 6,
                    "intersection_membership_available": True,
                },
                {"upset_plot"},
            ),
            (
                "pairwise_relationships",
                {
                    "dimensions": 6,
                    "observations": 120,
                    "paired_observations_available": True,
                },
                {"corrgram_pairwise_relationship_matrix"},
            ),
            (
                "weighted_category_relations",
                {"groups": 8, "has_edges": True, "has_flow_weights": True},
                {"chord_diagram"},
            ),
            (
                "ordered_category_magnitudes",
                {
                    "groups": 18,
                    "ordered_categories": True,
                    "readability_gain": True,
                },
                {"lollipop_plot"},
            ),
            (
                "signed_category_effects",
                {
                    "groups": 8,
                    "signed_values_available": True,
                    "meaningful_zero": True,
                },
                {"bidirectional_diverging_bar"},
            ),
            (
                "shap_explanation",
                {"shap_available": True},
                {"shap_beeswarm", "shap_dependence", "shap_waterfall"},
            ),
        ]
        for evidence_kind, kwargs, expected in cases:
            with self.subTest(evidence_kind=evidence_kind):
                result = advanced_figure_candidate_gate(
                    evidence_kind,
                    material_gain=True,
                    readable_at_final_size=True,
                    **kwargs,
                )
                self.assertEqual(result.status, "CONSIDER_ADVANCED")
                self.assertTrue(expected.issubset(result.candidates))

    def test_advanced_candidate_gate_requires_material_gain(self) -> None:
        result = advanced_figure_candidate_gate(
            "categorical_matrix", material_gain=False
        )
        self.assertEqual(result.status, "KEEP_STANDARD")
        self.assertEqual(result.candidates, ("bubble_matrix",))
        self.assertIn("NO_MATERIAL_INFORMATION_OR_STRUCTURE_GAIN", result.issues)

    def test_categorical_candidates_require_complete_contract_and_real_gain(self) -> None:
        incomplete = advanced_figure_candidate_gate(
            "categorical_association",
            categorical_dimensions=2,
            contingency_table=False,
            material_gain=True,
            readable_at_final_size=True,
        )
        self.assertEqual(incomplete.status, "KEEP_STANDARD")
        self.assertEqual(incomplete.candidates, ())

        no_extra_dimension = advanced_figure_candidate_gate(
            "total_plus_composition",
            compositional_parts=3,
            has_total_and_composition=True,
            composition_closes=True,
            material_gain=False,
            readable_at_final_size=True,
        )
        self.assertEqual(no_extra_dimension.status, "KEEP_STANDARD")
        self.assertEqual(no_extra_dimension.candidates, ("marimekko",))
        self.assertEqual(
            no_extra_dimension.metrics["extra_information_dimension_confirmed"],
            0.0,
        )

    def test_bioladder_inspired_candidates_require_complete_evidence_contracts(self) -> None:
        incomplete_cases = [
            ("upset", {"set_count": 6}),
            (
                "corrgram",
                {
                    "dimensions": 6,
                    "observations": 120,
                    "paired_observations_available": False,
                },
            ),
            (
                "chord",
                {"groups": 8, "has_edges": True, "has_flow_weights": False},
            ),
            ("lollipop", {"groups": 18, "ordered_categories": False}),
            (
                "diverging_bar",
                {
                    "groups": 8,
                    "signed_values_available": True,
                    "meaningful_zero": False,
                },
            ),
        ]
        for evidence_kind, kwargs in incomplete_cases:
            with self.subTest(evidence_kind=evidence_kind):
                result = advanced_figure_candidate_gate(
                    evidence_kind,
                    material_gain=True,
                    readable_at_final_size=True,
                    **kwargs,
                )
                self.assertEqual(result.status, "KEEP_STANDARD")
                self.assertEqual(result.candidates, ())

    def test_lollipop_can_qualify_only_through_confirmed_readability_gain(self) -> None:
        kept = advanced_figure_candidate_gate(
            "variable_importance",
            groups=18,
            ordered_categories=True,
            material_gain=True,
            readable_at_final_size=True,
        )
        self.assertEqual(kept.status, "KEEP_STANDARD")
        self.assertEqual(kept.candidates, ("lollipop_plot",))

        considered = advanced_figure_candidate_gate(
            "variable_importance",
            groups=18,
            ordered_categories=True,
            readability_gain=True,
            readable_at_final_size=True,
        )
        self.assertEqual(considered.status, "CONSIDER_ADVANCED")
        self.assertEqual(considered.candidates, ("lollipop_plot",))
        self.assertEqual(considered.metrics["extra_information_dimension_confirmed"], 0.0)
        self.assertEqual(considered.metrics["candidate_gain_confirmed"], 1.0)

    def test_portfolio_normalizes_new_candidate_families(self) -> None:
        result = figure_portfolio_gate(
            [
                {
                    "figure_id": "rank_lollipop",
                    "chart_family": "lollipop_plot",
                    "evidence_kind": "ranked_magnitudes",
                },
                {
                    "figure_id": "rank_dot",
                    "chart_family": "dot",
                    "evidence_kind": "ranked_magnitudes",
                },
            ]
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.metrics["chart_family_count"], 1.0)

    def test_every_basic_chart_can_be_checked_and_kept(self) -> None:
        for evidence_kind in ("time_series", "category_comparison", "point_estimate"):
            with self.subTest(evidence_kind=evidence_kind):
                result = advanced_figure_candidate_gate(evidence_kind)
                self.assertEqual(result.status, "KEEP_STANDARD")
                self.assertEqual(result.candidates, ())
                self.assertEqual(result.metrics["advanced_check_performed"], 1.0)

    def test_advanced_aliases_trigger_but_readability_can_keep_standard(self) -> None:
        result = advanced_figure_candidate_gate(
            "dense_scatter",
            observations=500,
            material_gain=True,
            readable_at_final_size=False,
        )
        self.assertEqual(result.status, "KEEP_STANDARD")
        self.assertIn("hexbin", result.candidates)
        self.assertIn(
            "ADVANCED_CANDIDATE_FAILS_FINAL_SIZE_READABILITY", result.issues
        )

        unconfirmed = advanced_figure_candidate_gate(
            "dense_scatter", observations=500, material_gain=True
        )
        self.assertEqual(unconfirmed.status, "KEEP_STANDARD")
        self.assertIn(
            "ADVANCED_CANDIDATE_READABILITY_NOT_CONFIRMED", unconfirmed.issues
        )

    def test_information_gain_is_checked_before_readability(self) -> None:
        result = advanced_figure_candidate_gate(
            "dense_bivariate",
            observations=500,
            material_gain=False,
            readable_at_final_size=False,
        )
        self.assertEqual(result.status, "KEEP_STANDARD")
        self.assertEqual(result.issues, ("NO_MATERIAL_INFORMATION_OR_STRUCTURE_GAIN",))

    def test_3d_response_surface_has_a_narrow_evidence_contract(self) -> None:
        rejected = advanced_figure_candidate_gate(
            "response_surface",
            material_gain=True,
            continuous_inputs=3,
            continuous_response=True,
            response_grid=True,
        )
        self.assertEqual(rejected.status, "REJECT_ADVANCED")
        self.assertEqual(rejected.candidates, ())

        accepted = advanced_figure_candidate_gate(
            "response_surface",
            material_gain=True,
            continuous_inputs=2,
            continuous_response=True,
            response_grid=True,
            readable_at_final_size=True,
        )
        self.assertEqual(accepted.status, "CONSIDER_ADVANCED")
        self.assertEqual(accepted.candidates, ("3d_response_surface",))

    def test_fig7_summary_values_must_not_be_called_distribution(self) -> None:
        result = visual_information_density_gate(
            "distribution", summary_count=5, summary_only=True
        )
        self.assertEqual(result.status, "RECHART")
        self.assertIn("SUMMARY_VALUES_ARE_NOT_A_DISTRIBUTION", result.issues)

    def test_real_profit_samples_pass_tail_density_gate(self) -> None:
        rng = np.random.default_rng(20260829)
        samples = np.concatenate(
            [rng.normal(4070, 16, 900), rng.normal(4018, 13, 100)]
        )
        result = visual_information_density_gate(
            "tail_risk", samples=samples, alpha=0.05
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.metrics["sample_count"], 1000.0)
        self.assertEqual(result.metrics["expected_tail_count"], 50.0)

    def test_fig10_interval_scale_is_focused_and_disclosed(self) -> None:
        intervals = [(36.35, 36.73), (34.99, 36.69), (34.43, 36.11)]
        estimates = [36.55, 35.87, 35.36]
        result = visual_information_density_gate(
            "paired_diff", intervals=intervals, axis_limits=(-1.5, 42.0)
        )
        self.assertEqual(result.status, "RESCALE")
        self.assertIn("INTERVALS_INVISIBLE_AT_CURRENT_SCALE", result.issues)
        self.assertLess(result.metrics["median_interval_axis_ratio"], 0.05)

        limits = suggest_interval_xlim(intervals, estimates=estimates)
        self.assertGreater(limits[0], 34.0)
        self.assertLess(limits[0], 34.5)
        self.assertGreater(limits[1], 36.8)
        self.assertLess(limits[1], 37.3)

        fig, axes = create_subplots(width="full", height=2.8)
        focused = focus_interval_axis(
            axes[0], intervals, estimates=estimates, reference_value=0.0
        )
        np.testing.assert_allclose(focused, axes[0].get_xlim())
        self.assertTrue(
            any("位于图外左侧" in text.get_text() for text in axes[0].texts)
        )
        axes[0].set_ylim(2.5, -0.5)
        annotation = annotate_point_safely(
            axes[0], intervals[0][1], 0.0, "36.55 [36.35, 36.73]"
        )
        self.assertEqual(annotation.get_ha(), "right")

    def test_boundary_annotation_is_placed_inward(self) -> None:
        fig, axes = create_subplots(width="full", height=2.8)
        ax = axes[0]
        ax.set_xlim(0.0, 0.4)
        ax.set_ylim(3998.0, 4079.0)
        annotation = annotate_point_safely(ax, 0.4, 4001.44, "4001.44")
        self.assertEqual(annotation.get_ha(), "right")
        self.assertEqual(annotation.get_va(), "bottom")

    def test_full_span_composition_lock_removes_white_band(self) -> None:
        fig, axes = create_subplots(width="full", height=2.8)
        ax = axes[0]
        ax.bar([0, 1], [62, 47], bottom=[0, 0], width=0.52)
        ax.bar([0, 1], [38, 53], bottom=[62, 47], width=0.52)
        before = audit_full_span_composition_axis(
            ax, chart_kind="100% stacked bar", percent_max=100
        )
        self.assertIn("FULL_SPAN_COMPOSITION_PERCENT_AXIS_NOT_LOCKED", before)

        lock_full_span_composition_axis(
            ax, chart_kind="100% stacked bar", percent_max=100
        )
        np.testing.assert_allclose(ax.get_ylim(), (0.0, 100.0))
        self.assertEqual(ax.margins()[1], 0.0)
        self.assertEqual(
            audit_full_span_composition_axis(
                ax, chart_kind="100_percent_stacked_bar", percent_max=100
            ),
            [],
        )

        limits_before = (ax.get_xlim(), ax.get_ylim())
        annotation = annotate_composition_boundary(ax, 1.0, "100%", edge="top")
        self.assertEqual(annotation.get_va(), "top")
        self.assertEqual(limits_before, (ax.get_xlim(), ax.get_ylim()))

    def test_marimekko_locks_both_axes_and_audit_catches_late_expansion(self) -> None:
        fig, axes = create_subplots(width="full", height=3.0)
        ax = axes[0]
        ax.bar([0, 40], [0.55, 0.72], width=[40, 60], align="edge")
        lock_full_span_composition_axis(
            ax,
            chart_kind="marimekko",
            percent_max=1.0,
            total_bounds=(0.0, 100.0),
        )
        np.testing.assert_allclose(ax.get_xlim(), (0.0, 100.0))
        np.testing.assert_allclose(ax.get_ylim(), (0.0, 1.0))
        np.testing.assert_allclose(ax.margins(), (0.0, 0.0))
        self.assertEqual(audit_figure(fig), [])

        ax.set_ylim(-0.02, 1.05)
        issues = audit_figure(fig)
        self.assertTrue(
            any(
                item.startswith("FULL_SPAN_COMPOSITION_PERCENT_AXIS_NOT_LOCKED")
                for item in issues
            )
        )

    def test_export_and_a4_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fig, axes = create_subplots(width="full", height=2.8)
            axes[0].plot([0, 1], [0, 1], color=SEMANTIC_COLORS["primary"])
            paths = finalize_figure(fig, tmp_path / "figure", close=False)
            self.assertEqual({path.suffix for path in paths}, {".pdf", ".png"})
            for path in paths:
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)
            preview = render_a4_preview(
                tmp_path / "figure.png", tmp_path / "preview.png", dpi=100
            )
            image = mpimg.imread(preview)
            self.assertGreater(image.shape[0], image.shape[1])

    def test_machine_audit_flags_small_text(self) -> None:
        fig, axes = create_subplots()
        axes[0].text(0.5, 0.5, "too small", fontsize=6)
        issues = audit_figure(fig)
        self.assertTrue(any(item.startswith("TEXT_TOO_SMALL") for item in issues))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path

import numpy as np

os.environ.setdefault("MPLBACKEND", "Agg")

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cumcm_figure_style import (  # noqa: E402
    advanced_figure_candidate_gate,
    evidence_richness_gate,
    figure_portfolio_gate,
    visual_information_density_gate,
)


class GoldenCaseRegressionTests(unittest.TestCase):
    """Frozen v1.4.3 decisions for representative C-problem evidence."""

    def test_2022_discrete_ranking_keeps_horizontal_bar_or_dot(self) -> None:
        advanced = advanced_figure_candidate_gate("category_comparison")
        density = visual_information_density_gate(
            "summary", summary_count=8, summary_only=True
        )
        richness = evidence_richness_gate(["ranked_category_magnitudes"])

        self.assertEqual(
            {
                "recommended_chart": "horizontal_bar_or_dot",
                "advanced": advanced.status,
                "density": density.status,
                "richness": richness.status,
                "final_decision": "KEEP_STANDARD",
            },
            {
                "recommended_chart": "horizontal_bar_or_dot",
                "advanced": "KEEP_STANDARD",
                "density": "PASS",
                "richness": "PASS",
                "final_decision": "KEEP_STANDARD",
            },
        )
        task_rules = (SKILL_ROOT / "references" / "task-patterns.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("优先水平条形或点图", task_rules)

    def test_2023_replenishment_line_and_pricing_heatmap_remain_split(self) -> None:
        replenishment_advanced = advanced_figure_candidate_gate("time_series")
        replenishment_density = visual_information_density_gate(
            "continuous_curve", x=np.arange(9), axis_limits=(0.0, 8.0)
        )
        pricing_advanced = advanced_figure_candidate_gate(
            "categorical_matrix", material_gain=False
        )
        pricing_density = visual_information_density_gate("heatmap")
        portfolio = figure_portfolio_gate(
            [
                {
                    "figure_id": "fig8",
                    "chart_family": "multi_series_line",
                    "evidence_kind": "replenishment_time_series",
                    "series_count": 6,
                },
                {
                    "figure_id": "fig9",
                    "chart_family": "heatmap",
                    "evidence_kind": "category_date_pricing_matrix",
                },
            ]
        )

        self.assertEqual(
            (
                "multi_series_line",
                replenishment_advanced.status,
                replenishment_density.status,
                "heatmap",
                pricing_advanced.status,
                pricing_density.status,
                portfolio.status,
            ),
            (
                "multi_series_line",
                "KEEP_STANDARD",
                "PASS",
                "heatmap",
                "KEEP_STANDARD",
                "PASS",
                "PASS",
            ),
        )
        router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("补货量随日期变化", router)
        self.assertIn("品类 × 日期定价", router)

    def test_2024_tail_risk_keeps_real_distribution_composite(self) -> None:
        samples = np.linspace(3900.0, 4150.0, 1000)
        advanced = advanced_figure_candidate_gate(
            "grouped_distribution",
            observations=samples.size,
            groups=1,
            material_gain=False,
            readable_at_final_size=True,
        )
        density = visual_information_density_gate(
            "tail_risk", samples=samples, alpha=0.05
        )
        richness = evidence_richness_gate(
            ["empirical_distribution", "kde", "mean", "var", "cvar", "risk_tail"],
            current_layers=["empirical_distribution"],
            relationship="complementary",
            same_claim=True,
            same_object=True,
            shared_coordinate=True,
        )

        self.assertEqual(
            {
                "recommended_chart": "tail_distribution_with_var_cvar",
                "advanced": advanced.status,
                "density": density.status,
                "richness": richness.status,
                "final_decision": "COMPOSE_LAYER",
            },
            {
                "recommended_chart": "tail_distribution_with_var_cvar",
                "advanced": "KEEP_STANDARD",
                "density": "PASS",
                "richness": "COMPOSE_LAYER",
                "final_decision": "COMPOSE_LAYER",
            },
        )
        task_rules = (SKILL_ROOT / "references" / "task-patterns.md").read_text(
            encoding="utf-8"
        )
        for token in ("VaR", "CVaR", "尾部着色"):
            self.assertIn(token, task_rules)

    def test_2025_before_after_confusion_matrix_remains_aligned_panels(self) -> None:
        advanced = advanced_figure_candidate_gate(
            "categorical_matrix", material_gain=False
        )
        density = visual_information_density_gate("heatmap")
        richness = evidence_richness_gate(
            ["baseline_confusion", "improved_confusion"],
            current_layers=["baseline_confusion"],
            relationship="complementary",
            same_claim=True,
            same_object=True,
            shared_coordinate=False,
        )

        self.assertEqual(
            {
                "recommended_chart": "aligned_confusion_matrix_panels",
                "advanced": advanced.status,
                "density": density.status,
                "richness": richness.status,
                "final_decision": "COMPOSE_PANEL",
            },
            {
                "recommended_chart": "aligned_confusion_matrix_panels",
                "advanced": "KEEP_STANDARD",
                "density": "PASS",
                "richness": "COMPOSE_PANEL",
                "final_decision": "COMPOSE_PANEL",
            },
        )
        task_rules = (SKILL_ROOT / "references" / "task-patterns.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("before/after、baseline/improved 优先 1×2", task_rules)

    def test_map_route_requires_real_geography_and_basic_audit(self) -> None:
        router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        selection = (SKILL_ROOT / "references" / "chart-selection.md").read_text(
            encoding="utf-8"
        )
        task_rules = (SKILL_ROOT / "references" / "task-patterns.md").read_text(
            encoding="utf-8"
        )
        audit = (SKILL_ROOT / "references" / "visual-audit.md").read_text(
            encoding="utf-8"
        )

        for token in (
            "point / choropleth / proportional-symbol / route-flow map",
            "Map 缺少有效坐标/边界/连接键",
        ):
            self.assertIn(token, router)
        for token in ("Map 选择门禁", "坐标参考系（CRS）", "未匹配率"):
            self.assertIn(token, selection)
        for token in (
            "只有地名、距离矩阵、邻接矩阵或抽象节点—边时",
            "原始总量不得被解释为发生率、风险或密度",
            "Sankey/alluvial 表达阶段/类别流",
        ):
            self.assertIn(token, task_rules)
        for token in ("Map 专项门禁", "不把无数据误画成 0", "落海"):
            self.assertIn(token, audit)

    def test_scheduling_gantt_requires_solver_intervals_and_feasibility_checks(self) -> None:
        router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        selection = (SKILL_ROOT / "references" / "chart-selection.md").read_text(
            encoding="utf-8"
        )
        task_rules = (SKILL_ROOT / "references" / "task-patterns.md").read_text(
            encoding="utf-8"
        )
        audit = (SKILL_ROOT / "references" / "visual-audit.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("resource-row Gantt / scheduling timeline", router)
        self.assertIn("Gantt 不是流程图、Sankey/alluvial 或算法收敛图", router)
        for token in ("Scheduling/Gantt 选择门禁", "end-start=duration", "同一资源不重叠"):
            self.assertIn(token, selection)
        for token in (
            "Flow Shop、Job Shop",
            "start, end 或 duration",
            "同一机器/资源的占用区间不得重叠",
            "图中最晚完工时刻与结果表的 makespan 一致",
            "Gantt 不能替代 precedence network",
        ):
            self.assertIn(token, task_rules)
        for token in ("Scheduling/Gantt 专项门禁", "求解状态为 `FEASIBLE`"):
            self.assertIn(token, audit)

    def test_router_shape_and_runtime_logic_are_frozen(self) -> None:
        router_lines = (SKILL_ROOT / "SKILL.md").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertGreaterEqual(len(router_lines), 350)
        self.assertLessEqual(len(router_lines), 500)

        reference_names = {
            path.name for path in (SKILL_ROOT / "references").glob("*.md")
        }
        self.assertEqual(
            reference_names,
            {
                "advanced-figure-candidates.md",
                "chart-selection.md",
                "evidence-richness-portfolio.md",
                "figures4papers-fusion.md",
                "publication-style.md",
                "task-patterns.md",
                "visual-audit.md",
                "visual-information-density.md",
            },
        )

        expected_hashes = {
            "cumcm_figure_style.py": "83e2aab95df54f3c2cd1c2bff00c9b99bfe4aa5fa91eb48738c5ee88d645d541",
            "render_a4_preview.py": "1f91b29e7bbd8dab041b9f72297c934bafe5b0138f6dbd3b015af06017baca26",
        }
        for name, expected in expected_hashes.items():
            digest = hashlib.sha256((SKILL_ROOT / "scripts" / name).read_bytes()).hexdigest()
            self.assertEqual(digest, expected)


if __name__ == "__main__":
    unittest.main()

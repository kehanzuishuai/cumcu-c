from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


interpretation = load_module(
    "pipeline_validate_interpretation",
    SKILLS_ROOT / "数模审题" / "scripts" / "validate_interpretation.py",
)
figures = load_module(
    "pipeline_write_figure_manifest",
    SKILLS_ROOT / "cumcm-c-paper-figure" / "scripts" / "write_figure_manifest.py",
)
freezer = load_module(
    "pipeline_freeze_submission",
    SKILLS_ROOT / "cumcm-paper-freeze" / "scripts" / "freeze_submission.py",
)
audit = load_module(
    "pipeline_audit_submission",
    SKILLS_ROOT / "数模论文审核" / "scripts" / "audit_submission.py",
)


class PipelineContractTests(unittest.TestCase):
    def write(self, root: Path, relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_manifests_freeze_and_full_gate_are_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard = self.write(
                root,
                "C题规范.md",
                '---\nstandard_id: cumcm-c-paper-standard\nstandard_version: "2026.09.01"\n---\n',
            )
            report = self.write(root, "handoff/赛题解读_final.md", "final")
            model_plan = self.write(root, "handoff/Q1模型方案_final.md", "plan")
            ambiguities = self.write(root, "handoff/歧义与口径确认.md", "ambiguities")
            granularity = self.write(root, "handoff/建模粒度合同.md", "granularity")
            hard = self.write(root, "handoff/约束冻结表.md", "hard")
            decisions = self.write(root, "handoff/题意决定冻结合同.md", "decisions")
            assumptions = self.write(root, "handoff/模型假设台账.md", "assumptions")
            ready = interpretation.build_paper_ready_manifest(
                {
                    "pass": True,
                    "interpretation_status": "PAPER_READY",
                    "detected_subproblems": [1],
                },
                project_root=root,
                standard=standard,
                report=report,
                model_plan=model_plan,
                ambiguities=ambiguities,
                granularity_contract=granularity,
                hard_constraints=hard,
                interpretation_decisions=decisions,
                model_assumptions=assumptions,
            )
            ready_path = root / "handoff/paper_ready_manifest.json"
            ready_path.write_text(json.dumps(ready), encoding="utf-8")

            data = self.write(root, "results/q1.csv", "x,y\n1,2\n")
            script = self.write(root, "code/draw.py", "print('draw')\n")
            output = self.write(root, "figures/q1.png", "png fixture")
            paper_source = self.write(
                root,
                "paper/paper.tex",
                "为核对预测结果与真实观测的对应关系，绘制下图。\n结果表明二者趋势一致，可进入决策阶段。\n",
            )
            brief = self.write(
                root,
                "handoff/figure_briefs_all.md",
                "# Figure Briefs\n\n```yaml\n"
                "brief_schema_version: 2\n"
                "brief_type: figure\n"
                'standard_version: "2026.09.01"\n'
                f"paper_ready_manifest_sha256: {figures.sha256_file(ready_path)}\n"
                "figure_id: fig_q1_01\n"
                "question: Q1\n"
                "contract_ids: []\n"
                "paper_source:\n"
                "  path: paper/paper.tex\n"
                f"  sha256: {figures.sha256_file(paper_source)}\n"
                "task_type: prediction\n"
                "claim: 预测结果与真实观测保持一致趋势\n"
                "evidence_object: paired_observations\n"
                "evidence_roles: [raw_data, prediction]\n"
                "structure: x 与 y 为逐点配对观测\n"
                "data_sources:\n"
                "  - path: results/q1.csv\n"
                f"    sha256: {figures.sha256_file(data)}\n"
                "    fields: [x, y]\n"
                "statistical_scope: Q1 当前评估样本，不额外聚合\n"
                "units: {x: index, y: value}\n"
                "axes_or_groups: {x_axis: x, y_axis: y}\n"
                "comparison_baseline: null\n"
                "uncertainty_to_show: null\n"
                "required_annotations: []\n"
                "standard_chart_candidate: scatter\n"
                "advanced_candidate_inputs: []\n"
                "scale_and_density: {point_count: 1, axis_policy: honest}\n"
                "semantic_roles: {}\n"
                "final_width: full\n"
                "outputs: [pdf, png, code, caption]\n"
                "caption_key_message: 预测结果与真实观测的配对一致性\n"
                "paragraph_before_figure: 为核对预测结果与真实观测的对应关系，绘制下图。\n"
                "paragraph_after_figure: 结果表明二者趋势一致，可进入决策阶段。\n"
                "revision: 1\n"
                "status: READY_FOR_DRAWING\n"
                "```\n",
            )
            figure_manifest = figures.build_figure_manifest(
                project_root=root,
                paper_ready_manifest=ready_path,
                standard_path=standard,
                records={
                    "standard_version": "2026.09.01",
                    "paper_ready_manifest_sha256": figures.sha256_file(ready_path),
                    "assets": [
                        {
                            "asset_id": "fig_q1_01",
                            "asset_type": "figure",
                            "brief_revision": 1,
                            "contract_ids": [],
                            "brief": {"path": brief.relative_to(root).as_posix()},
                            "data_sources": [{
                                "path": data.relative_to(root).as_posix(),
                                "fields": ["x", "y"],
                            }],
                            "script": {"path": script.relative_to(root).as_posix()},
                            "outputs": [{"path": output.relative_to(root).as_posix()}],
                            "qa": {
                                "density": "PASS",
                                "evidence_richness": "PASS",
                                "portfolio": "PASS",
                                "a4_visual": "PASS",
                            },
                            "status": "FINAL",
                        }
                    ],
                },
            )
            figure_manifest_path = root / "figure_manifest.json"
            figure_manifest_path.write_text(json.dumps(figure_manifest), encoding="utf-8")

            self.write(root, "paper/final.pdf", "%PDF fixture")
            self.write(root, "problem/C题.pdf", "%PDF problem")
            self.write(root, "support/AI 工具使用详情.pdf", "%PDF ai")
            freezer.freeze_package(
                project_root=root,
                standard_path=standard,
                destination=root / "paper_final",
                plan={
                    "schema_version": 1,
                    "paper_ready_manifest": "handoff/paper_ready_manifest.json",
                    "figure_manifest": "figure_manifest.json",
                    "paper": "paper/final.pdf",
                    "source": "paper/paper.tex",
                    "problem_files": ["problem/C题.pdf"],
                    "code": ["code"],
                    "results": ["results"],
                    "figures": ["figures"],
                    "support": ["support"],
                    "ai_declarations": ["support/AI 工具使用详情.pdf"],
                    "additional_files": [],
                    "required_files": [{"path": "results/q1.csv"}],
                    "blockers": [],
                    "audit_fields": {
                        "ai_used": True,
                        "has_support_materials": True,
                        "uses_programs": True,
                    },
                },
            )

            args = argparse.Namespace(
                project=str(root / "paper_final"),
                mode="full",
                paper=None,
                manifest=None,
                run_entrypoint=False,
                compile_latex=False,
                render_pdf=False,
                visual_dir=None,
                forbidden_term=[],
                json_out=None,
                md_out=None,
            )
            auditor = audit.SubmissionAudit(args)
            auditor.load_manifest()
            auditor.check_readiness()

            self.assertFalse(auditor.not_ready)
            self.assertIn("READY-006", {item["check_id"] for item in auditor.passes})


if __name__ == "__main__":
    unittest.main()

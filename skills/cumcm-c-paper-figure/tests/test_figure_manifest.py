from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manifest_writer = load_module(
    "write_figure_manifest", SKILL_ROOT / "scripts" / "write_figure_manifest.py"
)


class FigureManifestTests(unittest.TestCase):
    def fixture(self, root: Path):
        standard = root / "C题规范.md"
        standard.write_text(
            '---\nstandard_id: cumcm-c-paper-standard\nstandard_version: "2026.09.01"\n---\n',
            encoding="utf-8",
        )
        roles = [
            "interpretation_final",
            "model_plan_final",
            "ambiguity_decisions",
            "granularity_contract",
            "hard_constraints",
            "interpretation_decisions",
            "model_assumptions",
        ]
        handoff_files = []
        for index, role in enumerate(roles):
            path = root / f"handoff_{index}.md"
            path.write_text(f"handoff {index}\n", encoding="utf-8")
            handoff_files.append(
                {
                    "role": role,
                    "path": path.name,
                    "sha256": manifest_writer.sha256_file(path),
                }
            )
        paper_ready = root / "paper_ready_manifest.json"
        paper_ready.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "PAPER_READY",
                    "standard": manifest_writer.standard_metadata(standard),
                    "files": handoff_files,
                }
            ),
            encoding="utf-8",
        )
        for name, content in {
            "results.csv": "x,y\n1,2\n",
            "draw.py": "print('draw')\n",
            "figure.png": "png fixture\n",
            "flowchart.pptx": "editable pptx fixture\n",
            "paper.md": "为核对预测值与真实值的对应关系，绘制下图。\n\n结果表明预测趋势与真实观测一致，可用于后续决策。\n",
        }.items():
            (root / name).write_text(content, encoding="utf-8")
        (root / "figure_briefs_all.md").write_text(
            "# Figure Briefs\n\n```yaml\n"
            "brief_schema_version: 2\n"
            "brief_type: figure\n"
            'standard_version: "2026.09.01"\n'
            f"paper_ready_manifest_sha256: {manifest_writer.sha256_file(paper_ready)}\n"
            "figure_id: fig_q1_01\n"
            "question: Q1\n"
            "contract_ids: [G-01]\n"
            "paper_source:\n"
            "  path: paper.md\n"
            f"  sha256: {manifest_writer.sha256_file(root / 'paper.md')}\n"
            "task_type: prediction\n"
            "claim: 预测值与真实值在当前样本上保持一致趋势\n"
            "evidence_object: paired_observations\n"
            "evidence_roles: [raw_data, prediction]\n"
            "structure: x 与 y 为逐点配对观测\n"
            "data_sources:\n"
            "  - path: results.csv\n"
            f"    sha256: {manifest_writer.sha256_file(root / 'results.csv')}\n"
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
            "caption_key_message: 预测与真实观测的配对一致性\n"
            "paragraph_before_figure: 为核对预测值与真实值的对应关系，绘制下图。\n"
            "paragraph_after_figure: 结果表明预测趋势与真实观测一致，可用于后续决策。\n"
            "revision: 1\n"
            "status: READY_FOR_DRAWING\n"
            "```\n",
            encoding="utf-8",
        )
        records = {
            "standard_version": "2026.09.01",
            "paper_ready_manifest_sha256": manifest_writer.sha256_file(paper_ready),
            "assets": [
                {
                    "asset_id": "fig_q1_01",
                    "asset_type": "figure",
                    "brief_revision": 1,
                    "contract_ids": ["G-01"],
                    "brief": {"path": "figure_briefs_all.md"},
                    "data_sources": [{"path": "results.csv", "fields": ["x", "y"]}],
                    "script": {"path": "draw.py"},
                    "outputs": [{"path": "figure.png"}],
                    "qa": {
                        "density": "PASS",
                        "evidence_richness": "PASS",
                        "portfolio": "PASS",
                        "a4_visual": "PASS",
                    },
                    "status": "FINAL",
                }
            ],
        }
        return standard, paper_ready, records

    def test_builds_hash_verified_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)

            manifest = manifest_writer.build_figure_manifest(
                project_root=root,
                records=records,
                paper_ready_manifest=paper_ready,
                standard_path=standard,
            )

            self.assertEqual(manifest["status"], "FIGURES_READY")
            self.assertEqual(manifest["assets"][0]["status"], "FINAL")
            self.assertEqual(len(manifest["assets"][0]["outputs"][0]["sha256"]), 64)
            self.assertEqual(manifest["assets"][0]["brief_contract"]["asset_id"], "fig_q1_01")

    def test_unresolved_resample_blocks_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)
            records["resample_requests"] = [{"asset_id": "fig_q1_01"}]

            with self.assertRaisesRegex(ValueError, "RESAMPLE"):
                manifest_writer.build_figure_manifest(
                    project_root=root,
                    records=records,
                    paper_ready_manifest=paper_ready,
                    standard_path=standard,
                )

    def test_stale_data_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)
            records["assets"][0]["data_sources"][0]["sha256"] = "0" * 64

            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                manifest_writer.build_figure_manifest(
                    project_root=root,
                    records=records,
                    paper_ready_manifest=paper_ready,
                    standard_path=standard,
                )

    def test_resample_status_inside_brief_blocks_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)
            brief = root / "figure_briefs_all.md"
            brief.write_text(
                brief.read_text(encoding="utf-8").replace(
                    "status: READY_FOR_DRAWING", "status: RESAMPLE_REQUIRED"
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "RESAMPLE_REQUIRED"):
                manifest_writer.build_figure_manifest(
                    project_root=root,
                    records=records,
                    paper_ready_manifest=paper_ready,
                    standard_path=standard,
                )

    def test_brief_id_revision_and_upstream_hash_must_match(self):
        replacements = (
            ("figure_id: fig_q1_01", "figure_id: DIFFERENT", "matching figure_id"),
            ("revision: 1", "revision: 9", "revision mismatch"),
            (
                f"paper_ready_manifest_sha256: ",
                "paper_ready_manifest_sha256: stale # ",
                "paper_ready_manifest_sha256 mismatch",
            ),
        )
        for old, new, message in replacements:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                standard, paper_ready, records = self.fixture(root)
                brief = root / "figure_briefs_all.md"
                brief.write_text(brief.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    manifest_writer.build_figure_manifest(
                        project_root=root,
                        records=records,
                        paper_ready_manifest=paper_ready,
                        standard_path=standard,
                    )

    def test_brief_data_hash_must_match_asset_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)
            brief = root / "figure_briefs_all.md"
            actual = manifest_writer.sha256_file(root / "results.csv")
            brief.write_text(brief.read_text(encoding="utf-8").replace(actual, "0" * 64), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                manifest_writer.build_figure_manifest(
                    project_root=root,
                    records=records,
                    paper_ready_manifest=paper_ready,
                    standard_path=standard,
                )

    def test_records_standard_version_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)
            records.pop("standard_version")
            with self.assertRaisesRegex(ValueError, "standard_version"):
                manifest_writer.build_figure_manifest(
                    project_root=root,
                    records=records,
                    paper_ready_manifest=paper_ready,
                    standard_path=standard,
                )

    def test_semantic_fields_cannot_be_empty_shells(self):
        replacements = (
            ("units: {x: index, y: value}", "units: {}", "units"),
            ("axes_or_groups: {x_axis: x, y_axis: y}", "axes_or_groups: {}", "axes_or_groups"),
            ("scale_and_density: {point_count: 1, axis_policy: honest}", "scale_and_density: {}", "scale_and_density"),
            ("evidence_roles: [raw_data, prediction]", "evidence_roles: []", "evidence_roles"),
        )
        for old, new, message in replacements:
            with self.subTest(field=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                standard, paper_ready, records = self.fixture(root)
                brief = root / "figure_briefs_all.md"
                brief.write_text(brief.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    manifest_writer.build_figure_manifest(
                        project_root=root,
                        records=records,
                        paper_ready_manifest=paper_ready,
                        standard_path=standard,
                    )

    def test_body_anchors_must_exist_in_order_in_paper_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)
            brief = root / "figure_briefs_all.md"
            brief.write_text(
                brief.read_text(encoding="utf-8").replace(
                    "paragraph_after_figure: 结果表明预测趋势与真实观测一致，可用于后续决策。",
                    "paragraph_after_figure: 正文中不存在的结论。",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "paragraph_after_figure"):
                manifest_writer.build_figure_manifest(
                    project_root=root,
                    records=records,
                    paper_ready_manifest=paper_ready,
                    standard_path=standard,
                )

    def test_contract_ids_and_data_fields_must_match_asset_record(self):
        cases = (
            ("contract_ids", lambda records: records["assets"][0].update({"contract_ids": []})),
            (
                "path/hash/fields",
                lambda records: records["assets"][0]["data_sources"][0].update({"fields": ["x"]}),
            ),
        )
        for message, mutate in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                standard, paper_ready, records = self.fixture(root)
                mutate(records)
                with self.assertRaisesRegex(ValueError, message):
                    manifest_writer.build_figure_manifest(
                        project_root=root,
                        records=records,
                        paper_ready_manifest=paper_ready,
                        standard_path=standard,
                    )

    def test_flowchart_brief_requires_matching_logic_and_human_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, paper_ready, records = self.fixture(root)
            asset = records["assets"][0]
            asset.update(
                {
                    "asset_id": "flow_total_01",
                    "asset_type": "flowchart",
                    "data_sources": [],
                    "qa": {"logic_match": "PASS", "editability": "PASS", "a4_visual": "PASS"},
                    "human_approved": True,
                }
            )
            brief = root / "figure_briefs_all.md"
            brief.write_text(
                "# Flowchart Briefs\n\n```yaml\n"
                "brief_schema_version: 2\n"
                "brief_type: flowchart\n"
                'standard_version: "2026.09.01"\n'
                f"paper_ready_manifest_sha256: {manifest_writer.sha256_file(paper_ready)}\n"
                "flowchart_id: flow_total_01\n"
                "flowchart_type: total\n"
                "question: ALL\n"
                "contract_ids: [G-01]\n"
                "paper_source:\n"
                "  path: paper.md\n"
                f"  sha256: {manifest_writer.sha256_file(root / 'paper.md')}\n"
                "purpose: 说明输入到预测输出的主流程\n"
                "nodes:\n"
                "  - id: n1\n"
                "    label: 输入数据\n"
                "    role: input\n"
                "    group: null\n"
                "  - id: n2\n"
                "    label: 预测结果\n"
                "    role: output\n"
                "    group: null\n"
                "edges:\n"
                "  - from: n1\n"
                "    to: n2\n"
                "    label: 模型计算\n"
                "    interface_id: null\n"
                "reading_order: top_to_bottom\n"
                "final_width: full\n"
                "outputs: [pptx, png]\n"
                "paragraph_before_flowchart: 为核对预测值与真实值的对应关系，绘制下图。\n"
                "paragraph_after_flowchart: 结果表明预测趋势与真实观测一致，可用于后续决策。\n"
                "revision: 1\n"
                "status: LOGIC_FIXED\n"
                "human_approved: true\n"
                "```\n",
                encoding="utf-8",
            )
            asset.pop("script")
            asset["source"] = {"path": "flowchart.pptx"}
            manifest = manifest_writer.build_figure_manifest(
                project_root=root,
                records=records,
                paper_ready_manifest=paper_ready,
                standard_path=standard,
            )
            self.assertTrue(manifest["assets"][0]["brief_contract"]["human_approved"])
            self.assertNotIn("script", manifest["assets"][0])
            self.assertEqual("flowchart.pptx", manifest["assets"][0]["source"]["path"])

            brief.write_text(
                brief.read_text(encoding="utf-8").replace(
                    "human_approved: true", "human_approved: false"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "human_approved"):
                manifest_writer.build_figure_manifest(
                    project_root=root,
                    records=records,
                    paper_ready_manifest=paper_ready,
                    standard_path=standard,
                )


if __name__ == "__main__":
    unittest.main()

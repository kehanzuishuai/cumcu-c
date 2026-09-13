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


freezer = load_module("freeze_submission", SKILL_ROOT / "scripts" / "freeze_submission.py")


class FreezeSubmissionTests(unittest.TestCase):
    def write(self, root: Path, relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def fixture(self, root: Path):
        standard = self.write(
            root,
            "standard.md",
            '---\nstandard_id: cumcm-c-paper-standard\nstandard_version: "2026.09.01"\n---\n',
        )
        standard_meta = freezer.standard_metadata(standard)
        roles = [
            "interpretation_final",
            "model_plan_final",
            "ambiguity_decisions",
            "granularity_contract",
            "hard_constraints",
            "interpretation_decisions",
            "model_assumptions",
        ]
        handoff = []
        for role in roles:
            path = self.write(root, f"handoff/{role}.md", role)
            handoff.append(
                {"role": role, "path": path.relative_to(root).as_posix(), "sha256": freezer.sha256_file(path)}
            )
        paper_ready_path = root / "handoff/paper_ready_manifest.json"
        paper_ready_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "PAPER_READY",
                    "standard": standard_meta,
                    "problem_count": 4,
                    "files": handoff,
                }
            ),
            encoding="utf-8",
        )

        brief = self.write(root, "handoff/figure_briefs_all.md", "brief")
        data = self.write(root, "results/q1.csv", "x,y\n1,2\n")
        script = self.write(root, "code/draw.py", "print('draw')\n")
        output = self.write(root, "figures/q1.png", "png fixture")
        figure_manifest_path = root / "figure_manifest.json"
        figure_manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "status": "FIGURES_READY",
                    "standard": standard_meta,
                    "paper_ready_manifest_sha256": freezer.sha256_file(paper_ready_path),
                    "assets": [
                        {
                            "asset_id": "fig_q1_01",
                            "asset_type": "figure",
                            "brief_revision": 1,
                            "contract_ids": [],
                            "brief": {"path": "handoff/figure_briefs_all.md", "sha256": freezer.sha256_file(brief)},
                            "brief_contract": {
                                "schema_version": 2,
                                "brief_type": "figure",
                                "asset_id": "fig_q1_01",
                                "revision": 1,
                                "status": "READY_FOR_DRAWING",
                                "standard_version": "2026.09.01",
                                "paper_ready_manifest_sha256": freezer.sha256_file(paper_ready_path),
                                "contract_ids": [],
                                "semantic_sha256": "a" * 64,
                                "body_context": {
                                    "paper_source": {
                                        "path": "handoff/figure_briefs_all.md",
                                        "sha256": freezer.sha256_file(brief),
                                    },
                                    "before_sha256": "b" * 64,
                                    "after_sha256": "c" * 64,
                                },
                                "data_sources": [
                                    {
                                        "path": "results/q1.csv",
                                        "sha256": freezer.sha256_file(data),
                                        "fields": ["x", "y"],
                                    }
                                ],
                            },
                            "data_sources": [{
                                "path": "results/q1.csv",
                                "sha256": freezer.sha256_file(data),
                                "fields": ["x", "y"],
                            }],
                            "script": {"path": "code/draw.py", "sha256": freezer.sha256_file(script)},
                            "outputs": [{"path": "figures/q1.png", "sha256": freezer.sha256_file(output)}],
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
            ),
            encoding="utf-8",
        )
        self.write(root, "paper/final_paper.pdf", "%PDF fixture")
        self.write(root, "paper/paper.tex", "\\documentclass{article}")
        self.write(root, "problem/C题.pdf", "%PDF problem")
        self.write(root, "support/AI 工具使用详情.pdf", "%PDF ai")
        plan = {
            "schema_version": 1,
            "paper_ready_manifest": "handoff/paper_ready_manifest.json",
            "figure_manifest": "figure_manifest.json",
            "paper": "paper/final_paper.pdf",
            "source": "paper/paper.tex",
            "problem_files": ["problem/C题.pdf"],
            "code": ["code"],
            "results": ["results"],
            "figures": ["figures"],
            "support": ["support"],
            "ai_declarations": ["support/AI 工具使用详情.pdf"],
            "additional_files": [],
            "required_files": [{"path": "results/q1.csv", "rows": 2, "columns": 2}],
            "blockers": [],
            "audit_fields": {
                "ai_used": True,
                "has_support_materials": True,
                "uses_programs": True,
            },
        }
        return standard, plan

    def test_freezes_new_package_with_audit_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            destination = root / "paper_final"

            manifest = freezer.freeze_package(
                project_root=root,
                plan=plan,
                destination=destination,
                standard_path=standard,
            )

            self.assertTrue(manifest["frozen"])
            self.assertEqual(manifest["blockers"], [])
            self.assertTrue((destination / "audit_manifest.json").is_file())
            self.assertTrue((destination / "paper/final_paper.pdf").is_file())
            self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["frozen_files"]))

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            destination = root / "paper_final"
            destination.mkdir()

            with self.assertRaises(FileExistsError):
                freezer.freeze_package(
                    project_root=root,
                    plan=plan,
                    destination=destination,
                    standard_path=standard,
                )

    def test_stale_figure_dependency_blocks_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            (root / "results/q1.csv").write_text("x,y\n1,9\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                freezer.freeze_package(
                    project_root=root,
                    plan=plan,
                    destination=root / "paper_final",
                    standard_path=standard,
                )

    def test_stale_brief_contract_snapshot_blocks_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            manifest_path = root / "figure_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["assets"][0]["brief_contract"]["status"] = "RESAMPLE_REQUIRED"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "stale Brief contract"):
                freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)

    def test_nonempty_blockers_refuse_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            plan["blockers"] = ["figure pending"]

            with self.assertRaisesRegex(ValueError, "blockers"):
                freezer.freeze_package(
                    project_root=root,
                    plan=plan,
                    destination=root / "paper_final",
                    standard_path=standard,
                )

    def test_required_boolean_audit_fields_cannot_be_missing_or_non_boolean(self):
        for field in ("ai_used", "has_support_materials", "uses_programs"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                standard, plan = self.fixture(root)
                plan["audit_fields"].pop(field)
                with self.assertRaisesRegex(ValueError, field):
                    freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)

    def test_source_must_be_distinct_from_pdf_and_use_a_source_format(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            plan["source"] = plan["paper"]
            with self.assertRaisesRegex(ValueError, "distinct"):
                freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            self.write(root, "paper/source.txt", "not a paper source")
            plan["source"] = "paper/source.txt"
            with self.assertRaisesRegex(ValueError, "distinct final"):
                freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)

    def test_code_results_and_figures_completeness_is_enforced(self):
        cases = (("code", "code"), ("results", "results"), ("figures", "figures"))
        for field, message in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                standard, plan = self.fixture(root)
                plan[field] = []
                with self.assertRaisesRegex(ValueError, message):
                    freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)

    def test_support_and_ai_declarations_must_match_explicit_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            plan["support"] = []
            with self.assertRaisesRegex(ValueError, "has_support_materials"):
                freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            plan["ai_declarations"] = []
            with self.assertRaisesRegex(ValueError, "AI 工具使用详情"):
                freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            plan["audit_fields"].update({"ai_used": False, "has_support_materials": False})
            plan["support"] = []
            plan["ai_declarations"] = []
            manifest, _ = freezer.build_freeze_payload(
                project_root=root, plan=plan, standard_path=standard
            )
            self.assertFalse(manifest["ai_used"])
            self.assertFalse(manifest["has_support_materials"])

    def test_flowchart_requires_editable_pptx_but_not_generation_script(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard, plan = self.fixture(root)
            source = self.write(root, "figures/flow_total_01.pptx", "editable pptx fixture")
            manifest_path = root / "figure_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            asset = payload["assets"][0]
            asset.update(
                {
                    "asset_id": "flow_total_01",
                    "asset_type": "flowchart",
                    "data_sources": [],
                    "source": {
                        "path": "figures/flow_total_01.pptx",
                        "sha256": freezer.sha256_file(source),
                    },
                    "qa": {"logic_match": "PASS", "editability": "PASS", "a4_visual": "PASS"},
                    "human_approved": True,
                }
            )
            asset.pop("script")
            contract = asset["brief_contract"]
            contract.update(
                {
                    "brief_type": "flowchart",
                    "asset_id": "flow_total_01",
                    "status": "LOGIC_FIXED",
                    "human_approved": True,
                }
            )
            contract.pop("data_sources")
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            plan["audit_fields"]["uses_programs"] = False
            plan["code"] = []

            manifest, collected = freezer.build_freeze_payload(
                project_root=root, plan=plan, standard_path=standard
            )
            self.assertTrue(manifest["frozen"])
            self.assertIn("figures/flow_total_01.pptx", collected)

            asset.pop("source")
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source"):
                freezer.build_freeze_payload(project_root=root, plan=plan, standard_path=standard)


if __name__ == "__main__":
    unittest.main()

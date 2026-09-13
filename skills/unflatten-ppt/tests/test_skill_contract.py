from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_existing_reconstruction_scripts_are_unchanged(self) -> None:
        expected = {
            "scripts/compare_pngs.py": "672cc198b449cabe873a6fe7e89bdaf27c803dfe65bce785312b6e8019b816e6",
            "scripts/export_ppt_slide.ps1": "af133fff3518b2bed8b77740effa6fbd66afe8eeed0c4f8d30be0b9685130c5d",
        }
        for relative_path, digest in expected.items():
            data = (ROOT / relative_path).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)

    def test_main_skill_stays_light_and_routes_cumcm_detail(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 110)
        self.assertIn("references/cumcm-flowchart-style.md", skill)
        self.assertIn("references/quality-checklist.md", skill)
        self.assertRegex(skill, r"decide whether (?:the paper )?needs a flowchart|decide whether a flowchart is needed")

    def test_core_workflow_order_is_preserved(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        steps = re.findall(r"^\d+\. (.+)$", skill, flags=re.MULTILINE)
        self.assertEqual(
            steps[:5],
            [
                "Inspect the reference dimensions and content.",
                "Generate an editable PPT reconstruction.",
                "Export the slide and compare.",
                "Iterate.",
                "Deliver artifacts.",
            ],
        )

    def test_editable_pptx_is_required_but_generation_code_is_optional(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Code is optional", skill)
        self.assertIn("`source` must point to the editable `.pptx`", skill)
        self.assertIn("`script` is optional", skill)

    def test_cumcm_contract_contains_required_gates(self) -> None:
        reference = (ROOT / "references/cumcm-flowchart-style.md").read_text(encoding="utf-8")
        required = [
            "宋体",
            "Times New Roman",
            "two to four low-saturation",
            "Native-Editability Contract",
            "A4 / Actual-Insertion-Size Visual QA",
            "Text overflow",
            "Arrow correctness",
            "Crossings and overlap",
            "Whitespace",
            "Readability",
            "Export clarity",
            "Editability",
        ]
        for item in required:
            self.assertIn(item, reference)

        forbidden_effects = ["neon", "3D", "strong gradient", "heavy shadow", "AI-infographic"]
        for item in forbidden_effects:
            self.assertIn(item, reference)


if __name__ == "__main__":
    unittest.main()

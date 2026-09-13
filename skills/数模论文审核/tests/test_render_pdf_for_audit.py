from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "render_pdf_for_audit.py"
SPEC = importlib.util.spec_from_file_location("render_pdf_for_audit_for_tests", SCRIPT_PATH)
assert SPEC and SPEC.loader
render_pdf = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = render_pdf
SPEC.loader.exec_module(render_pdf)


class RenderReportTests(unittest.TestCase):
    def test_numeric_page_sorting(self) -> None:
        pages = [Path("raw-page-10.png"), Path("raw-page-2.png"), Path("raw-page-1.png")]
        ordered = sorted(pages, key=render_pdf.numeric_suffix)
        self.assertEqual(["raw-page-1.png", "raw-page-2.png", "raw-page-10.png"], [item.name for item in ordered])

    def test_visual_review_states_heuristic_boundary(self) -> None:
        pages = [
            {
                "page": 1,
                "metrics": {
                    "heuristic_flags": ["存在大面积连续空白候选"],
                    "occupied_height_ratio": 0.5,
                    "largest_blank_band_ratio": 0.4,
                },
            }
        ]
        report = render_pdf.build_review_markdown(
            Path("final.pdf"), "abc123", pages, Path("visual-session")
        )
        self.assertIn("只生成候选页，不自动判定视觉 FAIL", report)
        self.assertIn("逐页查看", report)


if __name__ == "__main__":
    unittest.main()

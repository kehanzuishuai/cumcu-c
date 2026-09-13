from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "audit_submission.py"
SPEC = importlib.util.spec_from_file_location("audit_submission_for_tests", SCRIPT_PATH)
assert SPEC and SPEC.loader
audit_submission = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_submission
SPEC.loader.exec_module(audit_submission)


def make_args(project: Path, mode: str = "paper-only") -> argparse.Namespace:
    return argparse.Namespace(
        project=str(project),
        mode=mode,
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


class FormatAndReadabilityTests(unittest.TestCase):
    def test_common_custom_abstract_and_keyword_forms_are_supported(self) -> None:
        text = r"""
\begin{zhabstract}
摘要正文。
\end{zhabstract}
\zhkeywords{预测；优化；稳健性；灵敏度；决策}
"""
        found, _ = audit_submission.find_abstract_evidence(text)
        payloads = audit_submission.find_keyword_payloads(text)
        self.assertTrue(found)
        self.assertEqual([5], [audit_submission.count_keywords(item) for item in payloads])

    def test_latex_comments_and_math_do_not_create_readability_candidates(self) -> None:
        text = (
            "% 由于因此从而进而同时此外并且" * 30
            + "\n\\begin{equation}\n"
            + "由于因此从而进而同时此外并且" * 30
            + "\n\\end{equation}\n正文较短，逻辑清楚。"
        )
        candidates = audit_submission.readability_candidates(text)
        self.assertTrue(all(not items for items in candidates.values()))

    def test_long_dense_sentence_is_only_a_candidate(self) -> None:
        sentence = (
            "由于样本同时具有时间相关性和对象内重复观测，因此先按对象划分训练集，"
            "同时保留时间顺序，从而避免未来信息泄漏；".replace("；", "，")
            + "在此基础上，考虑到异常值会影响参数估计，进一步采用稳健损失进行拟合，"
            + "并且通过滚动验证比较误差，因此最终只把该句列为人工可读性检查候选。"
        )
        candidates = audit_submission.readability_candidates(sentence)
        self.assertTrue(candidates["long_sentences"])
        self.assertTrue(candidates["dense_connectors"])

    def test_abstract_noun_stack_is_located_without_becoming_failure(self) -> None:
        sentence = (
            "本文构建机制体系框架与能力水平评价结构，通过协同路径和闭环策略实现过程优化，"
            "形成价值支撑与意义提升，并据此给出下一阶段的分析安排。"
        )
        candidates = audit_submission.readability_candidates(sentence)
        self.assertTrue(candidates["abstract_stacks"])

    def test_language_findings_are_heuristic_p3_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name)))
            auditor.audit_language("需要说明的是，甲。需要说明的是，乙。需要说明的是，丙。")
            self.assertTrue(auditor.findings)
            self.assertTrue(all(item.priority == "P3" for item in auditor.findings))
            self.assertTrue(all(item.certainty == "HEURISTIC" for item in auditor.findings))

    def test_default_terminology_variants_are_located_for_semantic_review(self) -> None:
        text = "第一问采用暖启动求解。第二问沿用热启动以缩短计算时间。"
        candidates = audit_submission.terminology_consistency_candidates(text)
        self.assertEqual(1, len(candidates))
        self.assertEqual("暖启动", candidates[0]["canonical"])
        self.assertEqual({"暖启动", "热启动"}, set(candidates[0]["variants"]))

    def test_single_terminology_variant_does_not_create_candidate(self) -> None:
        candidates = audit_submission.terminology_consistency_candidates(
            "训练与滚动预测均采用暖启动。"
        )
        self.assertEqual([], candidates)

    def test_manifest_custom_terminology_group_is_supported(self) -> None:
        config = [{"canonical": "风险情景", "variants": ["风险情景", "压力情景"]}]
        candidates = audit_submission.terminology_consistency_candidates(
            "风险情景用于拟合，压力情景用于验证。", config
        )
        self.assertIn("风险情景", {item["canonical"] for item in candidates})

    def test_showcase_citation_expression_is_located(self) -> None:
        text = r"相关方法见文献\cite{copula}。具体算法参见文献\parencite{solver}。"
        candidates = audit_submission.showcase_citation_candidates(text)
        self.assertEqual(2, len(candidates))

    def test_direct_method_citation_expression_is_not_flagged(self) -> None:
        text = r"采用 Gaussian Copula\cite{copula} 描述变量间的尾部相关。"
        self.assertEqual([], audit_submission.showcase_citation_candidates(text))

    def test_literature_review_phrase_is_not_treated_as_showcase_citation(self) -> None:
        self.assertEqual([], audit_submission.showcase_citation_candidates("本节可参考文献综述的分类框架。"))

    def test_terminology_and_showcase_findings_remain_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name)))
            auditor.audit_language(r"先用暖启动，后称热启动。相关方法见文献\cite{a}。")
            findings = {
                item.check_id: item for item in auditor.findings
                if item.check_id in {"TERM-001", "LANG-006"}
            }
            self.assertEqual({"TERM-001", "LANG-006"}, set(findings))
            self.assertTrue(all(item.priority == "P2" for item in findings.values()))
            self.assertTrue(all(item.certainty == "HEURISTIC" for item in findings.values()))


class FalsePositiveBoundaryTests(unittest.TestCase):
    def test_external_email_and_github_are_unverified_not_identity_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "references.md"
            source.write_text(
                "数据来源联系邮箱：editor@example.org\nhttps://github.com/example/project\n",
                encoding="utf-8",
            )
            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.files = [source]
            auditor.audit_anonymity_and_hygiene()
            self.assertFalse(any(item.priority in {"P0", "P1"} for item in auditor.findings))
            self.assertIn("ANON-004", {item["check_id"] for item in auditor.unverified})

    def test_explicit_identity_term_is_high_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "paper.md"
            source.write_text("作者来自示例大学。", encoding="utf-8")
            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.files = [source]
            auditor.manifest = {"identity_terms": {"schools": ["示例大学"]}}
            auditor.audit_anonymity_and_hygiene()
            self.assertIn("ANON-001", {item.check_id for item in auditor.findings if item.priority == "P0"})

    def test_personal_user_path_is_high_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "run.py"
            source.write_text(r'INPUT = "C:\Users\real_student\project\data.csv"', encoding="utf-8")
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="full"))
            auditor.files = [source]
            auditor.audit_anonymity_and_hygiene()
            self.assertIn("ANON-002", {item.check_id for item in auditor.findings if item.priority == "P1"})

    def test_declared_no_support_does_not_require_support_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="full"))
            auditor.manifest = {
                "has_support_materials": False,
                "uses_programs": False,
                "ai_used": False,
            }
            auditor.source_text = "附录\n本论文没有支撑材料。\n本论文没有用到程序。"
            auditor.audit_support()
            support_findings = [item for item in auditor.findings if item.check_id.startswith("SUPPORT-")]
            self.assertEqual([], support_findings)
            self.assertIn("SUPPORT-011", {item["check_id"] for item in auditor.passes})

    def test_unextractable_pdf_does_not_fail_abstract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paper = root / "final.pdf"
            paper.write_bytes(b"%PDF-1.4\n")
            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.paper = paper
            with (
                patch.object(audit_submission, "pdf_page_count", return_value=None),
                patch.object(audit_submission, "pdf_text", return_value=None),
                patch.object(audit_submission, "pdf_font_names", return_value=None),
            ):
                auditor.audit_paper_file()
            self.assertIn("PDF-003", {item["check_id"] for item in auditor.unverified})
            self.assertFalse(any(item.check_id.startswith("ABSTRACT-") for item in auditor.findings))


class ModeBoundaryAndEscalationTests(unittest.TestCase):
    def test_paper_only_is_not_incomplete_by_design(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="paper-only"))
            self.assertFalse(auditor.scope_incomplete)
            self.assertEqual(
                "PAPER_AUDIT_COMPLETE_WITH_WARNINGS",
                auditor.determine_script_status(),
            )
            deferred_items = {item["item"] for item in auditor.deferred}
            self.assertIn("代码执行与复现", deferred_items)
            self.assertIn("支撑材料目录/压缩包与工程卫生", deferred_items)
            self.assertIn("最终 PDF 逐页视觉确认", deferred_items)

    def test_paper_only_accepts_latex_source_without_final_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "main.tex"
            source.write_text("\\section{问题一}\n正文。", encoding="utf-8")
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            auditor.discover_files()
            auditor.render_visual_assets()
            self.assertEqual(source, auditor.source)
            self.assertFalse(auditor.scope_incomplete)
            self.assertNotIn("FILE-003", {item.check_id for item in auditor.findings})
            self.assertNotIn("VISUAL-001", {item["check_id"] for item in auditor.unverified})

    def test_paper_only_accepts_markdown_as_the_only_paper_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "论文.md"
            source.write_text("# 问题一\n\n正文。", encoding="utf-8")
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            auditor.discover_files()
            self.assertEqual(source, auditor.source)
            self.assertFalse(auditor.scope_incomplete)
            self.assertNotIn("FILE-003", {item.check_id for item in auditor.findings})

    def test_multiple_final_paper_candidates_are_deferred_when_source_is_locked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "main.tex"
            source.write_text("正文。", encoding="utf-8")
            (root / "draft.pdf").write_bytes(b"%PDF-1.4\n")
            (root / "paper.pdf").write_bytes(b"%PDF-1.4\n")
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            auditor.discover_files()
            self.assertFalse(auditor.scope_incomplete)
            self.assertNotIn("FILE-001", {item.check_id for item in auditor.findings})
            deferred = next(item for item in auditor.deferred if item["check_id"] == "SCOPE-FULL-006")
            self.assertEqual("DEFERRED_TO_FULL", deferred["status"])

    def test_paper_only_status_separates_warnings_and_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            warning_auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            warning_auditor.warn("P3", "TEST-WARN", "局部可优化", "paper.tex", "证据", "规则", "建议")
            self.assertEqual(
                "PAPER_AUDIT_COMPLETE_WITH_WARNINGS",
                warning_auditor.determine_script_status(),
            )

            blocker_auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            blocker_auditor.add("P1", "TEST-BLOCK", "论文内部冲突", "paper.tex", "证据", "规则", "建议")
            self.assertEqual(
                "PAPER_AUDIT_COMPLETE_WITH_BLOCKERS",
                blocker_auditor.determine_script_status(),
            )

    def test_paper_only_drawing_placeholder_is_deferred_not_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="paper-only"))
            auditor.audit_drawing_placeholders("图 3：联合情景比较（待绘制）")
            self.assertFalse(any(item.check_id.startswith("DRAWING-") for item in auditor.findings))
            deferred = next(item for item in auditor.deferred if item["check_id"] == "DRAWING-001")
            self.assertEqual("DEFERRED_TO_DRAWING", deferred["status"])
            coverage = next(
                item for item in auditor.build_paper_only_coverage()
                if item["module"] == "图表正文叙事"
            )
            self.assertEqual("WARN", coverage["status"])
            self.assertEqual("PAPER_AUDIT_COMPLETE_WITH_WARNINGS", auditor.determine_script_status())

    def test_full_drawing_placeholder_is_confirmed_p1(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="full"))
            auditor.audit_drawing_placeholders("表 5：稳健方案结果（待补表）")
            finding = next(item for item in auditor.findings if item.check_id == "DRAWING-002")
            self.assertEqual("P1", finding.priority)
            self.assertEqual("FULL_BLOCKER", finding.stage_status)

    def test_visual_only_drawing_placeholder_is_confirmed_p1(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="visual-only"))
            auditor.audit_drawing_placeholders("此处插入流程图")
            finding = next(item for item in auditor.findings if item.check_id == "DRAWING-002")
            self.assertEqual("P1", finding.priority)
            self.assertEqual("VISUAL_ONLY_BLOCKER", finding.stage_status)

    def test_problem_source_claim_is_located_without_automatic_failure(self) -> None:
        text = (
            r"根据题目给定的模拟关联数据，构造相关矩阵 $R_0$，"
            "得到 82 条替代边和 24 条互补边。"
        )
        candidates = audit_submission.source_attribution_candidates(text)
        self.assertEqual(1, len(candidates))
        objects = set(candidates[0]["objects"])
        self.assertIn("R_0", objects)
        self.assertIn("相关矩阵", objects)
        self.assertIn("替代边", objects)

        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="paper-only"))
            auditor.audit_source_attributions(text)
            finding = next(item for item in auditor.findings if item.check_id == "SOURCE-001")
            self.assertEqual("P2", finding.priority)
            self.assertEqual("HEURISTIC", finding.certainty)
            coverage = next(
                item for item in auditor.build_paper_only_coverage()
                if item["module"] == "模型选择证据链"
            )
            self.assertEqual("WARN", coverage["status"])
            payload, report = auditor.build_report()
            self.assertEqual(1, len(payload["source_attribution_candidates"]))
            self.assertIn("题面事实与模型设定来源矩阵", report)
            self.assertIn("R_0", report)

    def test_explicit_team_setting_is_not_mislabeled_as_problem_source_candidate(self) -> None:
        text = r"本文用固定随机种子生成相关矩阵 $R_0$，并设定 $\alpha=0.95$。"
        self.assertEqual([], audit_submission.source_attribution_candidates(text))

    def test_ordinary_problem_task_number_is_not_a_parameter_source_candidate(self) -> None:
        text = "题目要求预测未来 24 个月的销量。"
        self.assertEqual([], audit_submission.source_attribution_candidates(text))

    def test_data_shows_parameter_source_statement_is_located(self) -> None:
        text = r"模拟数据表明相关系数为 $\rho=0.6$。"
        candidates = audit_submission.source_attribution_candidates(text)
        self.assertEqual(1, len(candidates))
        self.assertIn("相关系数", candidates[0]["objects"])

    def test_ai_details_are_deferred_in_paper_only_but_p0_in_full(self) -> None:
        text = "AI 工具使用声明\n本参赛队使用了 AI 工具。\n参考文献"
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paper_auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            paper_auditor.manifest = {"ai_used": True}
            paper_auditor.audit_ai_statement(text)
            self.assertNotIn("AI-005", {item.check_id for item in paper_auditor.findings})
            detail = next(item for item in paper_auditor.deferred if item["check_id"] == "SCOPE-FULL-004")
            self.assertEqual("DEFERRED_TO_FULL", detail["status"])

            full_auditor = audit_submission.SubmissionAudit(make_args(root, mode="full"))
            full_auditor.manifest = {"ai_used": True}
            full_auditor.audit_ai_statement(text)
            finding = next(item for item in full_auditor.findings if item.check_id == "AI-005")
            self.assertEqual("P0", finding.priority)

    def test_paper_only_ignores_build_garbage_but_full_reports_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paper = root / "paper.md"
            garbage = root / "paper.aux"
            paper.write_text("匿名论文正文", encoding="utf-8")
            garbage.write_text("build", encoding="utf-8")

            paper_auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            paper_auditor.source = paper
            paper_auditor.files = [paper, garbage]
            paper_auditor.audit_anonymity_and_hygiene()
            self.assertNotIn("HYGIENE-001", {item.check_id for item in paper_auditor.findings})

            full_auditor = audit_submission.SubmissionAudit(make_args(root, mode="full"))
            full_auditor.files = [paper, garbage]
            full_auditor.audit_anonymity_and_hygiene()
            self.assertIn("HYGIENE-001", {item.check_id for item in full_auditor.findings})

    def test_valid_parindent_with_local_mixed_indentation_is_p3_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "paper.tex"
            text = r"""
\setlength{\parindent}{2em}
正文第一段。
\noindent 正文第二段。
\quad\quad 人工缩进段。
"""
            source.write_text(text, encoding="utf-8")
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="paper-only"))
            auditor.source = source
            auditor.source_units = [(source, text)]
            auditor.audit_latex_indentation()
            findings = {
                item.check_id: item for item in auditor.findings
                if item.check_id in {"INDENT-006", "INDENT-007"}
            }
            self.assertEqual({"INDENT-006", "INDENT-007"}, set(findings))
            self.assertTrue(all(item.priority == "P3" for item in findings.values()))

    def test_stage_status_is_exposed_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="paper-only"))
            auditor.add(
                "P1", "FORMULA-TEST", "论文公式与定义冲突", "Q3", "证据", "规则",
                "FULL 核对代码后再决定是否重算。", stage_status="NEED_CODE_CONFIRMATION",
            )
            payload, report = auditor.build_report()
            finding = next(item for item in payload["findings"] if item["check_id"] == "FORMULA-TEST")
            self.assertEqual("NEED_CODE_CONFIRMATION", finding["stage_status"])
            self.assertIn("阶段状态：NEED_CODE_CONFIRMATION", report)
            self.assertIn("## Deferred to FULL / Drawing / Out of Scope", report)
            self.assertLess(
                report.index("## Audit Coverage（PAPER_ONLY 自动预审）"),
                report.index("## Deferred to FULL / Drawing / Out of Scope"),
            )


class PaperOnlyCoverageAndCitationTests(unittest.TestCase):
    def test_manual_reference_candidate_excludes_math_interval(self) -> None:
        text = r"变量满足 $x\in[4,5]$。这种方法属于词典序多目标优化方法（2）。"
        tokens = audit_submission.manual_numeric_reference_tokens(text)
        self.assertNotIn("[4,5]", {item["token"] for item in tokens})
        hand_typed = next(item for item in tokens if item["token"] == "（2）")
        self.assertTrue(hand_typed["citation_like"])

    def test_reference_format_coverage_does_not_pass_from_key_count_alone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name)))
            auditor.passed("REF-008", "citation keys correspond")
            row = next(item for item in auditor.build_paper_only_coverage() if item["module"] == "引用格式")
            self.assertEqual("UNVERIFIED", row["status"])

    def test_missing_pdf_citation_links_is_confirmed_p1_when_source_uses_cite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "paper.tex"
            paper = root / "paper.pdf"
            source.write_text(r"正文引用\cite{a}。", encoding="utf-8")
            paper.write_bytes(b"%PDF-1.4\n")
            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.source = source
            auditor.source_text = source.read_text(encoding="utf-8")
            auditor.source_units = [(source, auditor.source_text)]
            auditor.paper = paper
            with patch.object(
                audit_submission,
                "inspect_pdf_reference_links",
                return_value={"reference_start_page": 2, "links": []},
            ):
                auditor.audit_pdf_reference_links()
            finding = next(item for item in auditor.findings if item.check_id == "REF-LINK-004")
            self.assertEqual("P1", finding.priority)
            self.assertEqual("DETERMINISTIC", finding.certainty)

    def test_parenthesized_body_link_conflicts_with_bracketed_bibliography(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "paper.tex"
            paper = root / "paper.pdf"
            source.write_text("该方法见（2）。", encoding="utf-8")
            paper.write_bytes(b"%PDF-1.4\n")
            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.source = source
            auditor.source_text = source.read_text(encoding="utf-8")
            auditor.source_units = [(source, auditor.source_text)]
            auditor.paper = paper
            auditor.paper_text = "参考文献\n[2] 示例文献"
            with patch.object(
                audit_submission,
                "inspect_pdf_reference_links",
                return_value={
                    "reference_start_page": 2,
                    "links": [{"source_page": 1, "target_page": 2, "display": "（2）"}],
                },
            ):
                auditor.audit_pdf_reference_links()
            finding = next(item for item in auditor.findings if item.check_id == "REF-LINK-007")
            self.assertEqual("P1", finding.priority)
            self.assertEqual("DETERMINISTIC", finding.certainty)

    def test_paper_only_script_report_contains_citation_matrix_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name)))
            _, report = auditor.build_report()
            self.assertIn("## PAPER_ONLY 强制执行顺序", report)
            self.assertIn("## Audit Coverage（PAPER_ONLY 自动预审）", report)
            self.assertIn("## 术语一致性矩阵（PAPER_ONLY 待语义审查填写）", report)
            self.assertIn("## 引用完整性矩阵（PAPER_ONLY 待语义审查填写）", report)
            self.assertIn("当前句子声称什么", report)


class DeterministicConsistencyTests(unittest.TestCase):
    def test_table_comparison_respects_numeric_tolerance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            generated = root / "generated.csv"
            frozen = root / "frozen.csv"
            generated.write_text("id,value\nA,1.0000004\n", encoding="utf-8")
            frozen.write_text("id,value\nA,1.0\n", encoding="utf-8")
            result = audit_submission.compare_tables(
                generated,
                frozen,
                sheet=None,
                atol=1e-6,
                rtol=0.0,
                key_columns=["id"],
                ignore_columns=None,
            )
            self.assertIsNotNone(result)
            self.assertTrue(result["equal"])

    def test_table_comparison_detects_out_of_tolerance_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            generated = root / "generated.csv"
            frozen = root / "frozen.csv"
            generated.write_text("id,value\nA,1.2\n", encoding="utf-8")
            frozen.write_text("id,value\nA,1.0\n", encoding="utf-8")
            result = audit_submission.compare_tables(
                generated,
                frozen,
                sheet=None,
                atol=1e-6,
                rtol=0.0,
                key_columns=["id"],
                ignore_columns=None,
            )
            self.assertIsNotNone(result)
            self.assertFalse(result["equal"])

    def test_duplicate_label_remains_deterministic_p1(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.audit_duplicate_labels(r"\label{fig:a}\label{fig:a}")
            finding = next(item for item in auditor.findings if item.check_id == "LATEX-001")
            self.assertEqual("P1", finding.priority)
            self.assertEqual("DETERMINISTIC", finding.certainty)


class PaperOnlyCitationAndCoverageTests(unittest.TestCase):
    def test_extended_citation_commands_are_recognized_but_numeric_interval_is_not(self) -> None:
        text = r"使用方法\parencite{alpha,beta}，并比较结论\supercite{gamma}；变量范围为 [4,5]。"
        commands = audit_submission.find_citation_commands(text)
        self.assertEqual(["parencite", "supercite"], [item["command"] for item in commands])
        self.assertEqual({"alpha", "beta", "gamma"}, {key for item in commands for key in item["keys"]})
        self.assertNotIn("[4,5]", {key for item in commands for key in item["keys"]})

    def test_citation_command_inside_macro_definition_is_not_treated_as_real_key(self) -> None:
        text = r"\newcommand{\mycite}[1]{\cite{#1}} 正文没有引用。"
        self.assertEqual([], audit_submission.find_citation_commands(text))

    def test_bib_database_entries_do_not_count_until_cited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "paper.tex"
            bibliography = root / "refs.bib"
            source.write_text(r"正文\cite{k1}。\bibliography{refs}", encoding="utf-8")
            bibliography.write_text(
                "\n".join(f"@article{{k{index}, title={{T{index}}}}}" for index in range(1, 13)),
                encoding="utf-8",
            )
            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.source = source
            auditor.source_units = audit_submission.collect_latex_sources(source, root)
            auditor.files = [source, bibliography]
            auditor.audit_latex_references(auditor.source_units[0][1])
            finding = next(item for item in auditor.findings if item.check_id == "REF-002")
            self.assertIn("检测到 1 个", finding.evidence)

    def test_manual_citation_candidate_and_plain_interval_are_separated(self) -> None:
        text = "已有研究提出该模型具有稳定性[2]。变量取值范围为 [4,5]。"
        tokens = audit_submission.manual_numeric_reference_tokens(text)
        by_token = {item["token"]: item for item in tokens}
        self.assertTrue(by_token["[2]"]["citation_like"])
        self.assertFalse(by_token["[4,5]"]["citation_like"])

    def test_latex_indentation_evidence_finds_settings_overrides_and_manual_spacing(self) -> None:
        text = r"""
\setlength{\parindent}{2em}
正文第一段。
\noindent 正文第二段。
\quad\quad 人工缩进段。
"""
        evidence = audit_submission.latex_indentation_evidence(text)
        self.assertEqual("2em", evidence["settings"][0]["value"])
        self.assertEqual(1, len(evidence["noindent"]))
        self.assertEqual(1, len(evidence["manual_spacing"]))

    def test_latex_source_bundle_follows_input_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            main = root / "main.tex"
            section = root / "sections" / "q1.tex"
            section.parent.mkdir()
            main.write_text(r"\input{sections/q1}", encoding="utf-8")
            section.write_text(r"模型说明\parencite{model-key}。", encoding="utf-8")
            units = audit_submission.collect_latex_sources(main, root)
            self.assertEqual([main.resolve(), section.resolve()], [path for path, _ in units])
            self.assertEqual(
                ["model-key"],
                audit_submission.find_citation_commands("\n".join(text for _, text in units))[0]["keys"],
            )

    def test_paper_only_script_report_always_contains_all_coverage_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="paper-only"))
            auditor.add("P1", "REF-002", "参考文献少于 10 篇", "paper.tex", "1 篇", "规则", "补充")
            payload, report = auditor.build_report()
            coverage = payload["audit_coverage"]
            self.assertEqual(16, len(coverage))
            self.assertEqual(
                audit_submission.PAPER_ONLY_CORE_MODULES,
                tuple(item["module"] for item in coverage),
            )
            self.assertTrue(all(item["status"] in {"PASS", "WARN", "FAIL", "UNVERIFIED"} for item in coverage))
            reference_count = next(item for item in coverage if item["module"] == "参考文献数量与正文对应关系")
            self.assertEqual("FAIL", reference_count["status"])
            terminology = next(item for item in coverage if item["module"] == "术语一致性")
            self.assertEqual("UNVERIFIED", terminology["status"])
            self.assertIn("## Audit Coverage（PAPER_ONLY 自动预审）", report)

    def test_heuristic_p1_does_not_become_confirmed_script_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="full"))
            auditor.scope_incomplete = False
            auditor.warn("P1", "REF-X", "手工引用候选", "paper.tex:1", "[2]", "规则", "人工确认")
            self.assertEqual("SCRIPT_WARNINGS_FOUND", auditor.determine_script_status())

    def test_pdf_interval_link_to_bibliography_is_exposed_for_source_review(self) -> None:
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not installed")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paper = root / "paper.pdf"
            document = fitz.open()
            page_one = document.new_page()
            point = fitz.Point(72, 72)
            page_one.insert_text(point, "[4,5]")
            rect = fitz.Rect(70, 58, 112, 78)
            document.new_page().insert_text(fitz.Point(72, 72), "References")
            page_one = document[0]
            page_one.insert_link({"kind": fitz.LINK_GOTO, "from": rect, "page": 1, "to": fitz.Point(72, 72)})
            document.save(paper)
            document.close()

            auditor = audit_submission.SubmissionAudit(make_args(root))
            auditor.paper = paper
            auditor.source_text = "变量取值范围为 [4,5]。"
            auditor.audit_pdf_reference_links()
            finding = next(item for item in auditor.findings if item.check_id == "REF-LINK-005")
            self.assertEqual("P1", finding.priority)
            self.assertEqual("HEURISTIC", finding.certainty)


class FrozenPackageInterfaceTests(unittest.TestCase):
    def build_package(self, root: Path) -> Path:
        standard = {"version": "2026.09.01", "sha256": "a" * 64}
        roles = (
            "interpretation_final",
            "model_plan_final",
            "ambiguity_decisions",
            "granularity_contract",
            "hard_constraints",
            "interpretation_decisions",
            "model_assumptions",
        )
        handoff_names = [f"{role}.md" for role in roles]
        for name in (*handoff_names, "brief.md", "data.csv", "draw.py", "figure.png"):
            (root / name).write_text(name, encoding="utf-8")
        paper_ready = {
            "schema_version": 1,
            "status": "PAPER_READY",
            "standard": standard,
            "files": [
                {"role": role, "path": name, "sha256": audit_submission.sha256_file(root / name)}
                for role, name in zip(roles, handoff_names)
            ],
        }
        paper_ready_path = root / "paper_ready_manifest.json"
        paper_ready_path.write_text(json.dumps(paper_ready), encoding="utf-8")
        figure_manifest = {
            "schema_version": 2,
            "status": "FIGURES_READY",
            "standard": standard,
            "paper_ready_manifest_sha256": audit_submission.sha256_file(paper_ready_path),
            "assets": [
                {
                    "asset_id": "fig_q1_01",
                    "asset_type": "figure",
                    "brief_revision": 1,
                    "contract_ids": [],
                    "brief": {"path": "brief.md", "sha256": audit_submission.sha256_file(root / "brief.md")},
                    "brief_contract": {
                        "schema_version": 2,
                        "brief_type": "figure",
                        "asset_id": "fig_q1_01",
                        "revision": 1,
                        "status": "READY_FOR_DRAWING",
                        "standard_version": "2026.09.01",
                        "paper_ready_manifest_sha256": audit_submission.sha256_file(paper_ready_path),
                        "contract_ids": [],
                        "semantic_sha256": "b" * 64,
                        "body_context": {
                            "paper_source": {
                                "path": "brief.md",
                                "sha256": audit_submission.sha256_file(root / "brief.md"),
                            },
                            "before_sha256": "c" * 64,
                            "after_sha256": "d" * 64,
                        },
                        "data_sources": [{
                            "path": "data.csv",
                            "sha256": audit_submission.sha256_file(root / "data.csv"),
                            "fields": ["x", "y"],
                        }],
                    },
                    "data_sources": [{
                        "path": "data.csv",
                        "sha256": audit_submission.sha256_file(root / "data.csv"),
                        "fields": ["x", "y"],
                    }],
                    "script": {"path": "draw.py", "sha256": audit_submission.sha256_file(root / "draw.py")},
                    "outputs": [{"path": "figure.png", "sha256": audit_submission.sha256_file(root / "figure.png")}],
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
        figure_manifest_path = root / "figure_manifest.json"
        figure_manifest_path.write_text(json.dumps(figure_manifest), encoding="utf-8")
        frozen_paths = [
            *handoff_names,
            "brief.md",
            "data.csv",
            "draw.py",
            "figure.png",
            "paper_ready_manifest.json",
            "figure_manifest.json",
        ]
        audit_manifest = {
            "freeze_schema_version": 1,
            "frozen": True,
            "blockers": [],
            "standard": standard,
            "paper_ready_manifest": "paper_ready_manifest.json",
            "figure_manifest": "figure_manifest.json",
            "upstream_manifests": {
                "paper_ready": {
                    "path": "paper_ready_manifest.json",
                    "sha256": audit_submission.sha256_file(paper_ready_path),
                },
                "figures": {
                    "path": "figure_manifest.json",
                    "sha256": audit_submission.sha256_file(figure_manifest_path),
                },
            },
            "frozen_files": [
                {"path": name, "sha256": audit_submission.sha256_file(root / name), "categories": []}
                for name in frozen_paths
            ],
        }
        manifest_path = root / "audit_manifest.json"
        manifest_path.write_text(json.dumps(audit_manifest), encoding="utf-8")
        return manifest_path

    def test_full_requires_audit_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="full"))
            auditor.load_manifest()
            auditor.check_readiness()
            self.assertTrue(auditor.not_ready)
            self.assertIn("READY-003", {item.check_id for item in auditor.findings})

    def test_paper_only_does_not_gain_freeze_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            auditor = audit_submission.SubmissionAudit(make_args(Path(temp_name), mode="paper-only"))
            auditor.load_manifest()
            auditor.check_readiness()
            self.assertFalse(auditor.not_ready)

    def test_full_accepts_hash_verified_frozen_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            self.build_package(root)
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="full"))
            auditor.load_manifest()
            auditor.check_readiness()
            self.assertFalse(auditor.not_ready)
            self.assertIn("READY-006", {item["check_id"] for item in auditor.passes})

    def test_tampered_frozen_file_blocks_full(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            self.build_package(root)
            (root / "figure.png").write_text("tampered", encoding="utf-8")
            auditor = audit_submission.SubmissionAudit(make_args(root, mode="full"))
            auditor.load_manifest()
            auditor.check_readiness()
            self.assertTrue(auditor.not_ready)
            self.assertIn("READY-005", {item.check_id for item in auditor.findings})


if __name__ == "__main__":
    unittest.main()

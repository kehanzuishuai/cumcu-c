from __future__ import annotations

import copy
import importlib.util
import json
import re
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


def markdown_section(text: str, heading: str) -> str:
    """Return one Markdown section up to the next heading at the same/higher level."""
    marker = heading + "\n"
    start = text.index(marker) + len(marker)
    level = len(heading) - len(heading.lstrip("#"))
    remainder = text[start:]
    match = re.search(rf"(?m)^#{{1,{level}}} ", remainder)
    return remainder[: match.start()] if match else remainder


def markdown_table(section: str) -> list[dict[str, str]]:
    """Parse the first simple Markdown table in a section."""
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        raise AssertionError("Markdown table not found")

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip("|").split("|")]

    headers = cells(lines[0])
    rows = []
    for line in lines[2:]:
        values = cells(line)
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values)))
    return rows


inventory = load_module("inventory_problem", SKILL_ROOT / "scripts" / "inventory_problem.py")
validator = load_module(
    "validate_interpretation", SKILL_ROOT / "scripts" / "validate_interpretation.py"
)


class ScriptTests(unittest.TestCase):
    def write_contract(self, directory: Path, name: str, contract: dict) -> Path:
        path = directory / name
        path.write_text(
            "```contract-json\n"
            + json.dumps(contract, ensure_ascii=False, indent=2)
            + "\n```\n",
            encoding="utf-8",
        )
        return path

    def test_inventory_reports_files_and_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "records.csv").write_text("id,value\n1,2\n", encoding="utf-8")
            (root / "metadata.json").write_text('{"unit": "kg"}', encoding="utf-8")

            report = inventory.build_inventory(root)

            self.assertIn("records.csv", report)
            self.assertIn("表头=id, value", report)
            self.assertIn("metadata.json", report)
            self.assertIn("keys=unit", report)

    def test_validator_accepts_synthetic_report(self):
        report = SKILL_ROOT / "tests" / "fixtures" / "minimal_report.md"

        result = validator.inspect(report, expected_subproblems=1)

        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(result["detected_subproblems"], [1])
        self.assertEqual(result["placeholder_count"], 0)

    def test_anonymized_example_runs_end_to_end(self):
        example = SKILL_ROOT / "examples" / "anonymized-problem"
        report = example / "interpretation_final.md"

        result = validator.inspect(
            report,
            expected_subproblems=3,
            stage="final",
            ambiguities=example / "ambiguity_decisions.md",
            granularity_contract=example / "granularity_contract.md",
            hard_constraints=example / "hard_constraints.md",
            interpretation_decisions=example / "interpretation_decisions.md",
            model_assumptions=example / "model_assumptions.md",
            model_plan=example / "model_plan_final.md",
        )

        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(result["interpretation_status"], "PAPER_READY")
        self.assertEqual(result["detected_subproblems"], [1, 2, 3])
        self.assertEqual(result["placeholder_count"], 0)

        self.assertEqual(len(result["evidence_tags"]), 7)
        self.assertEqual(
            set(result["contract_checks"]["loaded_contracts"]),
            {
                "ambiguities",
                "granularity_contract",
                "hard_constraints",
                "interpretation_decisions",
                "model_assumptions",
                "model_plan",
            },
        )
        self.assertEqual(result["contract_checks"]["ambiguities"]["count"], 0)
        self.assertEqual(
            result["contract_checks"]["model_plan"]["granularity_conflicts"], []
        )
        self.assertEqual(
            result["contract_checks"]["model_plan"]["missing_hard_constraints"], []
        )
        self.assertEqual(result["contract_checks"]["model_assumptions"]["count"], 2)
        self.assertEqual(result["contract_checks"]["interpretation_decision_count"], 2)
        self.assertEqual(result["final_document_state"]["stale"], [])
        self.assertEqual(
            {Path(path).name for path in result["final_document_state"]["documents"]},
            {
                "interpretation_final.md",
                "ambiguity_decisions.md",
                "granularity_contract.md",
                "hard_constraints.md",
                "interpretation_decisions.md",
                "model_assumptions.md",
                "model_plan_final.md",
            },
        )
        self.assertTrue((example / "model_plan_final.md").is_file())
        self.assertFalse((example / "interpretation_draft.md").exists())

        draft = (example / "_archive" / "interpretation_draft.md").read_text(encoding="utf-8")
        self.assertIn("INTERPRETATION_PENDING", draft)

        inventory_report = inventory.build_inventory(example)
        self.assertIn("observations.csv", inventory_report)
        self.assertIn("zones.csv", inventory_report)
        self.assertIn("result_template.csv", inventory_report)

        audit = json.loads((example / "attachment_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "complete")
        self.assertEqual(len(audit["files"]), 3)
        self.assertTrue(all(item["audit_status"] == "verified" for item in audit["files"]))
        for item in audit["files"]:
            payload = (example / item["path"]).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(len(payload), item["size_bytes"])

        acceptance = (example / "acceptance_report.md").read_text(encoding="utf-8")
        self.assertIn("得分率：100%", acceptance)
        self.assertIn("实得分：28", acceptance)
        self.assertIn("当前可评分项满分：28", acceptance)
        legacy_fixed_score = "20" + "/" + "20"
        self.assertNotIn(legacy_fixed_score, acceptance)

        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("--stage final", readme)
        self.assertIn("--interpretation-decisions", readme)
        self.assertIn("--model-assumptions", readme)
        self.assertNotIn(legacy_fixed_score, readme)

    def test_skill_routes_are_single_problem_only(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        output_schema = (SKILL_ROOT / "references" / "output-schema.md").read_text(
            encoding="utf-8"
        )

        route_section = skill.split("## 单题工作深度", 1)[1].split(
            "## 输入与独立性", 1
        )[0]
        self.assertEqual(
            re.findall(r"^- \*\*([^*]+)\*\*", route_section, flags=re.MULTILINE),
            ["full", "re-review", "paper-ready"],
        )
        self.assertIn("只处理题号已经确定的一道 C 题", skill)
        self.assertIn("只处理题号已经确定的一道 C 题", readme)
        self.assertIn("禁止读取任何 backup/archive 目录（包括 `_archive/`）", skill)
        self.assertTrue(output_schema.startswith("# 输出结构\n\n## 完整解读主报告"))
        self.assertTrue((SKILL_ROOT / "references" / "problem-type-guides.md").is_file())

    def test_task_metrics_route_by_output_and_error_cost(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        rows = {
            row["任务"]: row
            for row in markdown_table(markdown_section(guide, "### 评价指标路由速查"))
        }

        self.assertIn("Brier", rows["分类"]["主比较/验证指标"])
        self.assertIn("PR-AUC", rows["分类"]["必须同时检查"])
        self.assertIn("optimality gap", rows["优化/启发式"]["必须同时检查"])
        self.assertIn("分组稳定性", rows["聚类"]["必须同时检查"])
        self.assertIn("步长/求解精度收敛", rows["ODE 动态系统"]["必须同时检查"])

    def test_ode_route_requires_rate_mechanism_and_numerical_convergence(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 微分方程模型路由")
        rows = {row["证据结构"]: row for row in markdown_table(section)}

        continuous = rows["连续状态 + 可写出的变化率/守恒关系"]
        self.assertIn("ODE", continuous["优先路线"])
        self.assertIn("Euler", continuous["优先路线"])
        self.assertIn("RK4", continuous["优先路线"])
        observed = rows["只有观测序列，目标是样本外预测"]
        self.assertIn("时间序列/回归预测优先", observed["优先路线"])
        self.assertIn("否则不把拟合曲线解释为 ODE", observed["方案中必须固定"])
        self.assertIn("减小步长或提高求解精度后关键输出稳定", section)

    def test_statistical_test_route_preserves_pairing_and_multiple_testing_scope(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 统计检验细化路由")
        rows = {row["数据/问题结构"]: row for row in markdown_table(section)}

        paired = rows["配对或同一对象前后比较，参数条件不足"]
        self.assertIn("Wilcoxon 符号秩检验", paired["候选检验或模型"])
        self.assertIn("不能拆成两组独立样本", paired["关键防错"])
        self.assertIn("条件/控制相关", rows["存在共同混杂因素"]["候选检验或模型"])
        self.assertIn("多重检验校正", rows["同时检验多组变量或多重比较"]["候选检验或模型"])
        self.assertIn("不能仅凭 `p < 0.05` 冻结主模型", section)

    def test_glm_routes_follow_response_support_not_model_preference(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 统计与回归候选模型路由")
        rows = {row["方法"]: row for row in markdown_table(section)}

        self.assertEqual(
            set(rows),
            {
                "Bayesian/MCMC",
                "Poisson GLM",
                "Logistic GLM",
                "Gamma GLM",
                "分位数回归",
                "稳健回归",
                "Elastic Net",
                "GPR",
                "LMM",
                "NLME",
                "GEE",
                "VIKOR",
                "QDA",
                "GARCH",
                "无监督异常检测",
            },
        )

        self.assertIn("非负整数计数", rows["Poisson GLM"]["进入候选的数据结构/任务"])
        self.assertIn("平均率", rows["Poisson GLM"]["简单基线"])
        self.assertIn("过度离散", rows["Poisson GLM"]["必须验证"])
        self.assertIn("零膨胀", rows["Poisson GLM"]["必须验证"])
        self.assertIn("二分类或二项比例", rows["Logistic GLM"]["进入候选的数据结构/任务"])
        self.assertIn("校准与 Brier", rows["Logistic GLM"]["必须验证"])
        self.assertIn("严格为正、连续且右偏", rows["Gamma GLM"]["进入候选的数据结构/任务"])
        self.assertIn("log-OLS", rows["Gamma GLM"]["简单基线"])

    def test_regression_upgrades_keep_simple_baselines_and_failure_checks(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 统计与回归候选模型路由")
        rows = {row["方法"]: row for row in markdown_table(section)}

        self.assertIn("上下尾部", rows["分位数回归"]["进入候选的数据结构/任务"])
        self.assertIn("OLS", rows["分位数回归"]["简单基线"])
        self.assertIn("pinball loss", rows["分位数回归"]["必须验证"])
        self.assertIn("高影响观测", rows["稳健回归"]["进入候选的数据结构/任务"])
        self.assertIn("不能用它掩盖数据错误", rows["稳健回归"]["必须验证"])
        self.assertIn("Ridge、Lasso", rows["Elastic Net"]["简单基线"])
        self.assertIn("嵌套调参", rows["Elastic Net"]["必须验证"])
        self.assertIn("小到中等样本", rows["GPR"]["进入候选的数据结构/任务"])
        self.assertIn("预测区间覆盖", rows["GPR"]["必须验证"])
        self.assertIn("外推失效边界", rows["GPR"]["必须验证"])

    def test_bayesian_and_clustered_routes_define_convergence_and_estimand(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 统计与回归候选模型路由")
        rows = {row["方法"]: row for row in markdown_table(section)}

        bayes = rows["Bayesian/MCMC"]
        self.assertIn("先验可审计", bayes["进入候选的数据结构/任务"])
        self.assertIn("MLE", bayes["简单基线"])
        self.assertIn("R-hat", bayes["必须验证"])
        self.assertIn("ESS/MC 误差", bayes["必须验证"])
        self.assertIn("后验预测检查", bayes["必须验证"])

        self.assertIn("主体特异效应", rows["LMM"]["进入候选的数据结构/任务"])
        self.assertIn("忽略聚类的 OLS", rows["LMM"]["简单基线"])
        self.assertIn("按主体切分", rows["LMM"]["必须验证"])
        self.assertIn("非线性形态", rows["NLME"]["进入候选的数据结构/任务"])
        self.assertIn("可识别性", rows["NLME"]["必须验证"])
        self.assertIn("总体平均效应", rows["GEE"]["进入候选的数据结构/任务"])
        self.assertIn("工作相关结构敏感性", rows["GEE"]["必须验证"])

    def test_specialized_routes_require_structure_specific_validation(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 统计与回归候选模型路由")
        rows = {row["方法"]: row for row in markdown_table(section)}

        self.assertIn("最差指标遗憾", rows["VIKOR"]["进入候选的数据结构/任务"])
        self.assertIn("TOPSIS", rows["VIKOR"]["简单基线"])
        self.assertIn("妥协参数敏感性", rows["VIKOR"]["必须验证"])
        self.assertIn("各类协方差结构明显不同", rows["QDA"]["进入候选的数据结构/任务"])
        self.assertIn("Logistic 与 LDA", rows["QDA"]["简单基线"])
        self.assertIn("波动聚集", rows["GARCH"]["进入候选的数据结构/任务"])
        self.assertIn("样本外波动损失", rows["GARCH"]["必须验证"])
        self.assertIn("业务硬规则", rows["无监督异常检测"]["简单基线"])
        self.assertIn("无标签时不虚报 Accuracy/F1", rows["无监督异常检测"]["必须验证"])

    def test_extended_nonparametric_and_assumption_tests_follow_design(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 统计检验细化路由")
        rows = {row["数据/问题结构"]: row for row in markdown_table(section)}

        independent_two = rows["两个独立样本，连续/有序结果不满足参数条件"]
        self.assertIn("Mann–Whitney U", independent_two["候选检验或模型"])
        self.assertIn("不能与配对 Wilcoxon", independent_two["关键防错"])
        self.assertIn(
            "Kruskal–Wallis",
            rows["三个及以上独立样本不满足 ANOVA 条件"]["候选检验或模型"],
        )
        self.assertIn(
            "Friedman",
            rows["同一对象在三个及以上条件/时点重复测量，参数条件不足"]["候选检验或模型"],
        )
        self.assertIn("Shapiro–Wilk", rows["回归/组间比较需要检查正态前提"]["候选检验或模型"])
        self.assertIn("优先检查模型残差", rows["回归/组间比较需要检查正态前提"]["关键防错"])
        self.assertIn("Levene", rows["组间比较需要检查方差齐性"]["候选检验或模型"])
        self.assertIn("Bartlett 对非正态敏感", rows["组间比较需要检查方差齐性"]["关键防错"])
        self.assertIn("Kendall 秩相关", rows["有序等级、秩次关系、小样本或并列秩较多"]["候选检验或模型"])

    def test_solver_route_matches_structure_and_preserves_hard_constraints(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 优化求解器与工程化路线")
        rows = {row["数学结构"]: row for row in markdown_table(section)}

        self.assertIn("HiGHS", rows["MILP"]["优先求解路线"])
        self.assertIn("SCIP", rows["MILP"]["优先求解路线"])
        self.assertIn(
            "CP-SAT/OR-Tools",
            rows["逻辑和排程占主导的整数问题"]["优先求解路线"],
        )
        self.assertIn("不宣称未经证明的全局最优", rows["MINLP 或复杂非凸模型"]["必须报告的证据"])
        self.assertIn("是否保持全部 HARD 约束", section)
        self.assertIn("压缩前后规模", section)

    def test_multiobjective_route_separates_generation_from_compromise_choice(self):
        guide = (SKILL_ROOT / "references" / "problem-type-guides.md").read_text(
            encoding="utf-8"
        )
        section = markdown_section(guide, "### 多目标方法路由")
        rows = {row["优先候选"]: row for row in markdown_table(section)}

        self.assertIn("payoff table", rows["ε-约束法"]["使用边界与验证"])
        self.assertIn("ε 步长敏感性", rows["ε-约束法"]["使用边界与验证"])
        self.assertIn("弱有效解或重复解", rows["AUGMECON2"]["结构与目的"])
        self.assertIn("最终折中选择与前沿生成分开说明", rows["AUGMECON2"]["使用边界与验证"])
        self.assertIn("输出确为非支配方案", section)
        self.assertIn("应保留更简单路线", section)

        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        methodology = (SKILL_ROOT / "references" / "methodology.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("这些选择仍属于模型设计，不改变歧义与冻结规则", skill)
        self.assertIn("不改变 final 冻结合同或 `PAPER_READY` 门禁", methodology)

    def test_model_routing_tree_uses_structure_before_keywords(self):
        tree = (SKILL_ROOT / "references" / "model-routing-tree.md").read_text(
            encoding="utf-8"
        )
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

        for dimension in (
            "数据结构",
            "题目动作",
            "变量类型",
            "不确定性",
            "特殊结构",
            "规模与可解性",
        ):
            self.assertIn(dimension, tree)
        self.assertIn("动作词只能提示任务，不能单独触发模型", tree)
        self.assertIn("优先精确结构：解析式/图算法/LP/MILP/网络流/DP/CP-SAT", tree)
        self.assertIn("model-routing-tree.md", skill)
        self.assertLessEqual(len(skill.splitlines()), 175)

    def test_new_route_cards_follow_the_unified_competition_schema(self):
        labels = (
            "适用任务/触发条件",
            "数据结构与前提检查",
            "朴素基线",
            "主模型/必要候选",
            "核心变量与数学结构",
            "推荐求解方法/软件",
            "必做验证",
            "灵敏度或稳健性",
            "常见误用",
            "失败后的降级/替代方案",
            "与下一问可能的接口",
        )
        cards = {
            "operations-state-routes.md": (
                "图与网络模型",
                "排队模型",
                "马尔可夫链",
                "库存/存贮模型",
                "目标规划",
                "动态规划",
                "生产与任务调度",
                "稳态模型与离散差分模型",
            ),
            "data-evaluation-routes.md": (
                "灰色预测 GM(1,1)",
                "模糊综合评价",
                "DEA 数据包络分析",
                "插值与函数拟合",
                "PCA、因子分析、PLS、CCA 与 LDA 选择路由",
                "聚类模型选择与验证",
            ),
            "heuristic-routing.md": (
                "GA、PSO、SA、ACO、Tabu、NSGA-II 路由",
            ),
        }
        for filename, headings in cards.items():
            text = (SKILL_ROOT / "references" / filename).read_text(encoding="utf-8")
            for title in headings:
                with self.subTest(filename=filename, title=title):
                    section = markdown_section(text, f"## {title}")
                    for label in labels:
                        self.assertIn(f"**{label}：**", section)

    def test_network_queue_inventory_and_scheduling_routes_have_fatal_checks(self):
        guide = (
            SKILL_ROOT / "references" / "operations-state-routes.md"
        ).read_text(encoding="utf-8")

        graph = markdown_section(guide, "## 图与网络模型")
        for algorithm in (
            "Dijkstra",
            "Floyd",
            "Bellman-Ford",
            "Prim/Kruskal",
            "最大流",
            "最小费用流",
            "二分图匹配",
            "选址—配送",
        ):
            self.assertIn(algorithm, graph)
        self.assertIn("最大流与最小割值交叉核对", graph)

        queue = markdown_section(guide, "## 排队模型")
        self.assertIn("M/M/1", queue)
        self.assertIn("M/M/c", queue)
        self.assertIn("Little 定律", queue)
        self.assertIn("离散事件仿真", queue)

        inventory = markdown_section(guide, "## 库存/存贮模型")
        for model in ("EOQ", "EPQ", "数量折扣", "报童模型"):
            self.assertIn(model, inventory)
        self.assertIn("需求分布或情景", inventory)

        scheduling = markdown_section(guide, "## 生产与任务调度")
        self.assertIn("Flow Shop", scheduling)
        self.assertIn("Job Shop", scheduling)
        self.assertIn("MILP 或 CP-SAT", scheduling)
        self.assertIn("上下界/gap", scheduling)

    def test_gm_fuzzy_dea_projection_and_clustering_routes_are_guarded(self):
        guide = (
            SKILL_ROOT / "references" / "data-evaluation-routes.md"
        ).read_text(encoding="utf-8")

        gm = markdown_section(guide, "## 灰色预测 GM(1,1)")
        self.assertIn("级比", gm)
        self.assertIn("最近值", gm)
        self.assertIn("滚动/留后验证", gm)

        fuzzy = markdown_section(guide, "## 模糊综合评价")
        self.assertIn("真实模糊边界", fuzzy)
        self.assertIn("隶属函数", fuzzy)
        self.assertIn("透明标准化评分", fuzzy)

        dea = markdown_section(guide, "## DEA 数据包络分析")
        self.assertIn("多个同类决策单元 DMU", dea)
        self.assertIn("CCR", dea)
        self.assertIn("BCC", dea)
        self.assertIn("投入冗余", dea)

        projection = markdown_section(
            guide, "## PCA、因子分析、PLS、CCA 与 LDA 选择路由"
        )
        self.assertIn("PCA 只最大化 X 方差", projection)
        self.assertIn("PLS 需要响应 Y", projection)
        self.assertIn("CCA 需要两组变量", projection)
        self.assertIn("LDA 需要可靠类别标签", projection)

        clustering = markdown_section(guide, "## 聚类模型选择与验证")
        self.assertIn("K-means", clustering)
        self.assertIn("DBSCAN/HDBSCAN", clustering)
        self.assertIn("GMM", clustering)
        self.assertIn("扰动/重采样/不同初始化后的稳定性", clustering)

    def test_heuristics_require_exact_structure_and_multi_seed_evidence(self):
        guide = (SKILL_ROOT / "references" / "heuristic-routing.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("LP、MILP、网络流、动态规划或 CP-SAT", guide)
        self.assertIn("多个独立随机种子", guide)
        self.assertIn("可行率", guide)
        self.assertIn("小规模精确解", guide)
        self.assertIn("收敛曲线只能作为运行诊断", guide)
        self.assertIn("不得宣称全局最优", guide)

    def test_release_fixture_paths_are_ascii_safe(self):
        for name in ("2024c-regression", "2023c-style-regression"):
            fixture = SKILL_ROOT / "tests" / "fixtures" / name
            for path in fixture.rglob("*"):
                relative = path.relative_to(SKILL_ROOT)
                with self.subTest(path=str(relative)):
                    str(relative).encode("ascii")

    def test_acceptance_rubric_uses_dynamic_score_rate(self):
        rubric = (SKILL_ROOT / "references" / "acceptance-rubric.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("总得分率", rubric)
        self.assertIn("ceil(0.9 × 满分)", rubric)
        self.assertIn("所有 P0 项均为 `2` 分", rubric)
        self.assertNotIn("18/20", rubric)
        self.assertNotIn("按十项评分", rubric)

    def test_unique_high_evidence_must_be_resolved_without_user_confirmation(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=3,
            stage="final",
            ambiguities=fixture / "ambiguity_resolved.md",
            granularity_contract=fixture / "granularity_contract.md",
            hard_constraints=fixture / "hard_constraints.md",
            interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            model_plan=fixture / "model_plan_valid_final.md",
            model_assumptions=fixture / "model_assumptions_empty.md",
        )

        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(result["interpretation_status"], "PAPER_READY")
        self.assertEqual(result["contract_checks"]["ambiguities"]["blocking"], [])
        self.assertEqual(result["contract_checks"]["model_assumptions"]["count"], 0)

        ambiguity = validator.extract_contract(
            fixture / "ambiguity_resolved.md", "ambiguity_decisions"
        )["items"][0]
        self.assertIn("data_granularity", ambiguity["impact"])
        self.assertEqual(ambiguity["evidence"][0]["value"], ["crop", "year", "season"])
        self.assertEqual(ambiguity["status"], "RESOLVED_BY_EVIDENCE")
        self.assertIsNone(ambiguity["approved_by"])

    def test_final_stage_requires_all_freeze_contracts(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=3,
            stage="final",
        )

        self.assertFalse(result["pass"])
        self.assertEqual(result["interpretation_status"], "INTERPRETATION_PENDING")
        self.assertGreaterEqual(
            sum("missing contract" in error for error in result["errors"]), 6
        )

    def test_final_requires_interpretation_decisions_contract_even_when_empty(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=3,
            stage="final",
            ambiguities=fixture / "ambiguity_resolved.md",
            granularity_contract=fixture / "granularity_contract.md",
            hard_constraints=fixture / "hard_constraints.md",
            model_plan=fixture / "model_plan_valid_final.md",
            model_assumptions=fixture / "model_assumptions_empty.md",
        )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any("missing contract: interpretation_decisions" in error for error in result["errors"])
        )

    def test_final_requires_model_assumptions_contract_even_when_empty(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=3,
            stage="final",
            ambiguities=fixture / "ambiguity_resolved.md",
            granularity_contract=fixture / "granularity_contract.md",
            hard_constraints=fixture / "hard_constraints.md",
            interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            model_plan=fixture / "model_plan_valid_final.md",
        )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any("missing contract: model_assumptions" in error for error in result["errors"])
        )

    def test_2024c_explicit_each_season_evidence_cannot_be_overridden(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=3,
            stage="final",
            ambiguities=fixture / "ambiguity_override.md",
            granularity_contract=fixture / "granularity_contract.md",
            hard_constraints=fixture / "hard_constraints.md",
            model_plan=fixture / "model_plan_valid_final.md",
            model_assumptions=fixture / "model_assumptions_empty.md",
            interpretation_decisions=fixture / "interpretation_decisions_empty.md",
        )

        self.assertFalse(result["pass"])
        self.assertIn(
            "sales_limit_period",
            result["contract_checks"]["ambiguities"]["evidence_overrides"],
        )
        self.assertTrue(any("P0 EVIDENCE_OVERRIDE" in error for error in result["errors"]))

    def test_2024c_evidence_resolved_each_season_contract_passes(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=3,
            stage="final",
            ambiguities=fixture / "ambiguity_resolved.md",
            granularity_contract=fixture / "granularity_contract.md",
            hard_constraints=fixture / "hard_constraints.md",
            model_plan=fixture / "model_plan_valid_final.md",
            model_assumptions=fixture / "model_assumptions_empty.md",
            interpretation_decisions=fixture / "interpretation_decisions_empty.md",
        )

        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(result["interpretation_status"], "PAPER_READY")
        self.assertEqual(
            result["contract_checks"]["model_plan"]["granularity_conflicts"], []
        )

        ambiguity = validator.extract_contract(
            fixture / "ambiguity_resolved.md", "ambiguity_decisions"
        )["items"][0]
        sales_limit = validator.extract_contract(
            fixture / "granularity_contract.md", "granularity_contract"
        )["items"][1]
        model_plan = validator.extract_contract(
            fixture / "model_plan_valid_final.md", "model_plan"
        )["items"][1]
        self.assertEqual(ambiguity["decision"], ["crop", "year", "season"])
        self.assertEqual(sales_limit["dimensions"], ["crop", "year", "season"])
        self.assertEqual(model_plan["dimensions"], ["crop", "year", "season"])
        self.assertEqual(model_plan["symbol"], "D[c,t,s]")

    def test_resolved_ambiguity_with_stale_final_language_is_blocked_then_passes_when_cleaned(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        clean_report = (fixture / "interpretation_final.md").read_text(encoding="utf-8")
        clean_plan = (fixture / "model_plan_valid_final.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "interpretation_final.md"
            plan = root / "model_plan_final.md"
            report.write_text(
                clean_report
                + "\nAMB-01 待确认；方案 A/B 待选；当前仍存在 BLOCKING；"
                + "仍并列保留 A/B 两种题意口径。\n",
                encoding="utf-8",
            )
            plan.write_text(clean_plan, encoding="utf-8")

            stale_result = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )

            self.assertFalse(stale_result["pass"])
            self.assertEqual(stale_result["interpretation_status"], "INTERPRETATION_PENDING")
            self.assertTrue(
                any("P0 STALE_DECISION_STATE" in error for error in stale_result["errors"])
            )
            markers = {
                item["marker"] for item in stale_result["final_document_state"]["stale"]
            }
            self.assertTrue(
                {
                    "待确认",
                    "BLOCKING",
                    "A/B_PENDING_SELECTION",
                    "RESOLVED_AMBIGUITY_OPTIONS",
                }.issubset(markers)
            )

            report.write_text(
                clean_report
                + "\n冻结摘要：BLOCKING=0，UNRESOLVED=0，无待确认项，待决定项=0，无待实现确认项。\n",
                encoding="utf-8",
            )
            clean_result = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )

            self.assertTrue(clean_result["pass"], clean_result["errors"])
            self.assertEqual(clean_result["interpretation_status"], "PAPER_READY")
            self.assertEqual(clean_result["final_document_state"]["stale"], [])

    def test_final_requires_top_level_draft_to_be_archived(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "interpretation_final.md"
            plan = root / "model_plan_final.md"
            draft = root / "interpretation_draft.md"
            report.write_text(
                (fixture / "interpretation_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            plan.write_text(
                (fixture / "model_plan_valid_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            draft.write_text("# INTERPRETATION_PENDING\n", encoding="utf-8")

            blocked = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )
            self.assertFalse(blocked["pass"])
            self.assertTrue(
                any(
                    item["marker"] == "UNARCHIVED_DRAFT"
                    for item in blocked["final_document_state"]["stale"]
                )
            )

            archive = root / "_archive"
            archive.mkdir()
            draft.rename(archive / draft.name)
            passed = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )
            self.assertTrue(passed["pass"], passed["errors"])
            self.assertEqual(passed["interpretation_status"], "PAPER_READY")

    def test_stale_draft_language_in_any_markdown_contract_blocks_then_clean_passes(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "interpretation_final.md"
            plan = root / "model_plan_final.md"
            hard = root / "hard_constraints.md"
            report.write_text(
                (fixture / "interpretation_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            plan.write_text(
                (fixture / "model_plan_valid_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            clean_hard = (fixture / "hard_constraints.md").read_text(encoding="utf-8")
            hard.write_text(
                clean_hard + "\n状态：DRAFT；当前为草稿；确认后升级；待冻结。\n",
                encoding="utf-8",
            )

            stale = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=hard,
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )
            markers = {item["marker"] for item in stale["final_document_state"]["stale"]}
            self.assertFalse(stale["pass"])
            self.assertTrue({"DRAFT", "草稿", "确认后升级", "待冻结"}.issubset(markers))
            self.assertTrue(any("STALE_DECISION_STATE" in error for error in stale["errors"]))
            self.assertIn(str(hard.resolve()), stale["final_document_state"]["documents"])

            hard.write_text(clean_hard, encoding="utf-8")
            clean = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=hard,
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )
            self.assertTrue(clean["pass"], clean["errors"])
            self.assertEqual(clean["interpretation_status"], "PAPER_READY")
            self.assertEqual(clean["final_document_state"]["stale"], [])

    def test_backup_directory_must_leave_handoff_but_archive_is_ignored(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handoff = root / "handoff"
            handoff.mkdir()
            report = handoff / "interpretation_final.md"
            plan = handoff / "model_plan_final.md"
            report.write_text(
                (fixture / "interpretation_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            plan.write_text(
                (fixture / "model_plan_valid_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            backup = handoff / "history" / "draft_backup"
            backup.mkdir(parents=True)
            (backup / "old.md").write_text("# DRAFT\n", encoding="utf-8")

            blocked = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )
            self.assertFalse(blocked["pass"])
            self.assertTrue(
                any(
                    item["marker"] == "BACKUP_DIRECTORY_IN_HANDOFF"
                    for item in blocked["final_document_state"]["stale"]
                )
            )

            backup.rename(root / "draft_backup")
            archive = handoff / "_archive"
            archive.mkdir()
            (archive / "interpretation_draft.md").write_text(
                "# INTERPRETATION_PENDING DRAFT 草稿\n",
                encoding="utf-8",
            )
            passed = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=plan,
            )
            self.assertTrue(passed["pass"], passed["errors"])
            self.assertEqual(passed["interpretation_status"], "PAPER_READY")
            self.assertEqual(passed["final_document_state"]["stale"], [])

    def test_final_requires_regenerated_model_plan_filename(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "interpretation_final.md"
            old_plan = root / "model_plan.md"
            report.write_text(
                (fixture / "interpretation_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            old_plan.write_text(
                (fixture / "model_plan_valid_final.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = validator.inspect(
                report,
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                model_plan=old_plan,
            )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any(
                item["marker"] == "FINAL_NAME_REQUIRED"
                for item in result["final_document_state"]["stale"]
            )
        )
        self.assertTrue(any("STALE_DECISION_STATE" in error for error in result["errors"]))

    def test_2024c_cross_season_sales_limit_triggers_p0_conflict(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=3,
            stage="final",
            ambiguities=fixture / "ambiguity_resolved.md",
            granularity_contract=fixture / "granularity_contract.md",
            hard_constraints=fixture / "hard_constraints.md",
            model_plan=fixture / "model_plan_conflict_final.md",
            model_assumptions=fixture / "model_assumptions_empty.md",
            interpretation_decisions=fixture / "interpretation_decisions_empty.md",
        )

        self.assertFalse(result["pass"])
        self.assertIn(
            "sales_limit",
            result["contract_checks"]["model_plan"]["granularity_conflicts"],
        )
        self.assertTrue(any("P0 GRANULARITY_CONFLICT" in error for error in result["errors"]))

    def test_2023c_style_modeling_choices_and_mixed_roles_reach_paper_ready(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2023c-style-regression"

        result = validator.inspect(
            fixture / "interpretation_final.md",
            expected_subproblems=4,
            stage="final",
            ambiguities=fixture / "ambiguity_empty.md",
            granularity_contract=fixture / "granularity_contract.md",
            hard_constraints=fixture / "hard_constraints.md",
            interpretation_decisions=fixture / "interpretation_decisions.md",
            model_assumptions=fixture / "model_assumptions.md",
            model_plan=fixture / "model_plan_valid_final.md",
        )

        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(result["interpretation_status"], "PAPER_READY")
        self.assertEqual(result["contract_checks"]["ambiguities"]["count"], 0)
        self.assertEqual(result["contract_checks"]["interpretation_decision_count"], 2)
        self.assertEqual(
            result["contract_checks"]["model_plan"]["granularity_semantic_conflicts"], []
        )

    def test_modeling_choice_misclassified_as_ambiguity_is_rejected(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2023c-style-regression"
        contract = {
            "contract_type": "ambiguity_decisions",
            "schema_version": 1,
            "items": [
                {
                    "id": "profit_formula_choice",
                    "kind": "interpretation_ambiguity",
                    "ambiguity_scope": "model_implementation",
                    "question": "收益采用线性还是分段核算？",
                    "impact": ["feasible_region", "result"],
                    "evidence": [
                        {
                            "level": "testable_assumption",
                            "value": "piecewise_profit",
                            "source": "数学实现选择；题面未指定公式形式",
                        }
                    ],
                    "options": [],
                    "recommended": "piecewise_profit",
                    "decision": None,
                    "approved_by": None,
                    "status": "BLOCKING",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            ambiguity = self.write_contract(Path(directory), "ambiguity.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=4,
                stage="final",
                ambiguities=ambiguity,
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions.md",
                model_assumptions=fixture / "model_assumptions.md",
                model_plan=fixture / "model_plan_valid_final.md",
            )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any("P0 MISCLASSIFIED_MODELING_CHOICE" in error for error in result["errors"])
        )

    def test_downstream_impact_alone_does_not_classify_an_ambiguity(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2023c-style-regression"
        contract = {
            "contract_type": "ambiguity_decisions",
            "schema_version": 1,
            "items": [
                {
                    "id": "objective_meaning",
                    "kind": "interpretation_ambiguity",
                    "ambiguity_scope": "objective_definition",
                    "question": "题目中的收益是否包含处置成本？",
                    "impact": ["feasible_region", "result"],
                    "evidence": [
                        {
                            "level": "main_interpretation",
                            "value": "net_profit_with_disposal",
                            "source": "题面收益描述未明确处置成本归属",
                        },
                        {
                            "level": "alternative_interpretation",
                            "value": "net_profit_without_disposal",
                            "source": "附件另列处置费用但未说明是否计入目标",
                        },
                    ],
                    "options": [],
                    "recommended": "net_profit_with_disposal",
                    "decision": None,
                    "approved_by": None,
                    "freeze_targets": [],
                    "status": "BLOCKING",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            ambiguity = self.write_contract(Path(directory), "ambiguity.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=4,
                stage="draft",
                ambiguities=ambiguity,
            )

        self.assertTrue(result["pass"], result["errors"])
        self.assertFalse(
            any("MISCLASSIFIED_MODELING_CHOICE" in error for error in result["errors"])
        )
        self.assertEqual(result["contract_checks"]["ambiguities"]["blocking"], ["objective_meaning"])

    def test_granularity_semantic_role_must_match_model_plan(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2023c-style-regression"
        plan = validator.extract_contract(fixture / "model_plan_valid_final.md", "model_plan")
        plan = copy.deepcopy(plan)
        plan["items"][0]["semantic_role"] = "decision"
        with tempfile.TemporaryDirectory() as directory:
            plan_path = self.write_contract(Path(directory), "plan_final.md", plan)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=4,
                stage="final",
                ambiguities=fixture / "ambiguity_empty.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions.md",
                model_assumptions=fixture / "model_assumptions.md",
                model_plan=plan_path,
            )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any("P0 GRANULARITY_SEMANTIC_CONFLICT" in error for error in result["errors"])
        )

    def test_interpretation_decision_must_propagate_to_model_plan(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2023c-style-regression"
        plan = validator.extract_contract(fixture / "model_plan_valid_final.md", "model_plan")
        plan = copy.deepcopy(plan)
        plan["implemented_interpretation_decisions"]["profit_basis"]["metric"] = "gross_profit"
        with tempfile.TemporaryDirectory() as directory:
            plan_path = self.write_contract(Path(directory), "plan_final.md", plan)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=4,
                stage="final",
                ambiguities=fixture / "ambiguity_empty.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=fixture / "interpretation_decisions.md",
                model_assumptions=fixture / "model_assumptions.md",
                model_plan=plan_path,
            )

        self.assertFalse(result["pass"])
        self.assertIn(
            "profit_basis",
            result["contract_checks"]["model_plan"]["conflicting_interpretation_decisions"],
        )
        self.assertTrue(any("P0 DECISION_NOT_PROPAGATED" in error for error in result["errors"]))

    def test_resolved_ambiguity_can_propagate_through_decision_contract_to_plan(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2023c-style-regression"
        decisions = validator.extract_contract(
            fixture / "interpretation_decisions.md", "interpretation_decisions"
        )
        decisions = copy.deepcopy(decisions)
        decisions["items"][0]["status"] = "RESOLVED_BY_EVIDENCE"
        decision_value = decisions["items"][0]["value"]
        ambiguity = {
            "contract_type": "ambiguity_decisions",
            "schema_version": 1,
            "items": [
                {
                    "id": "profit_basis_review",
                    "kind": "interpretation_ambiguity",
                    "ambiguity_scope": "objective_definition",
                    "question": "题面收益目标采用什么标准化含义？",
                    "impact": ["objective_definition"],
                    "evidence": [
                        {
                            "level": "necessary_deduction",
                            "value": decision_value,
                            "source": "题面收入、成本与损耗字段共同确定净收益构成",
                        }
                    ],
                    "options": [],
                    "recommended": decision_value,
                    "decision": decision_value,
                    "approved_by": None,
                    "freeze_targets": [
                        {
                            "contract": "interpretation_decisions",
                            "id": "profit_basis",
                            "field": "value",
                        }
                    ],
                    "status": "RESOLVED_BY_EVIDENCE",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ambiguity_path = self.write_contract(root, "ambiguity.md", ambiguity)
            decisions_path = self.write_contract(root, "decisions.md", decisions)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=4,
                stage="final",
                ambiguities=ambiguity_path,
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                interpretation_decisions=decisions_path,
                model_assumptions=fixture / "model_assumptions.md",
                model_plan=fixture / "model_plan_valid_final.md",
            )

        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(
            result["contract_checks"]["ambiguities"]["decision_not_propagated"], []
        )

    def test_genuine_unresolved_interpretation_ambiguity_blocks_final(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        contract = {
            "contract_type": "ambiguity_decisions",
            "schema_version": 1,
            "items": [
                {
                    "id": "reporting_period",
                    "kind": "interpretation_ambiguity",
                    "ambiguity_scope": "delivery_requirement",
                    "question": "按月还是按季度交付？",
                    "impact": ["data_granularity", "delivery_requirement"],
                    "evidence": [
                        {
                            "level": "attachment_explicit",
                            "value": ["entity", "month"],
                            "source": "附件 A 表头：月份",
                        },
                        {
                            "level": "attachment_explicit",
                            "value": ["entity", "quarter"],
                            "source": "附件 B 模板：季度",
                        },
                    ],
                    "options": [],
                    "recommended": ["entity", "month"],
                    "decision": None,
                    "approved_by": None,
                    "status": "BLOCKING",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            ambiguity_path = self.write_contract(Path(directory), "ambiguity.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=ambiguity_path,
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertFalse(result["pass"])
        self.assertIn("reporting_period", result["contract_checks"]["ambiguities"]["blocking"])
        self.assertTrue(any("P0 FREEZE_GATE_BLOCKED" in error for error in result["errors"]))

    def test_conflicting_problem_and_official_attachment_cannot_be_user_selected(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        contract = {
            "contract_type": "ambiguity_decisions",
            "schema_version": 1,
            "items": [
                {
                    "id": "sales_limit_period",
                    "kind": "interpretation_ambiguity",
                    "ambiguity_scope": "data_granularity",
                    "question": "两个附件口径冲突时采用哪一种？",
                    "impact": ["data_granularity", "hard_constraint"],
                    "evidence": [
                        {
                            "level": "problem_explicit",
                            "value": ["crop", "year", "season"],
                            "source": "题面：按季次",
                        },
                        {
                            "level": "attachment_explicit",
                            "value": ["crop", "year"],
                            "source": "附件 B：按年度",
                        },
                    ],
                    "options": [],
                    "recommended": ["crop", "year", "season"],
                    "decision": ["crop", "year", "season"],
                    "approved_by": "user",
                    "freeze_targets": [
                        {
                            "contract": "granularity_contract",
                            "id": "sales_limit",
                            "field": "dimensions",
                        }
                    ],
                    "status": "APPROVED_BY_USER",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            ambiguity_path = self.write_contract(Path(directory), "ambiguity.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=ambiguity_path,
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertFalse(result["pass"])
        self.assertIn(
            "sales_limit_period",
            result["contract_checks"]["ambiguities"]["official_source_conflicts"],
        )
        self.assertTrue(any("P0 OFFICIAL_SOURCE_CONFLICT" in e for e in result["errors"]))

    def test_compatible_official_sources_and_higher_correction_resolve_by_evidence(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        base = validator.extract_contract(fixture / "ambiguity_resolved.md", "ambiguity_decisions")
        compatible = copy.deepcopy(base)
        compatible["items"][0]["evidence"].append(
            {
                "level": "attachment_explicit",
                "value": ["crop", "year", "season"],
                "source": "official attachment field: season",
            }
        )
        corrected = copy.deepcopy(base)
        corrected["items"][0]["evidence"] = [
            {
                "level": "problem_explicit",
                "value": ["crop", "year"],
                "source": "original problem wording: annual",
            },
            {
                "level": "attachment_explicit",
                "value": ["crop", "year", "season"],
                "source": "official attachment field: season",
            },
            {
                "level": "official_correction",
                "value": ["crop", "year", "season"],
                "source": "official correction: calculate for every season",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, contract in (("compatible", compatible), ("corrected", corrected)):
                with self.subTest(name=name):
                    ambiguity_path = self.write_contract(root, f"{name}.md", contract)
                    result = validator.inspect(
                        fixture / "interpretation_final.md",
                        expected_subproblems=3,
                        stage="final",
                        ambiguities=ambiguity_path,
                        granularity_contract=fixture / "granularity_contract.md",
                        hard_constraints=fixture / "hard_constraints.md",
                        model_plan=fixture / "model_plan_valid_final.md",
                        model_assumptions=fixture / "model_assumptions_empty.md",
                        interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                    )
                    self.assertTrue(result["pass"], result["errors"])
                    self.assertEqual(
                        result["contract_checks"]["ambiguities"]["official_source_conflicts"],
                        [],
                    )

    def test_resolved_decision_must_propagate_to_freeze_target(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        base = validator.extract_contract(fixture / "ambiguity_resolved.md", "ambiguity_decisions")
        missing_target = copy.deepcopy(base)
        del missing_target["items"][0]["freeze_targets"]
        mismatched = copy.deepcopy(base)
        mismatched["items"][0]["evidence"][0]["value"] = ["crop", "year"]
        mismatched["items"][0]["recommended"] = ["crop", "year"]
        mismatched["items"][0]["decision"] = ["crop", "year"]
        self_target = copy.deepcopy(base)
        self_target["items"][0]["freeze_targets"] = [
            {
                "contract": "ambiguity_decisions",
                "id": "sales_limit_period",
                "field": "decision",
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, contract in (
                ("missing", missing_target),
                ("mismatched", mismatched),
                ("self_target", self_target),
            ):
                with self.subTest(name=name):
                    ambiguity_path = self.write_contract(root, f"{name}.md", contract)
                    result = validator.inspect(
                        fixture / "interpretation_final.md",
                        expected_subproblems=3,
                        stage="final",
                        ambiguities=ambiguity_path,
                        granularity_contract=fixture / "granularity_contract.md",
                        hard_constraints=fixture / "hard_constraints.md",
                        model_plan=fixture / "model_plan_valid_final.md",
                        model_assumptions=fixture / "model_assumptions_empty.md",
                        interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                    )
                    self.assertFalse(result["pass"])
                    self.assertIn(
                        "sales_limit_period",
                        result["contract_checks"]["ambiguities"]["decision_not_propagated"],
                    )
                    self.assertTrue(
                        any("P0 DECISION_NOT_PROPAGATED" in e for e in result["errors"])
                    )

    def test_verified_cannot_close_a_reviewed_candidate_ambiguity(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        contract = validator.extract_contract(
            fixture / "ambiguity_resolved.md", "ambiguity_decisions"
        )
        contract = copy.deepcopy(contract)
        contract["items"][0]["status"] = "VERIFIED"
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_contract(Path(directory), "verified.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=path,
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any("VERIFIED is reserved for facts" in error for error in result["errors"])
        )

    def test_p1_non_blocking_finding_does_not_share_p0_gate(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        granularity = validator.extract_contract(
            fixture / "granularity_contract.md", "granularity_contract"
        )
        granularity = copy.deepcopy(granularity)
        granularity["items"][0]["mutable"] = "YES"
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_contract(Path(directory), "granularity.md", granularity)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=path,
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertTrue(result["pass"], result["errors"])
        finding = next(
            item for item in result["findings"] if item["code"] == "EXPLICIT_GRANULARITY_MUTABLE"
        )
        self.assertEqual(finding["severity"], "P1")
        self.assertEqual(finding["gate"], "NON_BLOCKING")

    def test_model_assumptions_with_sensitivity_do_not_block_final(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        contract = {
            "contract_type": "model_assumptions",
            "schema_version": 1,
            "items": [
                {
                    "id": "cvar_alpha",
                    "parameter": "CVaR confidence level",
                    "source": "model setting; not specified by the problem",
                    "main_value": 0.95,
                    "alternative_values": [0.9, 0.99],
                    "sensitivity": "compare feasibility, objective value, and key decisions",
                    "status": "MODEL_ASSUMPTION",
                },
                {
                    "id": "elasticity_strength",
                    "parameter": "elasticity strength",
                    "source": "estimated/model setting",
                    "main_value": 0.2,
                    "alternative_values": [0.1, 0.3],
                    "sensitivity": "re-estimate Q3 under both alternatives",
                    "status": "MODEL_ASSUMPTION",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            assumptions = self.write_contract(Path(directory), "assumptions.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=assumptions,
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(result["contract_checks"]["model_assumptions"]["count"], 2)
        self.assertFalse(result["contract_checks"]["model_assumptions"]["blocking"])

    def test_structural_assumption_can_use_diagnostic_without_numeric_alternatives(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        contract = {
            "contract_type": "model_assumptions",
            "schema_version": 1,
            "items": [
                {
                    "id": "independent_errors",
                    "statement": "errors are independent across entities",
                    "source": "model structure assumption; not specified by the problem",
                    "diagnostic": "inspect grouped residual correlations",
                    "failure_condition": "stable within-group residual correlation is detected",
                    "fallback_model": "use clustered errors or a correlated-error model",
                    "status": "MODEL_ASSUMPTION",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            assumptions = self.write_contract(Path(directory), "assumptions.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=assumptions,
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertTrue(result["pass"], result["errors"])

    def test_model_assumption_without_challenge_path_blocks_final(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        contract = {
            "contract_type": "model_assumptions",
            "schema_version": 1,
            "items": [
                {
                    "id": "stationarity",
                    "statement": "the process is stationary",
                    "source": "model structure assumption; not specified by the problem",
                    "status": "MODEL_ASSUMPTION",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            assumptions = self.write_contract(Path(directory), "assumptions.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=assumptions,
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any("at least one validation/challenge path is required" in e for e in result["errors"])
        )

    def test_model_assumption_cannot_be_stored_as_ambiguity(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        contract = {
            "contract_type": "ambiguity_decisions",
            "schema_version": 1,
            "items": [
                {
                    "id": "cvar_alpha",
                    "kind": "model_assumption",
                    "question": "CVaR alpha",
                    "impact": ["result"],
                    "evidence": [
                        {
                            "level": "testable_assumption",
                            "value": 0.95,
                            "source": "model setting",
                        }
                    ],
                    "decision": 0.95,
                    "status": "MODEL_ASSUMPTION",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            ambiguity_path = self.write_contract(Path(directory), "ambiguity.md", contract)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=ambiguity_path,
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertFalse(result["pass"])
        self.assertTrue(any("MODEL_ASSUMPTION is not an ambiguity status" in e for e in result["errors"]))

    def test_missing_frozen_hard_constraint_triggers_p0(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        hard = validator.extract_contract(fixture / "hard_constraints.md", "hard_constraints")
        plan = validator.extract_contract(fixture / "model_plan_valid_final.md", "model_plan")
        hard = copy.deepcopy(hard)
        plan = copy.deepcopy(plan)
        hard["items"] = [
            {
                "id": f"H-0{number}",
                "statement": f"hard constraint {number}",
                "type": "HARD",
                "evidence_level": "problem_explicit",
                "evidence_ref": f"problem statement line {number}",
                "granularity_ids": ["sales_limit"],
                "status": "VERIFIED",
            }
            for number in range(1, 4)
        ]
        plan["implemented_hard_constraints"] = ["H-01", "H-02"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hard_path = self.write_contract(root, "hard.md", hard)
            plan_path = self.write_contract(root, "plan_final.md", plan)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=hard_path,
                model_plan=plan_path,
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertFalse(result["pass"])
        self.assertTrue(
            any("P0 HARD_CONSTRAINT_NOT_IMPLEMENTED: H-03" in error for error in result["errors"])
        )

    def test_contract_schema_errors_block_freeze(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        ambiguity = validator.extract_contract(
            fixture / "ambiguity_resolved.md", "ambiguity_decisions"
        )
        granularity = validator.extract_contract(
            fixture / "granularity_contract.md", "granularity_contract"
        )

        cases = []

        duplicate_id = copy.deepcopy(granularity)
        duplicate_id["items"].append(copy.deepcopy(duplicate_id["items"][0]))
        cases.append(("duplicate_id", "granularity", duplicate_id))

        empty_dimensions = copy.deepcopy(granularity)
        empty_dimensions["items"][0]["dimensions"] = []
        cases.append(("empty_dimensions", "granularity", empty_dimensions))

        missing_source = copy.deepcopy(ambiguity)
        del missing_source["items"][0]["evidence"][0]["source"]
        cases.append(("missing_source", "ambiguity", missing_source))

        invalid_mutable = copy.deepcopy(granularity)
        invalid_mutable["items"][0]["mutable"] = "MAYBE"
        cases.append(("invalid_mutable", "granularity", invalid_mutable))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, target, contract in cases:
                with self.subTest(name=name):
                    bad_path = self.write_contract(root, f"{name}.md", contract)
                    kwargs = {
                        "ambiguities": fixture / "ambiguity_resolved.md",
                        "granularity_contract": fixture / "granularity_contract.md",
                    }
                    kwargs["ambiguities" if target == "ambiguity" else "granularity_contract"] = bad_path
                    result = validator.inspect(
                        fixture / "interpretation_final.md",
                        expected_subproblems=3,
                        stage="final",
                        hard_constraints=fixture / "hard_constraints.md",
                        model_plan=fixture / "model_plan_valid_final.md",
                        model_assumptions=fixture / "model_assumptions_empty.md",
                        interpretation_decisions=fixture / "interpretation_decisions_empty.md",
                        **kwargs,
                    )
                    self.assertFalse(result["pass"])
                    self.assertTrue(
                        any("P0 CONTRACT_SCHEMA_ERROR" in error for error in result["errors"]),
                        result["errors"],
                    )

    def test_every_contract_requires_schema_version(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        paths = {
            "ambiguities": (fixture / "ambiguity_resolved.md", "ambiguity_decisions"),
            "granularity_contract": (
                fixture / "granularity_contract.md",
                "granularity_contract",
            ),
            "hard_constraints": (fixture / "hard_constraints.md", "hard_constraints"),
            "interpretation_decisions": (
                fixture / "interpretation_decisions_empty.md",
                "interpretation_decisions",
            ),
            "model_assumptions": (
                fixture / "model_assumptions_empty.md",
                "model_assumptions",
            ),
            "model_plan": (fixture / "model_plan_valid_final.md", "model_plan"),
        }
        base_kwargs = {key: value[0] for key, value in paths.items()}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for key, (path, contract_type) in paths.items():
                with self.subTest(contract=key):
                    contract = copy.deepcopy(validator.extract_contract(path, contract_type))
                    del contract["schema_version"]
                    bad_path = self.write_contract(root, f"{key}.md", contract)
                    kwargs = dict(base_kwargs)
                    kwargs[key] = bad_path
                    result = validator.inspect(
                        fixture / "interpretation_final.md",
                        expected_subproblems=3,
                        stage="final",
                        **kwargs,
                    )
                    self.assertFalse(result["pass"])
                    self.assertTrue(
                        any(
                            "P0 CONTRACT_SCHEMA_ERROR" in error
                            and "schema_version" in error
                            for error in result["errors"]
                        ),
                        result["errors"],
                    )

    def test_semantic_contract_fields_are_required(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        granularity = validator.extract_contract(
            fixture / "granularity_contract.md", "granularity_contract"
        )
        hard = validator.extract_contract(fixture / "hard_constraints.md", "hard_constraints")
        plan = validator.extract_contract(fixture / "model_plan_valid_final.md", "model_plan")

        cases = []
        missing_object = copy.deepcopy(granularity)
        del missing_object["items"][0]["object"]
        cases.append(("missing_object", "granularity_contract", missing_object))

        missing_granularity_role = copy.deepcopy(granularity)
        del missing_granularity_role["items"][0]["semantic_role"]
        cases.append(("missing_granularity_role", "granularity_contract", missing_granularity_role))

        missing_statement = copy.deepcopy(hard)
        del missing_statement["items"][0]["statement"]
        cases.append(("missing_statement", "hard_constraints", missing_statement))

        missing_used_by = copy.deepcopy(plan)
        del missing_used_by["items"][0]["used_by"]
        cases.append(("missing_used_by", "model_plan", missing_used_by))

        missing_plan_role = copy.deepcopy(plan)
        del missing_plan_role["items"][0]["semantic_role"]
        cases.append(("missing_plan_role", "model_plan", missing_plan_role))

        missing_actual_dimensions = copy.deepcopy(plan)
        missing_actual_dimensions["items"][0]["dimensions"] = []
        cases.append(("missing_dimensions", "model_plan", missing_actual_dimensions))

        missing_symbol_reason = copy.deepcopy(plan)
        del missing_symbol_reason["items"][0]["symbol"]
        cases.append(("missing_symbol_reason", "model_plan", missing_symbol_reason))

        missing_decision_map = copy.deepcopy(plan)
        del missing_decision_map["implemented_interpretation_decisions"]
        cases.append(("missing_decision_map", "model_plan", missing_decision_map))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, target, contract in cases:
                with self.subTest(name=name):
                    path = self.write_contract(root, f"{name}.md", contract)
                    kwargs = {
                        "ambiguities": fixture / "ambiguity_resolved.md",
                        "granularity_contract": fixture / "granularity_contract.md",
                        "hard_constraints": fixture / "hard_constraints.md",
                        "interpretation_decisions": fixture / "interpretation_decisions_empty.md",
                        "model_plan": fixture / "model_plan_valid_final.md",
                        "model_assumptions": fixture / "model_assumptions_empty.md",
                    }
                    kwargs[target] = path
                    result = validator.inspect(
                        fixture / "interpretation_final.md",
                        expected_subproblems=3,
                        stage="final",
                        **kwargs,
                    )
                    self.assertFalse(result["pass"])
                    self.assertTrue(
                        any("P0 CONTRACT_SCHEMA_ERROR" in error for error in result["errors"]),
                        result["errors"],
                    )

    def test_model_plan_null_reason_is_valid_when_symbol_does_not_apply(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        plan = validator.extract_contract(fixture / "model_plan_valid_final.md", "model_plan")
        plan = copy.deepcopy(plan)
        del plan["items"][0]["symbol"]
        plan["items"][0]["null_reason"] = "implemented as an indexed decision rule"
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_contract(Path(directory), "plan_final.md", plan)
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=fixture / "ambiguity_resolved.md",
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=path,
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertTrue(result["pass"], result["errors"])

    def test_paper_ready_manifest_hashes_the_two_finals_and_five_contracts(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        paths = {
            "report": fixture / "interpretation_final.md",
            "ambiguities": fixture / "ambiguity_resolved.md",
            "granularity_contract": fixture / "granularity_contract.md",
            "hard_constraints": fixture / "hard_constraints.md",
            "interpretation_decisions": fixture / "interpretation_decisions_empty.md",
            "model_plan": fixture / "model_plan_valid_final.md",
            "model_assumptions": fixture / "model_assumptions_empty.md",
        }
        result = validator.inspect(
            paths["report"], expected_subproblems=3, stage="final", **{
                key: value for key, value in paths.items() if key != "report"
            }
        )

        manifest = validator.build_paper_ready_manifest(
            result,
            project_root=fixture,
            standard=SKILL_ROOT.parent / "_shared" / "cumcm" / "C题规范.md",
            **paths,
        )

        self.assertEqual(manifest["status"], "PAPER_READY")
        self.assertEqual(len(manifest["files"]), 7)
        self.assertEqual(
            {item["role"] for item in manifest["files"]},
            {
                "interpretation_final",
                "model_plan_final",
                "ambiguity_decisions",
                "granularity_contract",
                "hard_constraints",
                "interpretation_decisions",
                "model_assumptions",
            },
        )
        self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["files"]))

    def test_paper_ready_manifest_refuses_pending_result(self):
        with self.assertRaisesRegex(ValueError, "PAPER_READY"):
            validator.build_paper_ready_manifest(
                {"pass": False, "interpretation_status": "INTERPRETATION_PENDING"},
                project_root=SKILL_ROOT,
                standard=SKILL_ROOT.parent / "_shared" / "cumcm" / "C题规范.md",
                report=SKILL_ROOT / "SKILL.md",
                model_plan=None,
                ambiguities=None,
                granularity_contract=None,
                hard_constraints=None,
                interpretation_decisions=None,
                model_assumptions=None,
            )

    def test_invalid_contract_json_blocks_freeze(self):
        fixture = SKILL_ROOT / "tests" / "fixtures" / "2024c-regression"
        with tempfile.TemporaryDirectory() as directory:
            bad_path = Path(directory) / "bad.md"
            bad_path.write_text(
                '```contract-json\n{"contract_type": "ambiguity_decisions", "items": [}\n```\n',
                encoding="utf-8",
            )
            result = validator.inspect(
                fixture / "interpretation_final.md",
                expected_subproblems=3,
                stage="final",
                ambiguities=bad_path,
                granularity_contract=fixture / "granularity_contract.md",
                hard_constraints=fixture / "hard_constraints.md",
                model_plan=fixture / "model_plan_valid_final.md",
                model_assumptions=fixture / "model_assumptions_empty.md",
                interpretation_decisions=fixture / "interpretation_decisions_empty.md",
            )

        self.assertFalse(result["pass"])
        self.assertTrue(any("P0 CONTRACT_SCHEMA_ERROR" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()

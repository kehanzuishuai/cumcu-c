# 自动审计脚本与清单

## 目录

1. 基本用法
2. 审计清单格式
3. 结果复现与正文数字
4. PDF 视觉准备
5. LaTeX 编译质量
6. 自动/人工边界
7. 回归测试

## 1. 基本用法

`scripts/audit_submission.py` 默认只读项目文件；只有指定输出报告、PDF 渲染或获准运行代码时才产生相应文件。

```bash
python3 scripts/audit_submission.py PROJECT_ROOT \
  --mode full \
  --paper final_paper.pdf \
  --manifest audit_manifest.json \
  --compile-latex \
  --render-pdf \
  --visual-dir .final-audit-visual \
  --json-out final_audit_findings.json \
  --md-out final_audit_script_report.md
```

只审论文内部时使用 `paper-only`；只做最终 PDF 视觉审查时使用 `visual-only`；按上一版报告定点复核时使用 `recheck`。PAPER_ONLY 不因代码、结果文件或支撑材料未提供而视为材料不全。可重复添加项目特有匿名禁词：

```bash
--forbidden-term "某某大学" --forbidden-term "张三"
```

`paper-only` 的脚本报告会附带 16 项 Coverage 占位表和独立 Deferred 表。总状态使用 `PAPER_AUDIT_PASS / PAPER_AUDIT_COMPLETE_WITH_WARNINGS / PAPER_AUDIT_COMPLETE_WITH_BLOCKERS`；代码、结果、支撑材料和 AI 详情默认 `DEFERRED_TO_FULL / OUT_OF_SCOPE`，不得进入 FAIL。脚本不能完成语义审查，因此只要 Coverage 仍有 `UNVERIFIED`，自动报告至少保留 `PAPER_AUDIT_COMPLETE_WITH_WARNINGS`；人工逐项核验后才能升为 `PAPER_AUDIT_PASS`。

## 2. 审计清单格式

FULL/RECHECK 在 `paper_final` 根目录读取最终冻结 Skill 生成的 `audit_manifest.json`；不要手工把半成品清单改成 `frozen: true`。下面展示审核字段的完整能力，只保留本项目真实可核验的字段，不要编造检查值。

```json
{
  "freeze_schema_version": 1,
  "frozen": true,
  "blockers": [],
  "standard": {"version": "2026.09.01", "sha256": "..."},
  "paper_ready_manifest": "handoff/paper_ready_manifest.json",
  "figure_manifest": "figure_manifest.json",
  "upstream_manifests": {
    "paper_ready": {"path": "handoff/paper_ready_manifest.json", "sha256": "..."},
    "figures": {"path": "figure_manifest.json", "sha256": "..."}
  },
  "paper": "final_paper.pdf",
  "source": "paper.tex",
  "problem_files": ["题目/C题.pdf", "题目/附件1.xlsx"],
  "problem_count": 4,
  "ai_used": true,
  "has_support_materials": true,
  "uses_programs": true,
  "support_dir": "support",
  "support_archive": "support.zip",
  "forbidden_terms": ["某某大学", "真实姓名", "报名号", "真实用户名"],
  "terminology_groups": [
    {
      "canonical": "样本外评估",
      "variants": ["样本外评测", "样本外评价", "样本外评估"]
    }
  ],
  "identity_terms": {
    "names": ["队员甲", "队员乙"],
    "schools": ["某某大学"],
    "student_ids": ["2026000000"],
    "usernames": ["real_user"]
  },
  "latex": {
    "source": "paper.tex",
    "engine": "xelatex",
    "timeout_seconds": 180,
    "args": []
  },
  "required_files": [
    {
      "path": "results/result1.xlsx",
      "sheets": ["Sheet1"],
      "rows": {"Sheet1": 20},
      "columns": {"Sheet1": 8},
      "sha256": "可选的64位SHA-256"
    },
    {
      "path": "results/result2.csv",
      "rows": 31,
      "columns": 8
    }
  ],
  "frozen_files": [
    {"path": "final_paper.pdf", "sha256": "...", "categories": ["paper"]}
  ],
  "reproducibility": {
    "entrypoint": ["python3", "run_all.py"],
    "working_directory": ".",
    "timeout_seconds": 300,
    "artifact_checks": [
      {
        "id": "q1-table",
        "generated": "recomputed/q1_result.csv",
        "frozen": "results/q1_result.csv",
        "method": "table",
        "key_columns": ["对象ID"],
        "ignore_columns": ["生成时间"],
        "atol": 1e-8,
        "rtol": 1e-6
      },
      {
        "id": "q2-figure",
        "generated": "recomputed/q2_core_figure.pdf",
        "frozen": "figures/q2_core_figure.pdf",
        "method": "hash"
      }
    ],
    "paper_claims": [
      {
        "id": "abstract-q1-score",
        "paper_pattern": "问题一[\\s\\S]{0,180}?准确率[^0-9]*([0-9.]+)%",
        "paper_scale": 0.01,
        "result": {
          "path": "results/metrics.json",
          "json_path": "q1.accuracy"
        },
        "atol": 0.0001,
        "rtol": 0.001
      }
    ]
  }
}
```

关键字段：

- `freeze_schema_version`、`frozen`、`blockers`：Final Audit 冻结门禁。
- `standard`、`upstream_manifests`、`frozen_files`：唯一规范、审题/绘图来源及全包 SHA-256 证据；FULL/RECHECK 必须匹配。
- 上例的 `frozen_files` 只展示单条形状；实际文件由最终冻结脚本完整枚举，必须覆盖两个上游 manifest 及其引用的 final、合同、Brief、数据、脚本和图形输出。
- `paper`、`source`、`problem_files`：最终论文、主源文件和原题证据。
- `has_support_materials`：必须明确 `true/false`。为 `false` 时不要求 support 文件夹，但附录应写“本论文没有支撑材料”。
- `uses_programs=false`：附录还应写“本论文没有用到程序”。
- `identity_terms`/`forbidden_terms`：队员姓名、学校、学号、用户名等确切身份词；命中才高优先级报警。
- `terminology_groups`：项目已知的同义术语组；脚本只在两种以上写法共同出现时列候选，是否确为同一概念仍由人工确认。
- `latex`：临时编译所用主文件、引擎和安全参数数组。
- `required_files`：精确文件、工作表、行列和可选冻结 hash。
- `reproducibility`：入口、工作目录、重算文件对比和正文关键数字。

若确实没有支撑材料：

```json
{
  "has_support_materials": false,
  "uses_programs": false
}
```

这不会因为缺少 `support/` 而报错；脚本改为核对 manifest 与附录规定说明是否一致。若 `ai_used=true`，则不能同时声明无支撑材料，因为需要提交 `AI 工具使用详情.pdf`。

## 3. 结果复现与正文数字

只有用户明确授权运行最终代码时添加 `--run-entrypoint`。入口必须是无 shell 的字符串数组，工作目录必须在项目根内。脚本不安装依赖、不联网、不使用隐藏凭据。

```bash
python3 scripts/audit_submission.py PROJECT_ROOT \
  --manifest audit_manifest.json \
  --run-entrypoint \
  --compile-latex \
  --render-pdf
```

不能把退出码 0 当成复现通过。至少配置：

- `artifact_checks.method=hash`：适合要求字节完全相同的冻结文件、图或模型产物。
- `artifact_checks.method=table`：适合 CSV/XLSX；比较行列、键和单元格，数值使用 `atol + rtol` 容差。
- `key_columns`：按业务主键对齐，避免仅因行顺序不同误报。
- `ignore_columns`：仅忽略时间戳等与结论无关、已明确批准的列。
- `paper_claims`：用唯一正则定位正文/摘要数字，再与 JSON、CSV 或 XLSX 单元格对照。

当 `generated` 与 `frozen` 是同一路径时，脚本在运行前临时快照冻结文件，运行后再比较，避免覆盖后“自己与自己相等”。随机算法不得用 hash 强求字节一致；应使用表格容差、分布摘要、固定种子或项目专用验证器。

复杂 Excel 业务约束（面积上限、轮作、库存守恒等）仍需项目专用验证脚本；通用脚本不会猜测题意。

## 4. PDF 视觉准备

`--render-pdf` 调用 `scripts/render_pdf_for_audit.py`，输出：

- `page-0001.png` 等所有全页图片；
- `contact-sheet-all.png` 全文总览；
- 每 12 页一张的分组 contact sheet；
- `visual-manifest.json` 页面指标和候选页；
- `visual-review.md` 人工检查清单。

空白率/内容占比只能定位候选页，不能自动断言机械分页、标题孤行、跨页表、图表碰撞或美观失败。Visual Audit 必须实际查看最终 PDF 的所有页面图，并放大候选页、摘要页和图表密集页。

## 5. LaTeX 编译质量

`--compile-latex` 在临时输出目录编译，不把 `.aux/.log` 写入提交工程。支持 `xelatex/pdflatex/lualatex`，优先使用 `latexmk`。检查：

- 最终主文件能否生成 PDF；
- undefined reference / citation；
- 编译日志确认的 missing file/figure；
- 重复 label；
- Overfull hbox（只作视觉 WARN，需看最终 PDF 是否真实溢出）。

静态 `includegraphics` 路径扫描找不到文件时先记 `UNVERIFIED`，因为图片可能由 `graphicspath`、宏或构建步骤提供；只有编译日志确认缺失才升级。

LaTeX 源码审计还会定位：

- `\parindent` 的显式设置、正文 `\noindent`、段首人工空格和局部缩进冲突候选；源码证据不能替代最终 PDF 视觉确认。
- 标准 citation command（含 `\cite`、`\parencite`、`\supercite` 等）及 citation key；普通 `[4,5]` 不再被当作引用证据。
- 带文献语义线索的手工 `（2）`/`[2]` 候选；确认前保持 HEURISTIC，确认后按 P1 处理。
- 若 PyMuPDF 可用，枚举最终 PDF 中指向参考文献页的内部链接，并把“可见数字标签与源码中无 citation command 的普通文本重合”列为错误链接候选。链接注释缺失或目标不可解析时标 `UNVERIFIED`。

## 6. 自动/人工边界

| 类型 | 自动结论 | 例子 |
|---|---|---|
| 确定性事实 | 可判 P0/P1 | 文件缺失、格式/大小、明确身份词、编译失败、hash/行列/容差冲突 |
| 启发式线索 | P2/P3 `WARN` | 裸接图表、重复模板句、空白候选、Overfull hbox |
| 工具无法确认 | `UNVERIFIED` | PDF 无文本层、自定义摘要命令、字体别名、普通邮箱/GitHub、元数据作者字段 |
| 学术/视觉判断 | 人工审查 | 模型合理性、阈值/权重依据、AI 感、图表冗余、美观和遮挡 |

模式边界先于上表的严重度：PAPER_ONLY 的占位图写 `DEFERRED_TO_DRAWING`；VISUAL_ONLY/FULL 在最终 PDF 中确认占位时判 P1；代码、result.xlsx、支撑包、AI 详情和构建垃圾在 PAPER_ONLY 写 `DEFERRED_TO_FULL / OUT_OF_SCOPE`。只有 FULL 仍缺失或不一致时才按 S0/S1 升级。

脚本支持多种摘要、关键词和标题写法，不把 `abstract`、`\keywords{}` 或内置 `\section` 当成唯一合法形式。PDF 文本提取失败时不得判摘要缺失。自动报告的 PASS 只对应具体事实，不能扩展为整个模块通过或可交卷。

连接与过渡、模型百科式表达、“问题分析—最终模型”边界必须阅读上下文，因此不得由词频或正则直接判 FAIL。长句、多层连接和抽象名词堆叠可由脚本生成 P3 `HEURISTIC` 候选，但只有人工确认其确实妨碍理解后才进入正式语义问题清单。

脚本会用少量默认示例组和 manifest 的 `terminology_groups` 定位术语变体共现，并定位“相关方法见文献”“具体算法参见文献”“详见文献”等展示式引用表达。这两类自动命中为 P2 `HEURISTIC` 候选：前者必须确认变体是否真的同义，后者必须确认 citation 实际支持的对象和位置；均不得直接判 FAIL 或批量替换。直接写成“Gaussian Copula\cite{key} + 本题作用”的正常表达不应报警。

引用语义正确性也不能由题名相似度直接判 PASS。脚本只核对命令、key、条目、编译日志和可解析的 PDF 链接；“文献原文是否支持当前句子”必须进入引用完整性矩阵。只有题名/摘要而无全文时写 `UNVERIFIED`。

脚本还会定位“题目给出、附件提供、根据题设、由题目可知”等来源性表述，但只输出 P2 `HEURISTIC` 候选和来源矩阵待核项。脚本无法凭句子判断 `R_0`、边数、分布或阈值是否真来自题设；只有人工对照原题/附件确认冒充来源后才升为 P1。

## 7. 回归测试

修改脚本后在 Skill 根目录运行：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

测试至少覆盖两类边界：

- **应检出**：明确身份禁词、含真实用户名的个人路径、结果超容差、重复 label、真实长句/多层连接候选；
- **应检出**：统一/冲突的 `\parindent`、异常 `\noindent`、人工空格缩进、手工文献编号候选，以及 PDF 普通区间误链参考文献候选；
- **不应误报**：自定义摘要/关键词、普通邮箱与参考文献 GitHub、`has_support_materials=false`、PDF 无文本层、LaTeX 注释/公式、容差内结果、普通未链接区间 `[4,5]`；
- **应检出但需确认**：默认/自定义术语组中的两种以上变体共现、展示式引用表达；只出现一种术语写法和“方法名 + citation”直接引用不应误报。
- **模式边界**：PAPER_ONLY 图表占位只进入 `DEFERRED_TO_DRAWING`；VISUAL_ONLY/FULL 最终 PDF 中的占位是 P1；缺少 AI 详情、结果文件和支撑包不产生 PAPER_ONLY P0/P1；构建垃圾只在 FULL/RECHECK 工程范围检查。
- **来源反查**：题设声明候选能被定位且不自动判 FAIL；已确认的本队设定冒充题设事实必须在模型选择证据链中判 P1。
- **状态升级**：PAPER_ONLY 无问题/有低风险问题/有论文内 P0-P1 分别返回三种 `PAPER_AUDIT_*` 状态，不再因有意延后的 FULL 项返回 `INCOMPLETE_AUDIT_SCOPE`。
- **覆盖不回退**：`paper-only` 脚本报告始终保留 16 个 Audit Coverage 行，状态只来自 `PASS / WARN / FAIL / UNVERIFIED`。

测试失败时先修复规则或样例，不得通过放宽所有严重度、删除断言或把确定性错误统一降为 `UNVERIFIED` 来“通过测试”。

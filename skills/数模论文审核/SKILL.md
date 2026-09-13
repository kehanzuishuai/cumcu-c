---
name: 数模论文审核
description: Audit a frozen CUMCM undergraduate C-problem submission package, or run a PAPER_ONLY internal paper review before drawing and delivery artifacts are complete. Use for 最终审查、Final Audit、Final QA、交卷检查、提交前检查、论文审计、复现审计、匿名审计、AI 合规审计，或分阶段检查 C 题 PDF/Word/LaTeX、代码、结果文件、图表和支撑材料。Do not use this skill to continue modeling, choose a new model, or rewrite the paper.
---

# 数学建模论文最终审查

## 审查目标

FULL 判断一份已经冻结的 CUMCM 本科组 C 题论文及其交付工程是否具备交卷条件；PAPER_ONLY 只判断论文内部当前可确认的问题。沿以下方向反向验收：

> 题目要求 → 最终文件/数值 → 论文图表 → 代码输出 → 数学模型 → 变量与约束 → 原题/附件证据

只发现问题、定位证据、判定严重度并给出修复建议。不要在审查过程中继续建模，不要暗中更换模型、阈值、假设或结论。自动脚本无法确定时标记 `UNVERIFIED` 或 P2/P3 `WARN`，不得把某一种 LaTeX 写法、字体别名或文本提取结果当成唯一真相。

## 规则权威

1. 始终先读 [authoritative-rules.md](references/authoritative-rules.md)。
2. 当届组委会和赛区正式文件为 S0，优先于本 Skill 的任何默认值。
3. 唯一共享 `../_shared/cumcm/C题规范.md` 为 S1；其他 Skill、往年优秀论文、教师经验和对方项目只能补充检查方法，不能覆盖 S0/S1。
4. 对无法从材料中核验的项目标记 `UNVERIFIED`，不得猜测为 PASS。

## 审查模式

- **FULL**：只接收最终成稿冻结阶段生成的 `paper_final` 包；题面、附件、最终论文、源文件、代码、结果文件齐全，支撑材料状态已明确（包括合规声明“无支撑材料”）。只有此模式可以给出 `READY*` 结论。
- **PAPER_ONLY**：只有 PDF、Word、LaTeX 或 Markdown，可用于正文审核阶段而不要求交付工程已经齐全。检查论文内部可确认的结构、公式、语言、图表叙事和版面，完成核心模块覆盖表；代码、结果文件、支撑包和 AI 详情文件列入 `Deferred to FULL`，不得因有意缩小范围而写 `INCOMPLETE_AUDIT_SCOPE`。
- **VISUAL_ONLY**：只做最终 PDF 逐页视觉验收，不评价模型与复现。
- **RECHECK**：只复核上一版报告的问题及其直接受影响依赖，不重新执行无关模块的完整审查；发现与本次修改直接相关的回归时一并记录。

若用户没有指定模式，根据材料完整度选择；不要为了进入 FULL 而假定缺失文件存在。

## 入口门禁

FULL/RECHECK 审查开始前确认：

- `audit_manifest.json` 由最终成稿冻结阶段生成，`frozen: true`、`blockers: []`；
- `paper_ready_manifest.json` 与 `figure_manifest.json` 状态、规范版本和 hash 均一致；
- `figure_manifest.json` 使用严格接口：普通图含正文上下文/数据字段快照与绘图脚本，流程图含可编辑 `.pptx` 源文件，流程图生成脚本仅在实际使用时出现；
- 每问主模型、最终代码入口、结果文件和关键图表已经确定；
- 最终论文已进入“只修错、不大换模型”状态；
- 不存在尚未完成的问题、未生成的强制结果文件或仍在改动的核心图。

FULL/RECHECK 必须从冻结目录读取 `audit_manifest.json`，逐项核对 `frozen_files` 和两个上游 manifest 的 SHA-256；不得用目录中的零散 final 文件替代冻结清单。门禁未通过时立即输出 `NOT_READY_FOR_FINAL_AUDIT`，列出 BLOCKER，不执行完整 Final QA。PAPER_ONLY 不执行该门禁，其内部审查范围保持不变。

## 必须读取的参考文件

- 所有审查：读 [severity-and-report.md](references/severity-and-report.md)。
- FULL/PAPER_ONLY：读 [audit-checklist.md](references/audit-checklist.md)。
- PAPER_ONLY：额外读 [paper-only-coverage.md](references/paper-only-coverage.md)，执行强制覆盖与引用完整性矩阵。
- FULL/PAPER_ONLY 的正文语言与模型叙事：读 [language-transition-audit.md](references/language-transition-audit.md)。
- 涉及具体模型验证：读 [model-validation-routing.md](references/model-validation-routing.md)；命中新增结构化模型族时，再读 [共享最低验证门槛](../_shared/cumcm/model-validation-minimums.md)。
- 涉及 PDF、图表、摘要版面或字体：读 [visual-final-qa.md](references/visual-final-qa.md)。
- 运行脚本或使用清单：读 [automation.md](references/automation.md)。

## 执行顺序

### 1. 建立材料清单与审查范围

列出并标记 `VERIFIED / MISSING / UNREADABLE / NOT_PROVIDED`：

- 原题、附件、结果模板和当届官方规则；
- 最终论文 PDF/Word 与 LaTeX/Markdown 源文件；
- 最终代码入口、数据、结果文件和图表；
- `audit_manifest.json` 中的规范版本、上游 manifest、`frozen_files`、冻结结果、容差/hash、正文数字和支撑材料声明；
- 支撑材料目录或压缩包；若确实没有，确认 `has_support_materials=false` 及附录规定说明；
- AI 使用记录与 `AI 工具使用详情.pdf`；
- 上一版审查报告（RECHECK 模式）。

先声明本次未核验范围。缺少原题或代码时，不得给“题意覆盖通过”或“模型—代码一致”结论；但在 PAPER_ONLY 中，这些属于有意延后，不构成审查未完成。

PAPER_ONLY 不执行 FULL 冻结门禁，但也不得因材料少而只列一个发现项。先建立 [paper-only-coverage.md](references/paper-only-coverage.md) 规定的 16 个核心模块清单；随后逐项填入证据和 `PASS / WARN / FAIL / UNVERIFIED`。缺少论文内部必要证据时标记 `UNVERIFIED`；代码、结果文件、支撑材料、AI 详情文件及工程卫生统一写 `DEFERRED_TO_FULL / OUT_OF_SCOPE`，不能混入 FAIL 或 UNVERIFIED 计数。

### 2. 运行确定性脚本审计

在项目根目录运行：

```bash
python3 <skill-dir>/scripts/audit_submission.py <project-root> \
  --mode paper-only \
  --manifest <project-root>/audit_manifest.json \
  --compile-latex \
  --render-pdf \
  --visual-dir <project-root>/.final-audit-visual
```

示例使用 PAPER_ONLY；执行 FULL、VISUAL_ONLY 或 RECHECK 时把 `--mode` 改为对应的小写模式名。

脚本默认只读。除非用户明确授权执行最终代码，否则不要加 `--run-entrypoint`。脚本输出只作为证据，不替代语义审查和逐页视觉审查。

脚本将确定性事实与启发式线索分开，并先应用模式边界：只有当前模式负责的文件缺失、hash/行列/容差冲突、明确禁词或编译错误才能形成 P0/P1。PAPER_ONLY 的图表占位写 `DEFERRED_TO_DRAWING`，交付材料缺失写 `DEFERRED_TO_FULL / OUT_OF_SCOPE`；摘要自定义命令、字体别名、邮箱/GitHub、页面空白候选和语言模板感只能形成 WARN/UNVERIFIED。

### 3. 执行语义审查

按 [audit-checklist.md](references/audit-checklist.md) 逐项检查：题意覆盖、跨问接口、模型输出到决策的映射、模型选择证据链、数据处理、公式与单位、模型—算法—代码—结果—图表—正文一致性、结构参数来源、验证、引用、结论边界和反向证据链。其中“模型选择证据链”必须包含题面事实来源反查：对“题目给出、附件提供、根据题设、由题目可知”等表述，若涉及参数、分布、相关系数、阈值、关系矩阵、模拟边或权重，必须对照原题/附件。确认属于本队设定、模拟或估计，却写成题设事实时判 P1。

PAPER_ONLY 的人工/语义审查必须按以下顺序执行，不得因为脚本先发现“文献少于 10 篇”、缩进或其他易检项而提前停止或改变阅读顺序：

1. 题目覆盖 + 模型/结果闭环；
2. 跨问接口 + 模型输出→最终决策；
3. 模型选择依据 + 题面事实/结构参数来源反查 + 关键验证；
4. 连接过渡 + AI/百科式语言 + 术语一致性；
5. 引用格式 + 跳转 + 语义正确性；
6. 压缩冗余 + 章节结构；
7. 段首缩进等源码排版。

自动脚本可以先收集全部证据，但脚本发现顺序不是语义审查顺序、报告修复顺序或提前下结论的依据。前三步没有完成前，不得只输出引用数量、格式或排版问题。

再按 [language-transition-audit.md](references/language-transition-audit.md) 独立完成六项审查：

- 相邻段落/章节的连接与过渡，重点回答“上一段结论是否解释了下一段为什么出现”；
- 长句、多层逻辑连接和抽象名词堆叠造成的可读性风险；
- 模型介绍是否停留在百科式功能描述，而没有给出对本题数据、约束和任务的适配理由；
- 同一技术概念、动作、模型或方案是否在未定义差异的情况下换名称；
- 是否使用“相关方法见文献”“具体算法参见文献”“详见文献”等展示式引用，替代“方法/主张 + 就近 citation”的学术表达；
- “问题分析—候选比较—最终模型”的叙事边界，防止证据出现前提前写死最终模型。

这些项目以语义判断为主。自动脚本只可定位候选句，不能仅凭句长、连接词或关键词把它们判为 P0/P1。自然衔接清楚时不强求过渡句，更不得为每段套用统一句式。

PAPER_ONLY 还必须把引用拆为四层分别核验：源码命令与编号格式、citation key 与文末条目、最终 PDF 跳转、正文主张与文献原文支持。不能用“参考文献数量足够”代替其余三层；只有标题或主题可见而无法取得文献原文时，引用语义一律标记 `UNVERIFIED`。按 [paper-only-coverage.md](references/paper-only-coverage.md) 输出引用完整性矩阵。

对每一问至少建立一行映射：

| 题目要求 | 论文位置 | 核心结果 | 结果文件 | 代码入口 | 验证 | 状态 |
|---|---|---|---|---|---|---|

PAPER_ONLY 发现论文公式与前文定义冲突时，可以判 `P1 + NEED_CODE_CONFIRMATION`，但建议必须先要求 FULL 核对代码：代码也错才升级 `P0 + RECOMPUTE_REQUIRED`；代码正确则只修论文公式及相关文字，不得在无代码证据时直接要求重算全部结果。跨问数值不同时，先核对是否同一方案、同一评估集、同一参数口径以及是否为新联合情景下的重新评估；换口径重评通常为 P2/WARN，同口径矛盾才判 P1。

### 4. 执行视觉审查

FULL 和 VISUAL_ONLY 仅对最终冻结 PDF 做完整逐页渲染。PAPER_ONLY 可查看当前渲染以辅助正文审核，但不得给“最终视觉已通过”结论；其中“待绘制/待补图/此处插入”等占位写 `DEFERRED_TO_DRAWING`。VISUAL_ONLY 或 FULL 在最终 PDF 中确认占位时直接判 P1，无需再等下一模式确认。使用 `render_pdf_for_audit.py` 生成所有页面 PNG、全文 contact sheet 和分组 contact sheet，再实际查看渲染图；不得只凭源文件或空白率指标推断最终版面。

### 5. 执行反向证据链抽查

至少追踪：

- 每问一个核心结论；
- 每个最终策略或强制结果文件；
- 摘要中的全部结论级数字；
- 全文最重要的创新或改进。

对每条结论按“结论 → 图表/表格 → 冻结结果 → 重算结果 → 代码 → 模型/参数 → 原题”追踪。PAPER_ONLY 只对论文内可见层给结论，外部层写 `DEFERRED_TO_FULL`，不得把未提供代码等同于证据链断裂。FULL 用 manifest 的 `artifact_checks` 和 `paper_claims` 执行 hash、行列、数值容差和正文数字核对；确认关键层断开后再按影响判 P0/P1。

### 6. 生成固定报告

严格使用 [severity-and-report.md](references/severity-and-report.md) 的状态、优先级和报告结构。每个 P0/P1 必须包含：位置、证据、违反规则、风险和建议；不得只写“有问题”。

PAPER_ONLY 报告必须先给 `Audit Coverage`，再列发现项和独立的 `Deferred to FULL / Drawing / Out of Scope` 表。16 个核心模块每项只能填写 `PASS / WARN / FAIL / UNVERIFIED` 之一并附证据；阶段状态与严重度分开记录。不新增 Coverage 模块，但“模型选择证据链”行必须附一张简短的“题面事实与模型设定来源矩阵”。总状态只用 `PAPER_AUDIT_PASS / PAPER_AUDIT_COMPLETE_WITH_WARNINGS / PAPER_AUDIT_COMPLETE_WITH_BLOCKERS`；只有当前模式必需材料本身不可读或缺失，才使用 `INCOMPLETE_AUDIT_SCOPE`。

## 判定纪律

- **脚本能确认的事实**：报告实际文件、页码、行号、字段、数值或日志。
- **需要人工判断的内容**：模型是否合理、阈值/权重是否正确、语言是否有 AI 感、图表是否美观或冗余，明确写“语义判断”或“视觉判断”，不得由脚本直接判 FAIL。
- **证据不足**：写 `UNVERIFIED`，并说明缺少什么材料。
- **规则冲突**：优先 S0，再执行 S1；在报告中写明冲突来源。
- **建议而非硬规则**：不得升级为 P0。
- **同一根因**：合并成一个主问题并列出受影响位置，避免用重复计数夸大问题数量。
- **证据升级**：先记录当前证据能支持的严重度和阶段状态；进入 FULL 后获得代码/结果/最终 PDF 证据时可以升级或降级，不能在 PAPER_ONLY 一次定死。

## 修改权限边界

默认只审查，不修改任何文件。

用户另行明确要求修复时，可以自动修复：确定性的编号、交叉引用、文献编号、明显错别字、匿名路径、确定性排版错误和文件清单错误；修复后必须重新审计。

只报告、不自动修改：模型选择、阈值、参数、模型假设、数据删除规则、结果解释、结论力度、候选模型选择、AI 风格改写、大段正文重构及任何会改变数学含义的内容。

## 联网与 AI 合规

- 审查当前官方规则时优先使用用户提供的当届正式文件；若用户明确要求联网核验，限定到官方来源。
- 比赛进行中不得主动检索、发布或讨论赛题内容；遵守当届纪律。
- 使用本 Skill 本身属于 AI 使用。若用于正式参赛论文审查，提醒团队将用途、提示方式、采纳情况和人工核验写入 AI 使用记录，并按当届规则如实声明。

## 完成条件

只有 FULL 模式、入口门禁通过、所有 P0 清零、P1 已处理或有明确人工接受依据、最终 PDF 已逐页视觉确认、关键重算结果与冻结结果/正文数字一致、反向证据链与提交文件均可核验时，才允许给出可提交状态。任何范围受限的审查都不能声称“论文已可交卷”。

PAPER_ONLY 只有在 16 个核心模块全部出现在 Audit Coverage、题面事实与模型设定来源矩阵已完成、术语一致性矩阵已完成、缩进已完成可用源码层审查、引用完整性矩阵已生成且关键语义边界均有状态后才算执行完成。代码、结果文件、支撑材料和 AI 详情文件不参与 PAPER_ONLY 完成度；它们必须出现在 `Deferred to FULL`。缺少原题/附件时，来源矩阵保持 `UNVERIFIED`，但不得省略或将自设参数默认为题设事实。

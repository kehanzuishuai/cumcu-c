---
name: 数模审题
description: 根据单道数学建模 C 题的原始题面和附件，完成证据化审题、结构识别、模型选择与比较、数学建模、编程求解、验证和结果冻结，并生成论文可读取的稳定接口。仅适用于题号已经确定后的完整处理、关键口径冻结和已有解读复核；不在缺少原题时臆测题意，也不把未运行的候选模型伪装成已验证结果。
metadata:
  short-description: 数学建模赛题证据化解读
---

# 数学建模赛题解读

把自然语言题面翻译为可执行的建模规格，而不是复述题面或堆砌算法名。最终产物应让另一名队员能够独立回答：题目要什么、使用哪些数据、采用什么口径、哪些约束不能违反、如何验证，以及论文和附件要交付什么。

通用 C 题规则以 `../_shared/cumcm/C题规范.md` 为唯一 S1 规范源；本 Skill 只保留审题专属方法。跨 Skill 字段见 `../_shared/cumcm/interfaces.md`。

## 单题工作深度

- **full**：完整处理一道人选已确定的 C 题，从题意与附件审计开始；若出现 `BLOCKING` 先输出歧义文件并等待确认，解除后仍由本 Skill 继续模型比较、建模求解与验证。
- **re-review**：复核已有解读，列出新增、遗漏、争议和需要重算的口径。
- **paper-ready**：仅在关键口径完成证据化或人工确认后，锁定主模型、基线、参数来源、代码/求解器计划、验证门槛、跨问接口、失败输出和论文接口，并继续完成实际求解、验证与结果冻结；结构校验不能替代运行证据。

单道 C 题请求默认做 full。只有用户要求论文级蓝图、复现规格或完整方案，且冻结门禁通过时才进入 paper-ready。本 Skill 只处理题号已经确定的一道 C 题。

`PAPER_READY` 只表示题意与建模合同允许进入正式求解，不等于数值结果已经产生。同一 Skill 随后继续完成代码、求解、验证、灵敏度/稳健性和结果文件；论文写作必须同时确认这些实际产物存在，不能把结构 manifest 当作计算完成证明。

## 输入与独立性

1. 登记竞赛、年份、题号、原题、附件、结果模板和用户要求的输出深度；每项标记 `provided`、`missing` 或 `unreadable`。
2. 首次独立解读默认只读原题和附件，不读优秀论文、旧解读或标准答案。只有 re-review 或用户明确要求对照已有材料时才读取它们。
3. 缺少附件不等于附件没有约束。明确写出未核验范围，并降低结论强度。

## 必做流程

1. **材料清点。** 核对原题 PDF 页数、附件目录、工作表/字段、视频或图像、结果模板、文件名、单位和精度。可先运行 `scripts/inventory_problem.py`，但清单不能替代实际读取。
2. **题目定位。** 用一句话写清对象、输入、状态/关系、决策或估计任务和最终目标；随后给出跨小问任务链。
3. **证据分层。** 对关键结论使用 `[题面事实]`、`[附件事实]`、`[官方勘误]`、`[必要推论]`、`[主解释]`、`[可检验假设]`、`[备选解释]`、`[待计算]`，并执行下述证据优先级门禁。
4. **关键歧义门禁。** `歧义与口径确认.md` 只保存真正的题意歧义：高等级证据不能唯一确定，且不同解释会改变对象定义、数据粒度、HARD 约束、题目要求的目标、输出或交付。仅改变数学实现、参数、候选模型、求解方式、可行域表现或结果的选择，不得标记 `BLOCKING`；应进入模型假设、候选模型或题意决定冻结合同。高等级证据能够唯一确定时，由 AI 标记 `RESOLVED_BY_EVIDENCE`；仍有多个合理解释时才标记 `BLOCKING` 并请求用户确认。
5. **小问规格卡。** 每问至少包含动作词、分析单位、输入、输出、决策/状态变量、显式/隐含约束、目标/损失、主模型、基线/备选、验证和交付。
6. **附件审计。** 检查主键、粒度、重复结构、时间轴、空间内部点、缺失/异常、编码、跨表连接、模板结构和样本流。大文件采用分块或抽样读取，不能无理由整表载入内存。
7. **约束、假设与接口冻结。** 区分题面事实、真正题意歧义、普通模型假设和数学实现选择；将 HARD 约束写入 `约束冻结表.md`，将对象、语义角色、时间/空间维度写入 `建模粒度合同.md`，将目标定义、评价口径、聚合规则、跨问接口、候选集和输出定义等关键非粒度决定写入 `题意决定冻结合同.md`。所有普通模型设定写入固定输出 `模型假设台账.md`；没有相应条目时保留空合同。
8. **模型链。** 冻结门禁通过后，每问给一个主模型、一个朴素基线和仅在必要时启用的替代模型。先按 `references/model-routing-tree.md` 用数据结构、动作词、变量类型、不确定性和网络/状态/排队/库存/调度等专门结构缩小候选，再按 `references/problem-type-guides.md` 读取相关专项路由。模型方案必须声明实际采用的 `object + semantic_role + dimensions`、HARD 约束和题意决定，并与冻结合同逐项一致；这些选择仍属于模型设计，不改变歧义与冻结规则。
9. **建模、求解与冻结。** 主模型由统一口径比较确定后，仍在本 Skill 内完成数学表达、代码/求解器实现、数值求解、结果文件、模型验证、灵敏度/稳健性和跨问接口；论文写作只能消费已冻结模型和结果，不重新选模或求解。尚未实际运行的候选、不可复现的代码或未通过验证的结果不得写成已完成结论。
10. **冻结一致性清理。** 人工确认和合同更新后，不覆盖旧草案；重新生成 `赛题解读_final.md` 与 `Q1-QN模型方案_final.md`，把原 `*_draft.md` 移入 `_archive/`。final 报告、模型方案及全部 Markdown 冻结合同只保留唯一冻结口径，清除已失效的待确认、草稿和旧 A/B 状态。任何 backup 或非 `_archive/` 的归档目录必须移出正式交接目录。
11. **验证证据链。** 每项验证写明对象、基准/约束、指标、通过门槛或判断规则、失败影响。门槛没有依据时标 `待校准`，不得拍脑袋给数值。
12. **交付闭环。** 每问明确核心结果表、验证图、结论句、附件文件/模板、文件名、精度和摘要接口，最后做反向验收。

## 证据纪律

- 固定证据优先级：`官方勘误/补充说明 > 题面显式文字 = 官方附件显式说明/字段 > 必要数学推论 > 主解释 > 可检验假设 > 备选解释`。题面与官方附件属于同级官方显式证据：兼容时共同解释，出现不兼容值时标记 `BLOCKING: OFFICIAL_SOURCE_CONFLICT`，不得自动偏向其中一方。低等级证据不得覆盖、改写或弱化高等级证据。
- `[主解释]`、`[可检验假设]` 和 `[备选解释]` 只能填补未规定部分。若与题面或附件显式事实冲突，禁止冻结主模型并标记 `P0 EVIDENCE_OVERRIDE`。
- 不能因为附件数据难以构造、模型更方便或业务上更自然，就改变题面显式约束。任何由题面明确规定的时间、空间、主体、对象或周期粒度，不得被下游模型无证据聚合为更粗粒度并作为 HARD 规则使用。
- 优先读取原题和原始附件；文本抽取、OCR、转写或他人解读只作定位辅助。
- 给出可回查位置：文件路径、PDF 页码、工作表、字段或模板名称。无法确认时写“未核验”。
- 图示、公式排版、表头或空间结构会改变题意时，检查原始页面而不是只读抽取文本。
- 不根据文件名杜撰附件内容，不虚构数值结果、官方评分标准或因果结论。
- 不声称存在“官方唯一模型”。敏感性分析处理普通模型假设，不能替代题意确认；反过来，正常模型参数也不能因为会影响结果就升级为题意歧义。

## 关键歧义与冻结门禁

`ambiguity_decisions` 只允许：`RESOLVED_BY_EVIDENCE`、`APPROVED_BY_USER`、`UNRESOLVED`、`BLOCKING`。`VERIFIED` 表示从未形成真正歧义的普通确定事实，应写入证据卡、粒度或 HARD 合同；已经进入候选歧义核查后才由高等级证据排除其他解释的项目使用 `RESOLVED_BY_EVIDENCE`。`MODEL_ASSUMPTION` 不得进入歧义合同。

- 每个歧义项必须声明 `ambiguity_scope`，仅可为 `entity_definition`、`data_granularity`、`hard_constraint`、`objective_definition`、`required_output` 或 `delivery_requirement`。只说明“会影响结果、可行域或模型表现”不能证明存在题意歧义。
- “尽量满足需求如何数学化”“收益如何具体核算”“采用哪种模型或算法”等，在题目要求本身已经确定时属于数学实现；不得因存在多种合理实现就标记 `BLOCKING`。

- 若官方勘误、题面、附件或必要推论中的最高等级证据给出唯一标准化含义，AI 直接写入该决定并标记 `RESOLVED_BY_EVIDENCE`，不要求用户在错误选项中再次选择。
- 若最高等级证据仍支持多个合理解释，且会实质改变模型，标记 `BLOCKING`；AI 只给出选项、影响、推荐和依据，用户确认后改为 `APPROVED_BY_USER`。
- 若同级题面、官方附件或多个官方附件给出不兼容的标准化值，标记 `BLOCKING: OFFICIAL_SOURCE_CONFLICT`；只有更高等级官方勘误/补充说明或正式澄清才能解除，用户选择不能消除官方材料冲突。
- 用户确认不能覆盖明确的高等级证据；冲突时仍报告 `P0 EVIDENCE_OVERRIDE`。
- 每个 `RESOLVED_BY_EVIDENCE` 或 `APPROVED_BY_USER` 项必须列出 `freeze_targets`，明确决定应写入的合同、稳定 ID 和字段。校验器执行 `decision → freeze target → contract value` 的确定性比较；缺失或不一致报告 `P0 DECISION_NOT_PROPAGATED`。
- 普通模型假设即使影响结果或可行域，也不阻塞 paper-ready；但必须记录假设陈述、来源，并至少提供 `alternative_values`、`sensitivity`、`diagnostic`、`robustness_test` 或 `failure_condition` 之一。数值参数优先记录主值、备选值和灵敏度；结构性假设优先记录诊断、稳健性检验或失效条件。

正式生成 `赛题解读_final.md`、`建模粒度合同.md`、`约束冻结表.md`、`题意决定冻结合同.md`、`模型假设台账.md` 和 `Q1-QN模型方案_final.md` 前，必须同时满足：

1. `BLOCKING` 歧义数量为 0；
2. 所有关键题意歧义均为 `RESOLVED_BY_EVIDENCE` 或 `APPROVED_BY_USER`，从未形成歧义的事实另标 `VERIFIED`；
3. 所有 HARD 约束都有题面、附件或必要推论级证据；
4. 主解释不与题面/附件显式事实冲突；
5. `建模粒度合同.md` 已生成，每项含稳定 ID、对象、`semantic_role`、冻结维度、证据来源和 `mutable: YES/NO`；
6. 人工确认已经写回 `歧义与口径确认.md`、冻结报告和模型方案，而不是只停留在对话中；`模型假设台账.md` 已生成，非空条目均有来源和验证/挑战路径；
7. `题意决定冻结合同.md` 已生成；关键目标、评价口径、聚合规则、跨问接口、候选集和输出定义通过稳定 ID 传播到模型方案；没有相应条目时使用空合同；
8. `scripts/validate_interpretation.py` 的结构化合同检查通过；所有合同均有 `schema_version: 1`，确认决定已传播到冻结合同，模型方案具备 `object`、`semantic_role`、`used_by`、实际 `dimensions` 和 `symbol` 或明确 `null_reason`。
9. 所有 final 自然语言及 Markdown 冻结合同已重新同步；已解决决定只保留唯一口径，不残留 `BLOCKING`、`UNRESOLVED`、`INTERPRETATION_PENDING`、`DRAFT`、草稿、当前为草稿、确认后升级、待冻结、待确认、待决定、待实现确认或 A/B 待选状态；validator 不得出现 `STALE_DECISION_STATE`。

任一条件不满足时，只生成 `赛题解读_draft.md` 和 `歧义与口径确认.md`，在报告顶部写 `INTERPRETATION_PENDING`；不得标记 `paper-ready`，也不得把待确认口径写进正式约束。

## 不可省略的检查

- 分析单位正确：人、记录、批次、帧、网络节点/边、镜面、地块、产品状态等不得混淆。
- 时间原点、时间窗、单位、坐标方向和数据粒度统一，换算可追溯。
- 决策变量必须可达，不能把由运动学、流程或上游状态决定的量当独立自由变量。
- 重叠区间、覆盖区域或多事件概率按正确的并集/依赖结构处理，不默认可相加或相互独立。
- 结果模板、文件名、行列含义、指定时刻和小数精度属于题目硬交付。
- 无解、不可识别、严重外推、数据不足或约束冲突时，规定诚实的降级或弃权输出。

## 默认产物

首轮完整解读默认生成：

1. `赛题解读_draft.md`：按 `assets/interpretation-report-template.md` 组织主报告；
2. `歧义与口径确认.md`：按 `assets/ambiguity-confirmation-template.md` 只列真正的题意歧义和关键口径；没有歧义时保留空合同；
3. `附件审计.json`：有附件时登记路径、格式、大小、编码、工作表/字段、粒度、单位、异常、用途与状态；
4. `模型假设台账.md`：始终按 `assets/model-assumptions-template.md` 生成；没有普通模型假设时保留 `items: []`，非空条目记录来源和至少一种验证/挑战路径；
5. `题意决定冻结合同.md`：始终按 `assets/interpretation-decisions-template.md` 生成；没有关键非粒度决定时保留 `items: []`；
6. `验收报告.md`：按 `references/acceptance-rubric.md` 评分并列出未通过项。

冻结门禁通过后，以已更新合同为唯一来源重新生成 `赛题解读_final.md` 和 `Q1-QN模型方案_final.md`；不得直接覆盖草案。先将 `赛题解读_draft.md` 及其他 `*_draft.md` 移入 `_archive/`；backup、`draft_backup/` 及其他 archive 目录必须移出正式交接目录。冻结合同保留在当前目录供 final 和下游读取；`N` 取题目实际小问数。

final validator 通过后同时生成 `paper_ready_manifest.json`；它只记录当前规范版本、校验结果和两个 final 文件加五份冻结合同的 SHA-256，不替代原有语义复核。

可先运行 `scripts/validate_interpretation.py 赛题解读_draft.md --expected-subproblems N` 做结构预检。冻结时运行：

```bash
python <skill-dir>/scripts/validate_interpretation.py 赛题解读_final.md \
  --expected-subproblems N --stage final --project-root . \
  --ambiguities 歧义与口径确认.md \
  --granularity-contract 建模粒度合同.md \
  --hard-constraints 约束冻结表.md \
  --interpretation-decisions 题意决定冻结合同.md \
  --model-assumptions 模型假设台账.md \
  --model-plan Q1-QN模型方案_final.md \
  --json-out interpretation_validation.json \
  --manifest-out paper_ready_manifest.json
```

脚本只确定性比较结构化合同，并扫描 final 报告、final 模型方案、全部已提交 Markdown 冻结合同及同目录其他 `*_final.md` 的旧状态残留；不会用中文关键词推断全部题意，也不能替代人工语义复核。`BLOCKING=0`、`无待确认项`等明确清零表述不算残留。出现 `STALE_DECISION_STATE`、`DECISION_NOT_PROPAGATED`、`OFFICIAL_SOURCE_CONFLICT`、`GRANULARITY_CONFLICT`、`GRANULARITY_SEMANTIC_CONFLICT`、`MISCLASSIFIED_MODELING_CHOICE` 或 `EVIDENCE_OVERRIDE` 时必须停止，不得继续写作。

写作交接只允许读取 `paper_ready_manifest.json` 中列出且 hash 仍一致的 `赛题解读_final.md`、`Q1-QN模型方案_final.md` 和当前冻结合同；禁止读取任何 backup/archive 目录（包括 `_archive/`）、`*_draft.md` 或无 `_final` 后缀的旧模型方案。若 manifest 不存在、状态不是 `PAPER_READY` 或任一 hash 失配，不得启动写作 Skill。

可按题目删去不适用的小节，但不得删去题目定位、任务链、小问规格、附件审计、约束与歧义、模型链、验证与失败处理、结果交付、最终验收。

## 可移植性与发布边界

- 本目录应当能够脱离当前工作区独立使用。脚本接收用户提供的题目目录或报告路径，不依赖固定盘符、固定中文目录名或本仓库的其他文件。
- `scripts/` 中的工具面向 Python 3.9 及以上版本；`inventory_problem.py` 的 PDF 页数读取依赖可选包 `pypdf`，未安装时会明确标记为“未读取”，不会伪造页数。
- 原题 PDF、附件、优秀论文、历史解读、真实队伍数据和生成报告都属于用户材料或输出，不应随 skill 一起提交到公开仓库。测试只使用合成夹具。
- 运行脚本时优先把输出写入题目目录外的临时目录或用户指定的输出目录，避免污染 skill 本体；脚本不得修改原始材料。
- 公开发布前检查文件名、路径和示例中没有个人绝对路径、私有数据、访问令牌或未获授权转载的竞赛材料。

## 按需读取

- 完整方法、停止边界和证据解释：`references/methodology.md`
- 报告字段、歧义决策、粒度/题意决定合同、约束冻结、模型方案声明和附件 JSON：`references/output-schema.md`
- 统计/回归候选、评价指标、ODE、统计检验、优化求解器、多目标方法，以及机理、概率、网络、视频和大日志专项检查：`references/problem-type-guides.md`
- 统一六维结构卡、模型决策树、候选缩小和低频模型边界：`references/model-routing-tree.md`
- 图/网络、排队、马尔可夫、库存、目标规划、动态规划、调度、稳态与差分：`references/operations-state-routes.md`
- GM(1,1)、模糊评价、DEA、插值/拟合、PCA/因子/PLS/CCA/LDA 与聚类：`references/data-evaluation-routes.md`
- GA、PSO、SA、ACO、Tabu、NSGA-II 的精确优先门禁与验收：`references/heuristic-routing.md`
- 完成后的 P0/P1 验收与评分：`references/acceptance-rubric.md`
- paper-ready、Brief、RESAMPLE、绘图清单和冻结包接口：`../_shared/cumcm/interfaces.md`

## 边界

本 Skill 负责从审题到最终结果冻结的完整技术链。真正题意歧义未解决时先停在 `歧义与口径确认.md`；解除门禁后继续读取数据、比较基线与候选、实现并求解模型、验证结果和冻结跨问接口。论文写作阶段只组织和表述这些冻结产物，不得把候选模型名称或未经运行的公式包装成已完成结果。

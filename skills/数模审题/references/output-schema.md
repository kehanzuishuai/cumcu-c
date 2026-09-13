# 输出结构

## 完整解读主报告

首轮文件名为 `赛题解读_draft.md`，顶部写 `INTERPRETATION_PENDING`。人工确认并更新合同后，不覆盖该草案；将其移入 `_archive/`，再从冻结合同重新生成 `赛题解读_final.md`。任何 backup 或其他 archive 目录必须移出正式交接目录。不能只改文件名而不更新状态、歧义决定和自然语言结论。

### 1. 题目定位

- 一句话实质
- 主类型和副类型
- 原题、附件、模板位置与证据边界
- 最大读题风险

### 2. 任务链

用 4-8 个状态/动作节点表达。写对象如何变化，不写算法清单。

### 3. 逐句证据卡

只用于影响模型的关键语句：

| 字段 | 内容 |
| --- | --- |
| 原题语句 | 原文和页码/位置 |
| 证据标签 | 七类标签之一 |
| 数学翻译 | 变量、方程、集合、事件或规则 |
| 模型角色 | 输入/状态/决策/目标/硬约束/指标 |
| 歧义与风险 | 其他解释和错误后果 |
| 验证 | 数据核对、极限情况、敏感性或回放 |

### 4. 小问规格卡

| 字段 | 必填内容 |
| --- | --- |
| 动作词 | 建立/分析/确定/预测/优化/评价 |
| 分析对象/粒度 | 精确对象及层级 |
| 输入 | 题面常数、附件字段、上游结果 |
| 输出 | 数值、参数、区间、路径、规则、建议或文件 |
| 决策变量 | 仅可控制的量 |
| 状态变量 | 由模型演化或估计的量 |
| 显式硬约束 | 违反即不符合题意 |
| 隐含约束 | 物理/统计/时序/数据后果 |
| 目标/损失 | 数学定义和多目标聚合方式 |
| 主模型/基线/备选 | 角色明确，不列无关算法 |
| 验证门槛 | 指标和通过规则；无依据时写待校准 |
| 最终交付 | 表、图、结论、文件名和精度 |
| 致命误读 | 本题至少一项 |

### 5. 附件审计表

| 文件/工作表 | 格式/大小/编码 | 对象与粒度 | 字段/单位 | 缺失与异常 | 连接规则 | 用于小问 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |

若清洗改变分析集，报告原始、排除、合并/插值和最终样本数量。

### 6. 约束与假设台账

| ID | 内容 | 性质 | 模型入口 | 不成立的偏差/失败 | 检验或备选解释 |
| --- | --- | --- | --- | --- | --- |

### 7. 模型与接口蓝图

| 模块 | 主模型 | 基线 | 输入 | 输出 | 下游使用 |
| --- | --- | --- | --- | --- | --- |

### 8. 验证矩阵

| 验证对象 | 基线/基准/约束 | 指标 | 门槛 | 结果 | 灵敏度/稳健性 | 失败回退 | 对结论及下一问影响 |
| --- | --- | --- | --- | --- | --- | --- | --- |

模型未运行前，结果可写 `[待计算]`；其他列仍必须具体。

### 9. 交付映射

| 小问 | 核心结果表 | 验证图 | 结论句 | 指定文件/模板 | 摘要接口 |
| --- | --- | --- | --- | --- | --- |

## 歧义与口径确认

固定文件名：`歧义与口径确认.md`。只列 `kind=interpretation_ambiguity` 的真正题意歧义或其证据化解决记录。每项的 `ambiguity_scope` 必须明确指向对象定义、数据粒度、HARD 约束、题目要求的目标、输出或交付。普通确定事实使用 `VERIFIED` 并进入证据卡或冻结合同，不放入本文件；普通模型参数、候选模型、目标函数的数学实现和分布设定也不得放入该合同。

| ID | 原题/附件证据 | 待确认口径 | 选项及模型后果 | 影响范围 | 推荐与理由 | 用户决定 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |

文件末尾必须有一个 `contract-json` 代码块。`evidence.source` 保存原文及位置，`evidence.value` 保存已标准化、可机器比较的数学/结构含义。维度使用稳定英文枚举，如 `entity`、`year`、`period`、`scenario`；不要在不同文件中换同义词，也不要把整句原文放入 `value`。

```contract-json
{
  "contract_type": "ambiguity_decisions",
  "schema_version": 1,
  "items": [
    {
      "id": "time_resolution",
      "kind": "interpretation_ambiguity",
      "ambiguity_scope": "data_granularity",
      "question": "题目要求采用什么时间粒度？",
      "impact": ["data_granularity", "hard_constraint"],
      "evidence": [
        {
          "level": "problem_explicit",
          "value": ["entity", "year", "period"],
          "source": "原题第 X 页：按每一评价周期分别计算……"
        }
      ],
      "options": [
        {"value": ["entity", "year", "period"], "consequence": "按题面周期分别建模"},
        {"value": ["entity", "year"], "consequence": "聚合周期并改变 HARD 约束"}
      ],
      "recommended": ["entity", "year", "period"],
      "decision": ["entity", "year", "period"],
      "approved_by": null,
      "freeze_targets": [
        {
          "contract": "granularity_contract",
          "id": "capacity_limit",
          "field": "dimensions"
        }
      ],
      "status": "RESOLVED_BY_EVIDENCE"
    }
  ]
}
```

最高等级证据只有一个标准化值、且该项目曾形成候选歧义时，直接写入 `decision` 并标记 `RESOLVED_BY_EVIDENCE`；从未形成真正歧义的事实使用 `VERIFIED` 并移出本合同。最高等级证据仍支持多个合理值时才标记 `BLOCKING`，用户决定后改为 `APPROVED_BY_USER` 并填写 `approved_by`。用户决定若与唯一高等级证据冲突，仍判 `P0 EVIDENCE_OVERRIDE`。

题面 `problem_explicit` 与官方附件 `attachment_explicit` 同级；兼容时共同解释，不兼容时标记 `BLOCKING: OFFICIAL_SOURCE_CONFLICT`。`official_correction` 高于二者，可在明确对应关系后解决被正式更正的冲突。每个 `RESOLVED_BY_EVIDENCE` 或 `APPROVED_BY_USER` 项都必须有非空 `freeze_targets`；每个目标包含 `contract`、稳定 `id` 和可用点号表示嵌套路径的 `field`。目标必须指向粒度、HARD、题意决定、模型假设或模型方案等下游合同，不能回指 `ambiguity_decisions` 自证。目标字段必须与 `decision` 结构化相等，否则报告 `P0 DECISION_NOT_PROPAGATED`。

`ambiguity_scope` 用来声明它改变了题目要求的哪一部分；`impact` 只记录可行域、结果、模型方案等下游后果。校验器不因 `impact` 中出现 `feasible_region` 或 `result` 就认定为题意歧义；最终分类仍须回查题面和附件语义。

仅因不同数学实现会改变结果、可行域表现或模型复杂度，不能将其归为题意歧义。若题目要求本身已经确定，“怎样把尽量满足写成目标函数”“收益采用哪种可复现核算式”“选择哪个候选模型”等应进入候选模型、模型假设或下述题意决定冻结合同；误放入歧义合同时报告 `P0 MISCLASSIFIED_MODELING_CHOICE`。

## 题意决定冻结合同

固定文件名：`题意决定冻结合同.md`。它承载目标定义、评价口径、聚合规则、跨问接口、候选集合和输出定义等需要稳定传给模型方案、但不属于粒度、HARD 约束或普通模型假设的关键决定。没有相应决定时输出合法空合同。

```contract-json
{
  "contract_type": "interpretation_decisions",
  "schema_version": 1,
  "items": [
    {
      "id": "q2_q3_interface",
      "category": "cross_question_interface",
      "statement": "Q2向Q3传递统一口径下的候选方案及其评价结果",
      "value": {
        "payload": "candidate_plans_and_scores",
        "dimensions": ["candidate", "scenario"]
      },
      "source": "模型接口设计；题面未规定中间变量名称",
      "status": "MODEL_DESIGN",
      "used_by": ["Q2", "Q3"],
      "freeze_targets": [
        {
          "contract": "model_plan",
          "field": "implemented_interpretation_decisions.q2_q3_interface"
        }
      ]
    }
  ]
}
```

`category` 只使用 `objective_definition`、`evaluation_basis`、`aggregation_rule`、`cross_question_interface`、`candidate_set` 或 `output_definition`。`status` 可为 `VERIFIED`、`RESOLVED_BY_EVIDENCE`、`APPROVED_BY_USER` 或 `MODEL_DESIGN`；正常数学实现可以直接使用 `MODEL_DESIGN`，不要求用户逐项确认，也不计入 BLOCKING。每项必须通过稳定 ID 写入模型方案的 `implemented_interpretation_decisions`；不一致报告 `P0 DECISION_NOT_PROPAGATED`。

## 模型假设台账

固定文件名：`模型假设台账.md`。它是 final 必需合同，不能因为未传 `--model-assumptions` 而跳过。没有普通模型假设时输出合法空合同：

```contract-json
{
  "contract_type": "model_assumptions",
  "schema_version": 1,
  "items": []
}
```

普通模型假设不属于 `ambiguity_decisions`；完整披露后不阻塞 final。非空条目必须有稳定 ID、假设陈述、来源，并至少提供一种验证/挑战路径：`alternative_values`、`sensitivity`、`diagnostic`、`robustness_test` 或 `failure_condition`。

| ID | 假设陈述 | 来源 | 主值（可选） | 验证/挑战路径 | 失效处理 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |

```contract-json
{
  "contract_type": "model_assumptions",
  "schema_version": 1,
  "items": [
    {
      "id": "risk_confidence",
      "statement": "风险度量置信水平取 0.95",
      "source": "模型设定；题面未指定",
      "main_value": 0.95,
      "alternative_values": [0.90, 0.99],
      "sensitivity": "比较目标值、可行性和关键决策是否稳定",
      "status": "MODEL_ASSUMPTION"
    },
    {
      "id": "independent_errors",
      "statement": "误差项在主体之间相互独立",
      "source": "模型结构假设；题面与附件未指定",
      "diagnostic": "检查分组残差相关性和聚类结构",
      "failure_condition": "存在显著组内相关或残差相关矩阵出现稳定块结构",
      "fallback_model": "改用聚类稳健标准误或相关误差模型",
      "status": "MODEL_ASSUMPTION"
    }
  ]
}
```

数值型参数优先使用“主值 + 备选值 + 灵敏度”；结构性假设可以不提供 `main_value` 或 `alternative_values`，改用诊断、稳健性检验或明确失效条件。合法的 `MODEL_ASSUMPTION` 不参与 `BLOCKING` 计数，但缺少整份合同会阻止 final。

## 建模粒度合同

固定文件名：`建模粒度合同.md`。人工可读表与结构化块必须逐项一致。

| ID | 对象 | 语义角色 | 冻结粒度 | 证据等级与位置 | 状态 | mutable |
| --- | --- | --- | --- | --- | --- | --- |

```contract-json
{
  "contract_type": "granularity_contract",
  "schema_version": 1,
  "items": [
    {
      "id": "capacity_limit",
      "object": "容量上限",
      "semantic_role": "constraint",
      "dimensions": ["entity", "year", "period"],
      "evidence_level": "problem_explicit",
      "evidence_ref": "原题第 X 页：每个评价周期分别执行……",
      "status": "VERIFIED",
      "mutable": "NO"
    }
  ]
}
```

题面明确规定的粒度默认 `mutable: NO`。下游需要修改时必须返回审题阶段处理；不能在模型方案或论文中静默改动。

每项强制包含非空 `object`、非空 `dimensions` 和稳定的 `semantic_role`。角色只使用 `observation`、`parameter`、`state`、`decision`、`constraint`、`output`、`interface`。观测数据、决策变量、约束和最终输出即使维度相近，也必须使用不同稳定 ID 和对应角色；只有同一 ID 的 `object + semantic_role + dimensions` 才与模型方案做一致性比较。`schema_version` 必须为整数 `1`；缺失或非法均为 `P0 CONTRACT_SCHEMA_ERROR`。

## 约束冻结表

固定文件名：`约束冻结表.md`。HARD 项必须有高等级证据；模型设定另列为 `MODEL_ASSUMPTION`，不能混入 HARD。

| ID | 约束 | 类型 | 证据等级与位置 | 关联合同项 | 状态 |
| --- | --- | --- | --- | --- | --- |

```contract-json
{
  "contract_type": "hard_constraints",
  "schema_version": 1,
  "items": [
    {
      "id": "H-capacity-limit",
      "statement": "每个对象按年、周期分别执行容量上限",
      "type": "HARD",
      "evidence_level": "problem_explicit",
      "evidence_ref": "原题第 X 页：每个评价周期分别执行……",
      "granularity_ids": ["capacity_limit"],
      "status": "VERIFIED"
    }
  ]
}
```

每个 HARD 项强制包含非空 `statement` 和 `evidence_ref`。所有合同均强制 `schema_version: 1`；缺失或非法时阻止冻结。

## Q1-QN 模型方案声明

正式模型方案除正文外，必须声明实际采用的粒度、符号和 HARD 约束实现；第二阶段按实际小问数量重新生成 `Q1-QN模型方案_final.md`，不得覆盖或继续沿用冻结前方案。

每问正文还必须按 `model-routing-tree.md` 的统一顺序记录：适用任务/触发条件、数据结构与前提检查、朴素基线、主模型/必要候选、核心变量与数学结构、推荐求解方法/软件、必做验证、灵敏度或稳健性、常见误用、失败后的降级/替代方案、与下一问可能的接口。结构化合同只校验冻结对象和决定，不替代这份语义路线卡。

模型最终结果由本 Skill 的实际代码/求解器产生。方案中应给出代码入口、数据/参数版本、求解状态、随机种子或求解器设置、结果文件及其下游字段；未实际运行的路线继续标记 `[待计算]`，不得写成已验证结果或让论文写作重新选择模型。

```contract-json
{
  "contract_type": "model_plan",
  "schema_version": 1,
  "items": [
    {
      "id": "capacity_limit",
      "object": "容量上限",
      "semantic_role": "constraint",
      "dimensions": ["entity", "year", "period"],
      "symbol": "C[i,t,p]",
      "used_by": ["Q1", "Q2", "Q3"]
    }
  ],
  "implemented_hard_constraints": ["H-capacity-limit"],
  "implemented_interpretation_decisions": {
    "q2_q3_interface": {
      "payload": "candidate_plans_and_scores",
      "dimensions": ["candidate", "scenario"]
    }
  }
}
```

结构化块是确定性校验接口，不替代正文解释。若合同项、维度或 HARD 约束实现不一致，先修正方案或返回审题确认，不能绕过校验。

每个模型方案项必须声明非空 `object`、稳定 `semantic_role`、非空 `used_by` 和实际采用的非空 `dimensions`，并且在 `symbol` 与非空 `null_reason` 中恰好提供一个。确实没有单一符号时，例如某项只由求解器接口或离散规则实现，可省略 `symbol` 并明确写出 `null_reason`；不得两个字段都空。模型方案还必须包含对象形式的 `implemented_interpretation_decisions`；即使题意决定合同为空，也保留 `{}`。合同同样必须声明 `schema_version: 1`。

## 校验结果

`findings` 中每条结果同时包含：

```json
{
  "severity": "P0|P1|P2|P3",
  "gate": "BLOCKING|NON_BLOCKING",
  "code": "MACHINE_READABLE_CODE",
  "message": "定位与修复说明"
}
```

`severity` 表示优先级，`gate` 表示是否阻止 `PAPER_READY`。为兼容旧调用方，脚本继续输出 `errors`（BLOCKING）和 `warnings`（NON_BLOCKING）；最终状态只由 BLOCKING 项决定。确定性的合同/schema/传播错误直接归 `P0 + BLOCKING`，普通 P1 默认进入 `NON_BLOCKING`。

## 附件审计 JSON

```json
{
  "problem": "YEAR-PROBLEM",
  "root": "absolute/or/workspace/path",
  "status": "complete|partial|blocked",
  "files": [
    {
      "path": "relative/path",
      "format": "pdf|xlsx|csv|video|image|archive|other",
      "size_bytes": 0,
      "encoding": null,
      "sheets_or_structure": [],
      "granularity": "",
      "keys_and_units": [],
      "missing_or_anomalies": [],
      "used_by": [],
      "delivery_constraints": [],
      "audit_status": "verified|sampled|unreadable|missing"
    }
  ],
  "unverified_scope": []
}
```

## Paper-Ready 追加项

- 固定主模型名称和数学定义；
- 参数/阈值来源台账；
- 求解器编码、初值、修复、终止和随机种子；
- 跨问变量的单位、粒度、时间和变换；
- 收敛、守恒、预测或稳定性门槛；
- 失败、无解、弃权和分布外输出；
- 摘要的一条核心贡献和一条验证主线。
- `BLOCKING=0`，关键歧义状态已冻结；
- `建模粒度合同.md`、`约束冻结表.md` 与模型方案结构化声明一致；
- `题意决定冻结合同.md` 已生成，非空决定已传播到模型方案，空合同使用 `items: []`；
- 人工决定已写回冻结文件，状态没有把“主解释”误标为 `VERIFIED`。
- 固定模型假设合同已生成；非空条目记录来源和至少一种验证/挑战路径，空合同使用 `items: []`，且不计入 BLOCKING。
- `赛题解读_final.md`、`Q1-QN模型方案_final.md`、全部 Markdown 冻结合同及同目录其他 `*_final.md` 已重新同步；已解决决定只出现唯一口径，无旧候选、待确认、草稿或待冻结状态；
- 原 `*_draft.md` 只可移入 `_archive/`，final 目录顶层不再保留草案；backup、`draft_backup/` 及其他 archive 目录已移出正式交接目录；
- 写作阶段只读取 `*_final.md` 和当前冻结合同，并排除任何 backup/archive 目录（包括 `_archive/`）、`*_draft.md`。

若任一 final 自然语言或 Markdown 冻结合同仍出现未清零的 `BLOCKING`、`UNRESOLVED`、`INTERPRETATION_PENDING`、`DRAFT`、草稿、当前为草稿、确认后升级、待冻结、待确认、待决定、待实现确认或 A/B 待选表述，校验器报告 `P0 STALE_DECISION_STATE` 并阻止 `PAPER_READY`。`BLOCKING=0`、`无待确认项`等明确清零摘要不属于旧状态。

# 歧义与口径确认

> 本文件只列真正题意歧义及其证据化解决记录：不同解释必须改变对象定义、数据粒度、HARD 约束、题目要求的目标、输出或交付，而不是只改变数学实现、可行域表现或结果。普通模型参数和假设进入 `模型假设台账.md`，关键数学实现进入 `题意决定冻结合同.md`。存在 `BLOCKING` 时，审题状态必须保持 `INTERPRETATION_PENDING`。

`evidence.source` 保存原题/附件/官方勘误原文及位置；`evidence.value` 保存标准化、可机器比较的数学或结构含义。曾形成候选歧义、重核高等级证据后只剩唯一解释时标为 `RESOLVED_BY_EVIDENCE`；从未形成真正歧义的普通事实不进入本文件。题面与官方附件同级，二者冲突时标记 `BLOCKING: OFFICIAL_SOURCE_CONFLICT`。

| ID | 题意范围 | 原题/附件证据 | 待确认口径 | 选项及模型后果 | 下游影响 | 推荐与理由 | 用户决定 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {{AMBIGUITY_ID}} | {{AMBIGUITY_SCOPE}} | {{SOURCE_AND_LOCATION}} | {{QUESTION}} | {{OPTIONS_AND_CONSEQUENCES}} | {{IMPACT}} | {{RECOMMENDATION}} | {{DECISION_OR_EMPTY}} | {{BLOCKING / ...}} |

```contract-json
{
  "contract_type": "ambiguity_decisions",
  "schema_version": 1,
  "items": [
    {
      "id": "{{AMBIGUITY_ID}}",
      "kind": "interpretation_ambiguity",
      "ambiguity_scope": "{{entity_definition / data_granularity / hard_constraint / objective_definition / required_output / delivery_requirement}}",
      "question": "{{QUESTION}}",
      "impact": ["{{downstream effect, e.g. feasible_region / result / model_plan / delivery}}"],
      "evidence": [
        {
          "level": "{{official_correction / problem_explicit / attachment_explicit / necessary_deduction / main_interpretation / testable_assumption / alternative_interpretation}}",
          "value": {{JSON_VALUE}},
          "source": "{{SOURCE_AND_LOCATION}}"
        }
      ],
      "options": [
        {"value": {{JSON_VALUE}}, "consequence": "{{MODEL_CONSEQUENCE}}"}
      ],
      "recommended": {{JSON_VALUE_OR_NULL}},
      "decision": {{JSON_VALUE_OR_NULL}},
      "approved_by": {{JSON_STRING_OR_NULL}},
      "freeze_targets": [],
      "status": "{{RESOLVED_BY_EVIDENCE / APPROVED_BY_USER / UNRESOLVED / BLOCKING}}"
    }
  ]
}
```

`RESOLVED_BY_EVIDENCE` 和 `APPROVED_BY_USER` 的 `freeze_targets` 不得为空；每项写明目标 `contract`、稳定 `id` 和 `field`。`UNRESOLVED/BLOCKING` 可暂留空数组。

`ambiguity_scope` 决定这是不是题意歧义，`impact` 只记录其下游后果。不得因为某个数学实现会影响可行域或结果，就把它写成 `BLOCKING`。

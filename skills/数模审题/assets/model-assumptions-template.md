# 模型假设台账

> 本文件是 final 固定合同，登记普通模型假设和待验证参数。没有普通模型假设时仍保留本文件，并将 `items` 写为空数组。假设不是题意歧义，完整披露后不计入 `BLOCKING`；不得用模型假设覆盖题面或附件的高等级证据。

| ID | 假设陈述 | 来源 | 主值（可选） | 验证/挑战路径 | 失效处理 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| {{ASSUMPTION_ID}} | {{STATEMENT}} | {{SOURCE}} | {{MAIN_VALUE_OR_EMPTY}} | {{ALTERNATIVE / SENSITIVITY / DIAGNOSTIC / ROBUSTNESS}} | {{FAILURE_CONDITION_OR_FALLBACK}} | MODEL_ASSUMPTION |

```contract-json
{
  "contract_type": "model_assumptions",
  "schema_version": 1,
  "items": [
    {
      "id": "{{ASSUMPTION_ID}}",
      "statement": "{{STATEMENT}}",
      "source": "{{SOURCE}}",
      "main_value": {{OPTIONAL_JSON_VALUE}},
      "alternative_values": [{{OPTIONAL_JSON_ALTERNATIVES}}],
      "sensitivity": "{{OPTIONAL_SENSITIVITY}}",
      "diagnostic": "{{OPTIONAL_DIAGNOSTIC}}",
      "robustness_test": "{{OPTIONAL_ROBUSTNESS_TEST}}",
      "failure_condition": "{{OPTIONAL_FAILURE_CONDITION}}",
      "fallback_model": "{{OPTIONAL_FALLBACK_MODEL}}",
      "status": "MODEL_ASSUMPTION"
    }
  ]
}
```

生成时删除不适用的可选字段；不要把空字符串或空数组当成验证路径。至少保留 `alternative_values`、`sensitivity`、`diagnostic`、`robustness_test`、`failure_condition` 中一个有效字段。没有假设时使用：

```contract-json
{
  "contract_type": "model_assumptions",
  "schema_version": 1,
  "items": []
}
```

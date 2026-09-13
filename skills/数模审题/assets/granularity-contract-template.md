# 建模粒度合同

> 下游模型方案、写作和审计必须按稳定 ID 读取本合同。题面明确规定的粒度默认 `mutable: NO`。

| ID | 对象 | 语义角色 | 冻结粒度 | 证据等级与位置 | 状态 | mutable |
| --- | --- | --- | --- | --- | --- | --- |
| {{ITEM_ID}} | {{OBJECT}} | {{SEMANTIC_ROLE}} | {{DIMENSIONS}} | {{EVIDENCE_LEVEL_AND_REF}} | {{STATUS}} | {{YES / NO}} |

```contract-json
{
  "contract_type": "granularity_contract",
  "schema_version": 1,
  "items": [
    {
      "id": "{{ITEM_ID}}",
      "object": "{{OBJECT}}",
      "semantic_role": "{{observation / parameter / state / decision / constraint / output / interface}}",
      "dimensions": ["{{DIMENSION}}"],
      "evidence_level": "{{official_correction / problem_explicit / attachment_explicit / necessary_deduction / main_interpretation}}",
      "evidence_ref": "{{SOURCE_AND_LOCATION}}",
      "status": "{{VERIFIED / RESOLVED_BY_EVIDENCE / APPROVED_BY_USER}}",
      "mutable": "{{YES / NO}}"
    }
  ]
}
```

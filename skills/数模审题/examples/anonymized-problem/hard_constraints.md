# HARD 约束冻结表

| ID | 约束 | 证据 | 状态 |
| --- | --- | --- | --- |
| H-total-units | 总设施数不超过 6 | 题面问题 2 | VERIFIED |
| H-zone-capacity | 每区设施数不超过容量 | 题面与区域附件 | VERIFIED |
| H-integrality | 设施数为非负整数 | 题面对象定义与必要推论 | VERIFIED |
| H-delivery-schema | 固定列、区域行和两位小数 | 题面交付与结果模板 | VERIFIED |

```contract-json
{
  "contract_type": "hard_constraints",
  "schema_version": 1,
  "items": [
    {
      "id": "H-total-units",
      "statement": "所有区域部署设施总数不超过6",
      "type": "HARD",
      "evidence_level": "problem_explicit",
      "evidence_ref": "problem_statement.md 问题2：总设施数不超过6个",
      "granularity_ids": ["deployment_decision"],
      "status": "VERIFIED"
    },
    {
      "id": "H-zone-capacity",
      "statement": "每个区域部署数量不得超过附件给定容量",
      "type": "HARD",
      "evidence_level": "attachment_explicit",
      "evidence_ref": "attachments/zones.csv: capacity",
      "granularity_ids": ["deployment_decision"],
      "status": "VERIFIED"
    },
    {
      "id": "H-integrality",
      "statement": "设施部署数量必须为非负整数",
      "type": "HARD",
      "evidence_level": "necessary_deduction",
      "evidence_ref": "problem_statement.md：设施按个数部署",
      "granularity_ids": ["deployment_decision"],
      "status": "VERIFIED"
    },
    {
      "id": "H-delivery-schema",
      "statement": "结果按区域保留四个固定列且降幅保留两位小数",
      "type": "HARD",
      "evidence_level": "problem_explicit",
      "evidence_ref": "problem_statement.md 交付要求与 attachments/result_template.csv",
      "granularity_ids": ["result_row"],
      "status": "VERIFIED"
    }
  ]
}
```


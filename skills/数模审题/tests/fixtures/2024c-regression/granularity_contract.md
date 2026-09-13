# 建模粒度合同

| ID | 对象 | 冻结粒度 | 证据来源 | 状态 | mutable |
| --- | --- | --- | --- | --- | --- |
| planting_decision | 种植决策 | 地块×作物×年份×季次 | 题面与附件 | VERIFIED | NO |
| sales_limit | 销售量上限 | 作物×年份×季次 | 题面“每季” | RESOLVED_BY_EVIDENCE | NO |

```contract-json
{
  "contract_type": "granularity_contract",
  "schema_version": 1,
  "items": [
    {
      "id": "planting_decision",
      "object": "种植决策",
      "semantic_role": "decision",
      "dimensions": ["plot", "crop", "year", "season"],
      "evidence_level": "problem_explicit",
      "evidence_ref": "2024 C 题题面与附件中的地块、作物、年份、季次",
      "status": "VERIFIED",
      "mutable": "NO"
    },
    {
      "id": "sales_limit",
      "object": "销售量上限",
      "semantic_role": "constraint",
      "dimensions": ["crop", "year", "season"],
      "evidence_level": "problem_explicit",
      "evidence_ref": "2024 C 题题面：每季种植的农作物均在当季销售",
      "status": "RESOLVED_BY_EVIDENCE",
      "mutable": "NO"
    }
  ]
}
```

# 约束冻结表

```contract-json
{
  "contract_type": "hard_constraints",
  "schema_version": 1,
  "items": [
    {
      "id": "H-sales-limit",
      "statement": "每种作物按年份、季次分别执行销售量上限",
      "type": "HARD",
      "evidence_level": "problem_explicit",
      "evidence_ref": "2024 C 题题面：每季种植的农作物均在当季销售",
      "granularity_ids": ["sales_limit"],
      "status": "VERIFIED"
    }
  ]
}
```

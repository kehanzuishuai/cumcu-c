# Hard Constraints Contract

```contract-json
{
  "contract_type": "hard_constraints",
  "schema_version": 1,
  "items": [
    {
      "id": "H-time-order",
      "statement": "决策只能使用决策时点之前可得的数据",
      "type": "HARD",
      "evidence_level": "necessary_deduction",
      "evidence_ref": "预测与决策任务的时间先后关系",
      "granularity_ids": ["item_sales_observation", "category_replenishment_decision"],
      "status": "VERIFIED"
    }
  ]
}
```

# Q1-Q3 模型方案

本反例把销售量写成跨季共享的 `D[c,t]`。

```contract-json
{
  "contract_type": "model_plan",
  "schema_version": 1,
  "items": [
    {
      "id": "planting_decision",
      "object": "种植决策",
      "semantic_role": "decision",
      "dimensions": ["plot", "crop", "year", "season"],
      "symbol": "x[p,c,t,s]",
      "used_by": ["Q1", "Q2", "Q3"]
    },
    {
      "id": "sales_limit",
      "object": "销售量上限",
      "semantic_role": "constraint",
      "dimensions": ["crop", "year"],
      "symbol": "D[c,t]",
      "used_by": ["Q1", "Q2", "Q3"]
    }
  ],
  "implemented_hard_constraints": ["H-sales-limit"],
  "implemented_interpretation_decisions": {}
}
```

# Q1-Q3 模型方案

Q1、Q2、Q3 的销售量约束均使用 `D[c,t,s]`，不跨季共享 `D[c,t]`。

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
      "dimensions": ["crop", "year", "season"],
      "symbol": "D[c,t,s]",
      "used_by": ["Q1", "Q2", "Q3"]
    }
  ],
  "implemented_hard_constraints": ["H-sales-limit"],
  "implemented_interpretation_decisions": {}
}
```

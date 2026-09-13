# Model Plan Contract

```contract-json
{
  "contract_type": "model_plan",
  "schema_version": 1,
  "items": [
    {
      "id": "item_sales_observation",
      "object": "单品销量记录",
      "semantic_role": "observation",
      "dimensions": ["item", "date", "time_slot"],
      "symbol": "q[i,d,h]",
      "used_by": ["Q1", "Q2"]
    },
    {
      "id": "category_demand_state",
      "object": "品类需求估计",
      "semantic_role": "state",
      "dimensions": ["category", "date"],
      "symbol": "D[c,d]",
      "used_by": ["Q2", "Q3"]
    },
    {
      "id": "category_replenishment_decision",
      "object": "品类补货决策",
      "semantic_role": "decision",
      "dimensions": ["category", "date"],
      "symbol": "x[c,d]",
      "used_by": ["Q3", "Q4"]
    },
    {
      "id": "result_output",
      "object": "结果表行",
      "semantic_role": "output",
      "dimensions": ["category", "date"],
      "symbol": "result[c,d]",
      "used_by": ["Q3", "Q4"]
    }
  ],
  "implemented_hard_constraints": ["H-time-order"],
  "implemented_interpretation_decisions": {
    "profit_basis": {
      "metric": "net_profit",
      "components": ["revenue", "procurement_cost", "waste_cost"]
    },
    "q2_q3_interface": {
      "payload": "category_demand_estimate",
      "dimensions": ["category", "date"]
    }
  }
}
```

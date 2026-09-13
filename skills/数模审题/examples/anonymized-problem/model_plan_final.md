# Q1-Q3 模型方案声明

```contract-json
{
  "contract_type": "model_plan",
  "schema_version": 1,
  "items": [
    {
      "id": "paired_observation",
      "object": "配对观测",
      "semantic_role": "observation",
      "dimensions": ["zone", "date", "period"],
      "symbol": "delta_T[z,d,p]",
      "used_by": ["Q1", "Q3"]
    },
    {
      "id": "deployment_decision",
      "object": "设施配置决策",
      "semantic_role": "decision",
      "dimensions": ["zone"],
      "symbol": "units[z]",
      "used_by": ["Q2", "Q3"]
    },
    {
      "id": "result_row",
      "object": "结果模板行",
      "semantic_role": "output",
      "dimensions": ["zone"],
      "symbol": "result[z]",
      "used_by": ["Q2", "Q3"]
    }
  ],
  "implemented_hard_constraints": [
    "H-total-units",
    "H-zone-capacity",
    "H-integrality",
    "H-delivery-schema"
  ],
  "implemented_interpretation_decisions": {
    "deployment_objective": {
      "objective": "maximize_total_effect",
      "metric": "temperature_reduction"
    },
    "q1_q2_interface": {
      "payload": "zone_effect_estimate_and_interval",
      "dimensions": ["zone"]
    }
  }
}
```

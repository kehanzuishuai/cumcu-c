# Model Assumptions Contract

```contract-json
{
  "contract_type": "model_assumptions",
  "schema_version": 1,
  "items": [
    {
      "id": "demand_loss_weight",
      "statement": "需求偏差损失权重取 1.0",
      "source": "模型设定；题面未指定",
      "main_value": 1.0,
      "alternative_values": [0.5, 1.5],
      "sensitivity": "比较候选方案排序和关键决策是否稳定",
      "status": "MODEL_ASSUMPTION"
    }
  ]
}
```

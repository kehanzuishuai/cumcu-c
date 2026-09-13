# 题意决定冻结合同

本合同只冻结需要稳定传给模型方案、但不属于粒度、HARD 约束或普通模型假设的关键口径。

```contract-json
{
  "contract_type": "interpretation_decisions",
  "schema_version": 1,
  "items": [
    {
      "id": "deployment_objective",
      "category": "objective_definition",
      "statement": "在设施总量和区域容量约束下最大化总降温效果",
      "value": {
        "objective": "maximize_total_effect",
        "metric": "temperature_reduction"
      },
      "source": "problem_statement.md 问题2的目标与约束",
      "status": "VERIFIED",
      "used_by": ["Q2", "Q3"],
      "freeze_targets": [
        {
          "contract": "model_plan",
          "field": "implemented_interpretation_decisions.deployment_objective"
        }
      ]
    },
    {
      "id": "q1_q2_interface",
      "category": "cross_question_interface",
      "statement": "Q1向Q2传递区域效果估计及其区间",
      "value": {
        "payload": "zone_effect_estimate_and_interval",
        "dimensions": ["zone"]
      },
      "source": "模型接口设计；题面未规定具体中间变量",
      "status": "MODEL_DESIGN",
      "used_by": ["Q1", "Q2", "Q3"],
      "freeze_targets": [
        {
          "contract": "model_plan",
          "field": "implemented_interpretation_decisions.q1_q2_interface"
        }
      ]
    }
  ]
}
```

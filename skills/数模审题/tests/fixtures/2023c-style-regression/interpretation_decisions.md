# Interpretation Decisions Contract

```contract-json
{
  "contract_type": "interpretation_decisions",
  "schema_version": 1,
  "items": [
    {
      "id": "profit_basis",
      "category": "evaluation_basis",
      "statement": "所有候选方案采用同一净收益核算口径",
      "value": {
        "metric": "net_profit",
        "components": ["revenue", "procurement_cost", "waste_cost"]
      },
      "source": "数学实现选择；题目要求比较收益但未规定中间变量名称",
      "status": "MODEL_DESIGN",
      "used_by": ["Q3", "Q4"],
      "freeze_targets": [
        {
          "contract": "model_plan",
          "field": "implemented_interpretation_decisions.profit_basis"
        }
      ]
    },
    {
      "id": "q2_q3_interface",
      "category": "cross_question_interface",
      "statement": "Q2向Q3传递品类需求估计及其日期索引",
      "value": {
        "payload": "category_demand_estimate",
        "dimensions": ["category", "date"]
      },
      "source": "跨问接口设计",
      "status": "MODEL_DESIGN",
      "used_by": ["Q2", "Q3"],
      "freeze_targets": [
        {
          "contract": "model_plan",
          "field": "implemented_interpretation_decisions.q2_q3_interface"
        }
      ]
    }
  ]
}
```

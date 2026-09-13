# 歧义与口径确认

```contract-json
{
  "contract_type": "ambiguity_decisions",
  "schema_version": 1,
  "items": [
    {
      "id": "sales_limit_period",
      "kind": "interpretation_ambiguity",
      "ambiguity_scope": "data_granularity",
      "question": "销售量上限按作物—年还是作物—年—季次？",
      "impact": ["data_granularity", "hard_constraint", "feasible_region", "result"],
      "evidence": [
        {
          "level": "problem_explicit",
          "value": ["crop", "year", "season"],
          "source": "2024 C 题题面：每季种植的农作物均在当季销售"
        }
      ],
      "options": [
        {"value": ["crop", "year", "season"], "consequence": "分季执行销售量上限"},
        {"value": ["crop", "year"], "consequence": "跨季共享上限并改变可行域"}
      ],
      "recommended": ["crop", "year"],
      "decision": ["crop", "year"],
      "approved_by": "user",
      "freeze_targets": [
        {
          "contract": "granularity_contract",
          "id": "sales_limit",
          "field": "dimensions"
        }
      ],
      "status": "APPROVED_BY_USER"
    }
  ]
}
```

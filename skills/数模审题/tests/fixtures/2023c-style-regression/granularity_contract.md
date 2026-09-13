# Granularity Contract

```contract-json
{
  "contract_type": "granularity_contract",
  "schema_version": 1,
  "items": [
    {
      "id": "item_sales_observation",
      "object": "单品销量记录",
      "semantic_role": "observation",
      "dimensions": ["item", "date", "time_slot"],
      "evidence_level": "attachment_explicit",
      "evidence_ref": "合成附件字段：item,date,time_slot,quantity",
      "status": "VERIFIED",
      "mutable": "NO"
    },
    {
      "id": "category_demand_state",
      "object": "品类需求估计",
      "semantic_role": "state",
      "dimensions": ["category", "date"],
      "evidence_level": "necessary_deduction",
      "evidence_ref": "问题2要求形成品类级需求估计",
      "status": "VERIFIED",
      "mutable": "NO"
    },
    {
      "id": "category_replenishment_decision",
      "object": "品类补货决策",
      "semantic_role": "decision",
      "dimensions": ["category", "date"],
      "evidence_level": "problem_explicit",
      "evidence_ref": "合成题面问题3：形成品类级补货方案",
      "status": "VERIFIED",
      "mutable": "NO"
    },
    {
      "id": "result_output",
      "object": "结果表行",
      "semantic_role": "output",
      "dimensions": ["category", "date"],
      "evidence_level": "attachment_explicit",
      "evidence_ref": "合成结果模板：每个品类和日期一行",
      "status": "VERIFIED",
      "mutable": "NO"
    }
  ]
}
```

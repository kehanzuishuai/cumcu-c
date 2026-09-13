# 建模粒度合同

| ID | 对象 | 冻结粒度 | 证据来源 | 状态 | mutable |
| --- | --- | --- | --- | --- | --- |
| paired_observation | 配对观测 | 区域×日期×时段 | 观测附件字段 | VERIFIED | NO |
| deployment_decision | 设施配置决策 | 区域 | 题面与区域附件 | VERIFIED | NO |
| result_row | 结果模板行 | 区域 | 题面交付与模板 | VERIFIED | NO |

```contract-json
{
  "contract_type": "granularity_contract",
  "schema_version": 1,
  "items": [
    {
      "id": "paired_observation",
      "object": "配对观测",
      "semantic_role": "observation",
      "dimensions": ["zone", "date", "period"],
      "evidence_level": "attachment_explicit",
      "evidence_ref": "attachments/observations.csv: zone,date,period,treatment",
      "status": "VERIFIED",
      "mutable": "NO"
    },
    {
      "id": "deployment_decision",
      "object": "设施配置决策",
      "semantic_role": "decision",
      "dimensions": ["zone"],
      "evidence_level": "problem_explicit",
      "evidence_ref": "problem_statement.md 问题2：确定各区域部署数量",
      "status": "VERIFIED",
      "mutable": "NO"
    },
    {
      "id": "result_row",
      "object": "结果模板行",
      "semantic_role": "output",
      "dimensions": ["zone"],
      "evidence_level": "attachment_explicit",
      "evidence_ref": "attachments/result_template.csv: one row per zone",
      "status": "VERIFIED",
      "mutable": "NO"
    }
  ]
}
```

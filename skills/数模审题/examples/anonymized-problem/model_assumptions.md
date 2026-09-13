# 模型假设台账

这些条目是正常建模设定，不属于题意歧义，也不冒充题面事实。

```contract-json
{
  "contract_type": "model_assumptions",
  "schema_version": 1,
  "items": [
    {
      "id": "diminishing_second_unit",
      "statement": "同一区域第二个遮阴设施的边际降温收益不高于第一个",
      "source": "模型结构设定；题面与附件未给出第二个设施的效果函数",
      "main_value": 0.5,
      "alternative_values": [0.0, 1.0],
      "sensitivity": "比较第二设施边际系数为0、0.5和1.0时的配置及目标值",
      "failure_condition": "主配置对边际系数变化高度敏感",
      "status": "MODEL_ASSUMPTION"
    },
    {
      "id": "interval_lower_bound",
      "statement": "区域效果区间足以支持稳健性比较，且保守方案用区间下界代表可接受的悲观效果",
      "source": "Q3稳健优化口径；题面只要求比较保守方案",
      "robustness_test": "将点估计、区间下界和区间宽度惩罚三种口径并列比较",
      "failure_condition": "不同区间构造方法导致关键配置反转",
      "status": "MODEL_ASSUMPTION"
    }
  ]
}
```

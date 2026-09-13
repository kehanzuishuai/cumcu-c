# Q1-Q4模型方案（Final）

状态：当前正式 MAIN。本文档仅登记已经晋级并写入正式结果工作簿的模型。

## Q1：购电—储能词典序线性规划

在144个10分钟时段内，以购电费用最低为首要目标；在费用相同的可行方案中减少储能充放电。模型执行供需平衡、SOC状态方程、容量范围、5000 kW功率上限、日初日末6000 kWh和充放互斥。代码入口为 code/q1_solve.py，正式结果为 results/result1.xlsx、results/q1_detail.csv，验证为 validation/q1_validation.json 与 validation/q1_independent_recompute.json。

## Q2：因果预测驱动的风险修正滚动线性规划

每日0:00在48小时窗口制定正常购电计划，只执行首日；负荷使用同星期线性加权历史预测，光伏使用近五个完整日同槽均值，并采用历史净负荷残差80%分位数修正量。实际执行按10分钟因果储能反馈，剩余缺口紧急购电，SOC跨日连续。代码入口为 code/q2_solve.py，正式结果为 results/result2.xlsx、results/q2_detail.csv，验证为 validation/q2_validation.json、validation/q2_independent_recompute.json 与 validation/result2_workbook_validation.json。

## Q3：日内预报与因果负载反馈驱动的滚动购电调整模型

每日0:00形成原计划；6:00、12:00、18:00仅根据当时最新光伏预报、实际SOC和已发生负荷更新尚未执行时段。负载反馈系数固定为alpha=0.5；最终有效正常购电量相对0:00原计划按冻结结算口径一次结算。代码入口为 code/final_promote_alpha05.py，正式结果为 results/result3.xlsx、results/q3_detail.csv，验证为 validation/q3_validation.json、validation/q3_independent_recompute.json 与 validation/result3_workbook_validation.json。

## Q4：波动电价下的因果滚动购电优化模型

每日0:00利用历史同星期价格构造当天价格预测，计划阶段用预测价优化，交付阶段按实际价格结算。每日计划分支保持Q2信息权限；日内调整分支继承Q3的0/6/12/18更新、alpha=0.5负载反馈和储能执行规则，价格预测仍保持0:00历史日型，不作日内价格修正。代码入口为 code/final_promote_alpha05.py 与 code/freeze_q4.py，正式结果为 results/result4-2.xlsx、results/result4-3.xlsx、results/q4_2_detail.csv、results/q4_3_detail.csv，验证为 validation/q4_2_validation.json、validation/q4_3_validation.json、validation/q4_independent_recompute.json、validation/result4-2_workbook_validation.json 与 validation/result4-3_workbook_validation.json。

## 共同实施口径

所有正式模型使用同一10分钟账本、同一储能物理边界和同一信息截止审计。A01仅为模板时段标签写回风险，已完整披露；不改变任何模型、结果、底账、工作簿或验证文件。

```contract-json
{
  "contract_type": "model_plan",
  "schema_version": 1,
  "items": [
    {
      "id": "G-time-slot",
      "object": "natural-day control interval",
      "semantic_role": "observation",
      "dimensions": [
        "date",
        "ten_minute_slot"
      ],
      "symbol": "t",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-load",
      "object": "load power",
      "semantic_role": "observation",
      "dimensions": [
        "date",
        "ten_minute_slot"
      ],
      "symbol": "L[d,t]",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-pv",
      "object": "photovoltaic power",
      "semantic_role": "observation",
      "dimensions": [
        "date",
        "ten_minute_slot"
      ],
      "symbol": "G[d,t]",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-price",
      "object": "external-grid price",
      "semantic_role": "parameter",
      "dimensions": [
        "date_or_repeated_day",
        "ten_minute_slot"
      ],
      "symbol": "p[d,t]",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-pv-forecast",
      "object": "PV forecast",
      "semantic_role": "observation",
      "dimensions": [
        "issue_date",
        "issue_time",
        "lead_hour"
      ],
      "symbol": "Ghat[r,d,h]",
      "used_by": [
        "Q3",
        "Q4-3"
      ]
    },
    {
      "id": "G-normal-plan",
      "object": "normal purchase plan version",
      "semantic_role": "decision",
      "dimensions": [
        "date",
        "ten_minute_slot",
        "plan_version"
      ],
      "symbol": "q[d,t,v]",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-storage-flow",
      "object": "bus-side storage charge/discharge energy",
      "semantic_role": "decision",
      "dimensions": [
        "date",
        "ten_minute_slot"
      ],
      "symbol": "c[d,t], d[d,t]",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-emergency",
      "object": "emergency purchase energy",
      "semantic_role": "decision",
      "dimensions": [
        "date",
        "ten_minute_slot"
      ],
      "symbol": "e[d,t]",
      "used_by": [
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-soc",
      "object": "battery internal stored energy",
      "semantic_role": "state",
      "dimensions": [
        "date",
        "slot_boundary"
      ],
      "symbol": "S[d,t]",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-daily-output",
      "object": "daily purchase summary",
      "semantic_role": "output",
      "dimensions": [
        "date"
      ],
      "symbol": "EP[d], EQ[d]",
      "used_by": [
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-storage-summary",
      "object": "storage flow summary",
      "semantic_role": "output",
      "dimensions": [
        "date",
        "four_hour_block"
      ],
      "symbol": "C[d,b], D[d,b]",
      "used_by": [
        "Q1",
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    },
    {
      "id": "G-emergency-event",
      "object": "maximal contiguous emergency-purchase event",
      "semantic_role": "output",
      "dimensions": [
        "date",
        "event"
      ],
      "symbol": "E[d,k]",
      "used_by": [
        "Q2",
        "Q3",
        "Q4-2",
        "Q4-3"
      ]
    }
  ],
  "implemented_hard_constraints": [
    "H-supply",
    "H-storage-state",
    "H-soc-range",
    "H-storage-power",
    "H-state-boundaries",
    "H-nonanticipativity",
    "H-action-rights",
    "H-past-lock",
    "H-emergency-price",
    "H-q3-adjustment",
    "H-price-information",
    "H-q4-permissions"
  ],
  "implemented_interpretation_decisions": {
    "D-objective-q1": "min_sum_price_times_normal_purchase",
    "D-objective-q2": "plan_cost_plus_5x_emergency",
    "D-adjustment-cost": "cancelled_quantity_settlement",
    "D-adjustment-baseline": "relative_to_original_plan_final_once",
    "D-price-index": "delivery_interval_price",
    "D-q4-data-permissions": {
      "Q4-2": "no_attachment3",
      "Q4-3": "use_attachment3"
    },
    "D-result-summaries": {
      "EP": "sum_normal_purchase_on_sheet",
      "EQ": "actual_strategy_total_cost"
    },
    "D-q3-adjusted-output": "final_adjusted_absolute_purchase",
    "D-emergency-event": "maximal_contiguous_event",
    "D-other-forecast-analysis": "existing_updates_primary",
    "D-cross-question-ledger": {
      "payload": "ten_minute_causal_ledger",
      "dimensions": [
        "date",
        "ten_minute_slot"
      ]
    }
  }
}
```

# 脱敏端到端示例：城市遮阴设施配置

这是一个完全合成的数学建模赛题示例，不对应任何真实竞赛、学校、城市、队伍或公开数据。它用于演示从原始题面与附件到赛题解读和验收的完整链路。

## 文件

- `problem_statement.md`：合成原题摘要，包含三个编号小问和交付要求。
- `attachments/observations.csv`：分区观测记录，粒度为“区域-日期-时段”。
- `attachments/zones.csv`：区域属性、权重和可部署容量。
- `attachments/result_template.csv`：合成结果模板，固定输出列和小数精度。
- `_archive/interpretation_draft.md`：冻结前草案，仅作历史记录，不进入写作输入。
- `ambiguity_decisions.md`：真正题意歧义合同；本题无真歧义，使用合法空合同。
- `granularity_contract.md`：观测、决策和结果行粒度合同。
- `hard_constraints.md`：总量、容量、整数性和交付格式冻结表。
- `interpretation_decisions.md`：目标定义与 Q1→Q2 跨问接口冻结合同。
- `model_assumptions.md`：递减边际收益与保守区间口径的普通模型假设。
- `model_plan_final.md`：从冻结合同重新生成的 Q1-Q3 对象、语义角色、实际粒度、HARD 约束和题意决定实现声明。
- `interpretation_final.md`：冻结门禁通过后的完整解读。
- `attachment_audit.json`：附件审计结果。
- `acceptance_report.md`：按 `references/acceptance-rubric.md` 的当前适用项完成的人工验收。

## 运行链路

从 skill 根目录运行：

```bash
python scripts/inventory_problem.py examples/anonymized-problem --out /tmp/anonymized-inventory.md
python scripts/validate_interpretation.py \
  examples/anonymized-problem/interpretation_final.md \
  --expected-subproblems 3 \
  --stage final \
  --ambiguities examples/anonymized-problem/ambiguity_decisions.md \
  --granularity-contract examples/anonymized-problem/granularity_contract.md \
  --hard-constraints examples/anonymized-problem/hard_constraints.md \
  --interpretation-decisions examples/anonymized-problem/interpretation_decisions.md \
  --model-assumptions examples/anonymized-problem/model_assumptions.md \
  --model-plan examples/anonymized-problem/model_plan_final.md \
  --json-out /tmp/anonymized-validation.json
python -m unittest discover -s tests -v
```

第一步只读清点题面和附件；第二步同时检查报告结构、六份合同、冻结状态、旧状态残留以及模型方案一致性，并必须返回 `PAPER_READY`；第三步运行全部回归测试。写作只读取两个 final 文件和冻结合同，禁止读取 `_archive/` 或任何 backup/archive 目录。示例尚未运行模型的数值仍标为 `[待计算]`。

## 验收结论

`acceptance_report.md` 按当前适用项逐项给出证据位置和得分。示例要求所有 P0 项为 2 分且得分率不低于 90%；这证明的是解读规格完整，不代表已经完成实际优化求解或数值验证。

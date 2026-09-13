# 脱敏示例验收报告

## 验收范围

对象：`_archive/interpretation_draft.md`、六份结构化合同、`interpretation_final.md`、`model_plan_final.md`、`attachment_audit.json` 以及 `attachments/` 下三份合成材料。

依据：`references/acceptance-rubric.md`。评分采用 `0=缺失或错误`、`1=部分完成`、`2=完整且可回查`。

## 当前适用项逐项评分

| 优先级 | 项目 | 得分 | 证据位置 | 结论 |
| --- | --- | ---: | --- | --- |
| P0 | 小问覆盖 | 2 | `interpretation_final.md` 第 2 节含问题 1-3 规格卡 | 通过 |
| P0 | 证据完整性 | 2 | 第 0、3、5、7 节使用事实、推论、主解释、假设和待计算标签 | 通过 |
| P0 | 证据优先级 | 2 | 无高等级证据冲突；普通模型假设没有冒充题面事实或题意歧义 | 通过 |
| P0 | 约束覆盖 | 2 | 第 2、5、7 节登记总量、容量、单位、时间和精度约束 | 通过 |
| P0 | 分析单位 | 2 | Q1 规定区域-日期-时段配对，Q2/Q3 规定区域级配置 | 通过 |
| P0 | 粒度合同一致性 | 2 | `granularity_contract.md` 与 `model_plan_final.md` 三个稳定 ID 的对象、语义角色和维度完全一致 | 通过 |
| P0 | 交付忠实度 | 2 | 第 0、4、8 节登记模板四列、两位小数和生成文件 | 通过 |
| P0 | 冻结门禁 | 2 | 空歧义合同合法，BLOCKING=0，草案已归档，final 无旧状态且返回 PAPER_READY | 通过 |
| P1 | 模型假设披露 | 2 | `model_assumptions.md` 两项均有来源和验证/挑战路径 | 通过 |
| P1 | 附件审计 | 2 | 第 4 节与 `attachment_audit.json` 覆盖格式、编码、粒度、字段、用途和状态 | 通过 |
| P1 | 模型链 | 2 | 第 6 节给出 Q1-Q3 的主模型、基线、输入、输出和接口 | 通过 |
| P1 | 验证设计 | 2 | 第 7 节包含配对键、约束回放、穷举比较和敏感性门槛 | 通过 |
| P1 | 不确定性/失败 | 2 | 第 2、5、7 节明确区间、不足数据、负效果和无解处理 | 通过 |
| P2 | 论文接口 | 2 | 第 8 节逐问映射结果表、图、结论、文件和摘要 | 通过 |

**实得分：28；当前可评分项满分：28；得分率：100%。所有 P0 项均为 2 分，BLOCKING=0，结构化合同校验通过。**

## 自动检查结果

以下命令从 skill 根目录执行：

```text
python scripts/inventory_problem.py examples/anonymized-problem --out <temporary>/inventory.md
python scripts/validate_interpretation.py examples/anonymized-problem/interpretation_final.md --expected-subproblems 3 --stage final --ambiguities examples/anonymized-problem/ambiguity_decisions.md --granularity-contract examples/anonymized-problem/granularity_contract.md --hard-constraints examples/anonymized-problem/hard_constraints.md --interpretation-decisions examples/anonymized-problem/interpretation_decisions.md --model-assumptions examples/anonymized-problem/model_assumptions.md --model-plan examples/anonymized-problem/model_plan_final.md --json-out <temporary>/validation.json
python -m unittest discover -s tests -v
```

预期结果：清单命令退出码 `0`；final 校验退出码 `0`，状态为 `PAPER_READY`，六份合同全部载入，粒度/语义角色冲突、题意决定传播错误、HARD 遗漏、BLOCKING 和 `STALE_DECISION_STATE` 均为 0；单元测试全部通过。

## 人工复核结论

该示例可以作为公开仓库的端到端演示，但不能被误读为已完成数值求解。`[待计算]` 保留在所有尚未运行模型的位置；真实题目使用时仍需逐页核对原题、逐表核对附件，并在模型运行后填写数值验证结果。

# 数模审题

一个面向 Codex 的数学建模 C 题全技术链 skill。它先把原始题面和附件翻译成可回查的建模规格；真正歧义确认后，继续完成模型选择、编程求解、验证、稳健性和结果冻结，而不是堆砌算法名称或虚构数值结果。

## 能做什么

- 完整拆解单题：任务链、小问输入输出、约束、歧义、附件结构、模型接口和验证方案。
- 复核已有解读，标出遗漏、口径变化、证据不足和需要重算的部分。
- 根据六维结构卡缩小模型候选，完成朴素基线、必要候选、主模型、代码/求解器、验证和灵敏度/稳健性。
- 将模型与实际结果收束为论文可读取的冻结接口，明确跨问字段、失败输出和交付映射。

## 目录结构

```text
数模审题/
├── SKILL.md                         # skill 入口和路由规则
├── agents/openai.yaml               # Codex UI 元数据
├── assets/interpretation-report-template.md
├── assets/ambiguity-confirmation-template.md
├── assets/model-assumptions-template.md
├── references/                      # 方法论、输出结构、题型检查和验收量表
├── scripts/inventory_problem.py     # 只读材料清单
├── scripts/validate_interpretation.py # 报告结构预检
├── tests/                            # 合成夹具和脚本测试
├── examples/anonymized-problem/      # 可公开发布的端到端脱敏示例
├── requirements.txt                  # 可选的 PDF 审计依赖
├── CONTRIBUTING.md
└── LICENSE
```

## 使用

将本目录放入 Codex 可发现的 skills 目录后，可显式调用：

```text
$数模审题 解读指定年份的数学建模竞赛 C 题及其全部附件，生成完整报告。
```

也可以直接描述单道 C 题的审题目标，skill 会按所需深度处理：

- `full`：从单题完整解读开始；有真正歧义时先等待确认，解除后继续建模求解；
- `re-review`：复核已有解读；
- `paper-ready`：冻结论文级建模蓝图并继续完成实际求解、验证和结果交接。

本 Skill 只处理题号已经确定的一道 C 题。

首次独立解读只使用原题和附件。只有复核已有解读或用户明确要求对照时，才读取优秀论文或旧解读。

## 安装

### 使用 skill-installer

在 Codex 中输入：

$skill-installer 请从以下 GitHub 仓库安装数模审题：
https://github.com/zhoufz021/interpret-modeling-problems

### 手动安装

将仓库下载并解压到：

Windows:
%USERPROFILE%\.codex\skills\数模审题

macOS/Linux:
$HOME/.codex/skills/数模审题

安装后调用：

$数模审题 解读指定赛题及附件。

如果没有立即显示，请重新启动 Codex。

### 发布形态

本仓库当前提供的是 **standalone Codex skill**，可通过 `skill-installer` 或手动复制到 skills 目录后使用。它不是插件包，因此当前不需要 `.codex-plugin/plugin.json`。如果未来需要接入公共插件目录，再单独增加 plugin 包装层。

## 依赖与脚本

- Codex skill 运行时：需要支持标准 skill 目录结构的 Codex 环境。
- Python：脚本兼容 Python 3.9 及以上版本。
- `pypdf`：可选。安装后 `inventory_problem.py` 能读取 PDF 页数；未安装时仍可生成其余清单。

从 skill 目录运行：

```bash
python scripts/inventory_problem.py /path/to/problem --out /tmp/problem-inventory.md
python scripts/validate_interpretation.py /tmp/赛题解读.md --expected-subproblems 4
python -m unittest discover -s tests -v
```

两个脚本都是只读或生成新文件，不会修改题目原始材料。结构预检不能替代逐页、逐表和语义复核。

## 端到端示例

[`examples/anonymized-problem/`](examples/anonymized-problem/) 是一套完全合成的三问赛题，包含归档 draft、六份结构化冻结合同、重新生成的 final、附件审计和动态验收报告。它与 2024 C 回归夹具题型不同，用来验证通用题也能走完整冻结链。可直接运行：

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
```

预期状态为 `PAPER_READY`。示例验收采用当前量表动态满分：所有 P0 项必须为 2 分、总得分率不低于 90%、不存在 BLOCKING 且结构化合同校验通过。它只测试“题意与建模合同允许进入正式求解”；其中的 `[待计算]` 不代表模型已经完成。真实比赛任务仍由本 Skill 继续生成代码、结果和验证产物，写作 Skill 不接收只有结构校验、没有实际结果的交接。

## 输出约定

完整解读默认包含：

1. `赛题解读_draft.md` 与仅含真正题意歧义的 `歧义与口径确认.md`；
2. `附件审计.json`；
3. 固定生成 `题意决定冻结合同.md`；没有关键非粒度决定时使用空的 `items: []` 合同；
4. 固定生成 `模型假设台账.md`；没有普通模型假设时使用空的 `items: []` 合同；
5. `验收报告.md`。

只有高等级证据冲突已消除、`BLOCKING=0`、粒度/HARD/题意决定/模型假设合同完整、模型方案一致性校验通过后，才重新生成 `赛题解读_final.md` 与 `Q1-QN模型方案_final.md`。旧 `*_draft.md` 只可移入 `_archive/`，不得直接覆盖；任何 backup 或其他 archive 目录必须移出正式交接目录。final 报告、模型方案或 Markdown 合同若残留待确认、草稿、待冻结或旧 A/B 口径，validator 报 `STALE_DECISION_STATE` 并阻止 `PAPER_READY`。

写作阶段只读取 `*_final.md` 和当前冻结合同，不读取任何 backup/archive 目录（包括 `_archive/`）、`*_draft.md` 或无 `_final` 后缀的旧模型方案，防止第一阶段题意污染正文。

报告中的关键判断应带有 `[题面事实]`、`[附件事实]`、`[必要推论]`、`[主解释]`、`[可检验假设]`、`[备选解释]` 或 `[待计算]` 标签，并给出文件、页码、工作表、字段或模板名称等回查位置。

## 发布边界

本仓库只分发 skill、模板、方法论和合成测试，不包含竞赛原题、附件、优秀论文、个人数据或任何生成报告。使用者应自行确认输入材料的版权、隐私和授权范围；不要把真实题目材料提交到公开仓库。

## 贡献前检查

提交修改前，请运行：

```bash
python -m unittest discover -s tests -v
python scripts/validate_interpretation.py tests/fixtures/minimal_report.md --expected-subproblems 1
```

并确认：没有未完成占位符、没有固定本机路径、没有把未经运行的候选模型写成结果，也没有把某一年题目的特殊口径扩张成普遍规则。


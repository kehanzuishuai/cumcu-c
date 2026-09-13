---
name: cumcm-paper-freeze
description: 在 CUMCM C 题论文写作完成、最终图表已插入后，把唯一最终 PDF、论文源文件、代码、结果、图表、支撑材料和 AI 声明复制到全新的 paper_final 目录，校验上游 manifest 与全部文件 SHA-256，并生成供 FULL 审核读取的 audit_manifest.json。只做组装、校验和冻结；不得改写论文、重算模型、重画图或替代审核。
---

# CUMCM 最终成稿冻结

本 Skill 位于“队员手动插入最终图表并导出唯一成稿 → `paper_final` → FULL 审核”之间。通用规则以 `../_shared/cumcm/C题规范.md` 为唯一 S1 规范源，跨 Skill 字段以 `../_shared/cumcm/interfaces.md` 为准。

## 入口

只在以下条件同时满足时运行：

- `paper_ready_manifest.json` 为 `PAPER_READY`，两个 final 与五份合同的 hash 仍一致；
- `figure_manifest.json` 为 `FIGURES_READY`，全部图/流程图为 `FINAL`；普通图的 Brief、数据、脚本、输出和 QA 无旧状态，流程图的 Brief、可编辑 PPT 源文件、输出和 QA 无旧状态，生成脚本仅在实际使用时核验；
- 已锁定唯一最终 PDF 和论文源文件；
- `freeze_plan.json` 的 `blockers` 为空，并列齐代码、结果、图表、支撑材料和 AI 声明。

字段和最小样例见 `references/freeze-contract.md`。缺项或 hash 失配时停止并返回对应上游，不自行修内容。

## 执行

```bash
python <skill-dir>/scripts/freeze_submission.py <project-root> \
  --plan <project-root>/freeze_plan.json \
  --destination paper_final
```

脚本先完成只读校验，再把所有列明文件和两个上游 manifest 复制到全新目录，保持项目内相对路径；目标目录已存在时拒绝覆盖。最后在冻结目录根部生成 `audit_manifest.json`。

## 不可越界

- 不编辑正文、源文件、图、表、代码或结果；
- 不重新执行模型或绘图；
- 不把旧版本、草稿、backup/archive 自动混入冻结包；
- 不生成贯穿流程的 AI 日志；只冻结当届规则需要的最终 AI 声明材料；
- 不把 `frozen: true` 当作审核通过，它只表示版本已锁定且 hash 可核验。

## 输出

输出是一个新的 `paper_final`（或用户指定的新版本目录），其中含最终文件、`paper_ready_manifest.json`、`figure_manifest.json` 与 `audit_manifest.json`。之后 FULL 审核只读该目录；PAPER_ONLY、VISUAL_ONLY、RECHECK 的既有职责不由本 Skill 改写。

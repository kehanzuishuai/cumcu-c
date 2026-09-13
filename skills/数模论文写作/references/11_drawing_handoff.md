# 写作到绘图/流程图交接

本页只解释跨 Skill 状态，不改变写作或绘图内部方法。完整字段以 `../../_shared/cumcm/interfaces.md` 为准。

## 正常交接

- Figure Brief 必须给出稳定 `figure_id`、Claim、证据结构、统计口径、字段、单位、坐标/分组语义、合同 ID、正文源文件及前后锚点、真实数据路径与 SHA-256；只有锚点按顺序存在于该版正文、全部字段非空且与资产记录一致后，才用 `READY_FOR_DRAWING`。
- Flowchart Brief 必须给出稳定节点 ID、节点角色、边方向、跨问接口、阅读顺序、正文源文件及前后锚点；写作阶段用 `LOGIC_FIXED`，正式插入前由队员把 `human_approved` 置为 `true`。
- 写作给出的图型候选不覆盖绘图 Skill 的选图、信息密度、证据丰富度、组合和 A4 Gate。
- 普通图表交给 `cumcm-c-paper-figure`；流程图只交给 `unflatten-ppt`，普通绘图 Skill 不绘制流程图。

## 队员手动插图

普通图表和流程图完成后，由队员在比赛时手动插入论文源文件，核对图号、题注、正文引用、前后叙事、实际宽度和分页，再导出唯一最终 PDF。Skill 不自动插图；手动插图后修改的是最终论文源文件，Figure/Flowchart Brief 中的 `paper_source` hash 只保留绘制时正文上下文快照。

## RESAMPLE 回退

绘图返回共享接口定义的 `RESAMPLE_REQUIRED` 记录后，该图及旧 `figure_manifest.json` 立即失效。“数模审题”根据 `reason_codes`、`required_evidence` 和 `affected_files` 重新计算、求解、验证并冻结结果；写作阶段随后只依据新冻结结果更新结果表、正文、摘要、数据 SHA-256、Brief 中图前/图后文字和 `revision`，再把状态恢复为 `READY_FOR_DRAWING`。若补算触及题意、HARD 或粒度，仍按原歧义与合同门禁重新确认；写作 Skill 不自行补算或更换模型。

禁止用插值、复制、抖动、静默重算或只换图型绕过 `RESAMPLE`，也禁止新图与旧正文数字并存。

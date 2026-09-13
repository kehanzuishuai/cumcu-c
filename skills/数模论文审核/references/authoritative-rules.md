# C 题审核规则权威入口

## 优先级

1. 当届全国组委会或赛区正式规则为 S0；
2. `../../_shared/cumcm/C题规范.md` 为唯一 S1 总标准；
3. 本审核 Skill 的 checklist、脚本和视觉 reference 只定义核验方法，不得覆盖 S0/S1；
4. 优秀论文、教师经验和其他 Skill 只能补充证据，不得单独制造 P0。

无法确认当届规则时标记 `UNVERIFIED_OFFICIAL_RULE`。共享规范的 `standard_version` 与 SHA-256 应写入冻结清单；发现版本或 hash 不一致时，不得把审查结果解释为对另一版本规范的结论。

## 使用方法

- FULL 审核先读取冻结包的 `audit_manifest.json`，再读取唯一 S1 总标准及本 Skill 的专题检查文件。
- PAPER_ONLY、VISUAL_ONLY、RECHECK 保留原有审查职责；其中 FULL/RECHECK 按共享冻结接口读取成稿包，PAPER_ONLY 不执行冻结门禁。
- 自动脚本只确认文件、hash、结构、数值或日志等确定性事实；语义、模型合理性和视觉判断仍按原审核流程执行。

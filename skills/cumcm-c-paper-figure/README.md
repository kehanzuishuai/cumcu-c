# CUMCM C题论文图表 Skill v1.4.6

核心文件：`SKILL.md`

用途：生成全国大学生数学建模竞赛论文中的预测、优化、评价、机理分析、分类、聚类、地理空间、生产调度、灵敏度与风险图表；流程图交给 `unflatten-ppt`。

设计依据：用户提供的 2021—2025 C题优秀论文资料，重点参考 2023、2025，尤其 2025 官方展示 C023/C132。

说明：当前来源包没有 2024 C题优秀论文全文，Skill 不虚构 2024 C 的视觉风格证据。

本版融合 `figures4papers` 的出版级几何、语义色板、灰度可辨编码、统一渲染层与矢量导出，但按 CUMCM A4 版面重新收敛，不复制其超宽画布、超大字体、粗黑柱边或截断柱轴。

新增内容：

- `Claim → Evidence → Chart Type` 选型门禁；
- 柱宽与组间留白规则；
- 真正的均值 + VaR + CVaR 下尾样本分布图；
- 只有汇总指标时的风险森林图；
- `scripts/cumcm_figure_style.py` 统一渲染层；
- `scripts/render_a4_preview.py` 最终论文宽度预览；
- `Render → Open → Visual Audit → Revise` 发布门禁。

v1.2.0 小范围新增：

- `Visual Information Density Gate`，在选图后检查有效点数、样本数、区间宽度/坐标跨度、数据占轴比例和边界标注；
- 连续权重曲线不足时返回 `RESAMPLE`，只生成待重新求解的采样位置，不插值伪造 y；
- 少量汇总指标冒充分布时返回 `RECHART`；
- 森林图区间退化成点时返回 `RESCALE`，并提供聚焦坐标与零基准图外说明；
- 增加边界安全标注和 fig6/fig7/fig10 型回归测试。

v1.3.0 小范围新增：

- `Evidence Richness Gate`：根据证据关系返回 `PASS / COMPOSE_LAYER / COMPOSE_PANEL / KEEP_SEPARATE`；
- 允许“分布 + KDE + 阈值 + 风险区域”等同一 Claim 的互补证据组合，不把复合图设为默认目标；
- `Figure Portfolio Gate`：全文图型家族过度重复且跨越不同证据结构时返回 `REVIEW`；
- 重复图型若由相同 Evidence 支撑可直接保留，禁止为多样性强行换图；
- 新增对应接口、参考说明与回归测试。

v1.4.0 小范围新增：

- Figure Portfolio Gate 增加连续多系列折线/柱复核，但不设多样性配额；
- 2023 C 题式边界：补货时间轨迹保留折线，品类 × 日期定价矩阵优先热力图；
- 新增 `Advanced Figure Candidate Gate`，按证据合同候选 Ridgeline、Raincloud、Bubble Matrix、Hexbin/2D KDE、Parallel Coordinates、Network、Slope/Dumbbell、Bump、Ternary、SHAP 与受限 3D Response Surface；
- 高级图只有在结构适配并带来实质增益时启用；完整规则和 `figure_*` 案例提炼放入 `references/` 按需读取；
- 现有选图、语义配色、信息密度和 A4 视觉 QA 流程保持不变。

v1.4.1 小范围修正：

- 固定决策顺序：`证据匹配 > 信息表达 > 可读性 > 全文多样性 > 高级感`；
- Portfolio Gate 不再把 heatmap 当作折线/柱状图的默认整改项，并同样检查 heatmap 跨 Evidence 重复；
- 每张图都运行轻量 Advanced Figure Candidate Gate，无候选、无信息增益或 A4 可读性下降时保留最合适的基础图；
- 增加常用 Evidence 别名，提高真实任务中的高级候选召回；
- 保留现有选图、语义配色、信息密度和最终视觉 QA 流程。

v1.4.2 小范围新增：

- Advanced Figure Candidate Gate 增加 Mosaic/Association Plot、标准化残差气泡图、Parallel Sets/Alluvial 与 Marimekko；
- 四类候选分别绑定列联关联、残差贡献、类别映射/迁移、总量 + 内部组成，只有比 bar/dot/heatmap 多表达一个真实信息维度时才启用，否则 `KEEP_STANDARD`；
- 新增满幅组成图边界 QA：100% 比例轴零 margin 且贴合理论边界，Marimekko 同时贴合真实累计总量轴；
- 边界标签使用向图内 annotation，不通过扩大坐标范围制造白带；
- 继续保留现有 Claim → Evidence → Chart Type、Portfolio Gate、语义配色、信息密度和最终 QA 主流程。

v1.4.3 小范围新增：

- 参考 BioLadder 的图型组织与用户给出的候选清单，在现有 Advanced Figure Candidate Gate 补入 UpSet、Corrgram/Pairwise Relationship Matrix、Chord、Lollipop 与 Bidirectional/Diverging Bar；
- 五类图分别绑定多集合交集、4–8 变量成对关系、带权类别关联、有序中等类别比较和围绕真实零点的正负效应；证据合同不完整时均 `KEEP_STANDARD`；
- Lollipop 允许由已确认的 A4 可读性增益进入候选，其余仍要求增加真实信息维度；
- 新图型映射回现有 dot、network、pairwise-matrix、set-intersection 等 Portfolio 家族，不绕开全文复核；
- 不引入 BioLadder 在线依赖、生物学专用标签或默认彩虹配色，现有选图、语义配色、信息密度与最终 QA 不变。

v1.4.4 behavior-preserving 轻量化重构：

- 主 `SKILL.md` 从 1564 行收敛为 358 行总控路由器，只保留 Figure Brief、Claim → Evidence → Chart Type、Gate 顺序、按需读取、核心工作流与输出要求；
- 新增 `references/task-patterns.md`，承接预测、优化、评价、统计、分类、聚类、风险、灵敏度、表格与任务最小图集；流程图已路由到 `unflatten-ppt`；
- 新增 `references/publication-style.md`，承接字体、语义配色、线宽、柱宽、坐标、图例、multi-panel、Matplotlib/MATLAB 与 publication rendering；
- `references/visual-audit.md` 承接 18 类常见视觉错误和详细 Final QA；其余 reference 继续保持原职责；
- `scripts/` 两个运行文件字节级不变；新增 2022/2023/2024/2025 golden-case 回归，确保推荐图型、Gate 状态和最终决策保持 v1.4.3 行为。

v1.4.6 轻量增量：

- 在既有 `chart-selection`、`task-patterns` 与 `visual-audit` 中补入地理空间 Map 和生产调度 Scheduling/Gantt；
- Map 按点位、区域、比例符号、路线/流向分流，并检查 CRS、边界/连接键及率/密度口径；
- Gantt 只接受真实任务时段与资源占用，并回查 duration、no-overlap、precedence、release/due、makespan 和求解状态；
- 与 heatmap、network、Sankey/alluvial、优化收敛图和流程图明确区分；原 Gate 与运行脚本不变。

测试：`python -m unittest discover -s tests -v`

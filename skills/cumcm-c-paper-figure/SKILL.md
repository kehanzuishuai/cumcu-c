---
name: cumcm-c-paper-figure
description: 面向全国大学生数学建模竞赛（高教社杯/CUMCM）论文的科研图表生成 Skill。以“Claim → Evidence → Chart Type”约束图型选择，并检查正文适配、信息密度、互补证据、全文图型组合及证据支持的高级候选；覆盖预测、优化、评价、机理/统计分析、分类、聚类、地理空间、生产调度、不确定性、灵敏度与风险，不绘制流程图，也不复刻任何参考原图。
metadata:
  version: "1.4.6"
---

# CUMCM 国赛论文图表总控路由器

## 0. Skill 定位

将模型结论转化为**评委扫一眼能看懂、细看能核验**的论文证据。目标不是海报感，也不是高级图数量。

核心原则：

> **一张图回答一个明确问题；颜色服务区分，线型服务逻辑，标注服务结论，图题服务论文。**

所有决策严格按以下顺序，后一项不得推翻前一项：

> **证据匹配 > 信息表达 > 可读性 > 全文多样性 > 高级感**

柱状图、折线图、点图和热力图都只是工具。问题是机械套图，不是基础图本身；不得从“无脑折线”转成“无脑热力图”。

本 Skill 只复用优秀论文和外部科研绘图资源的设计范式、信息组织与视觉习惯，不复刻具体原图、布局细节或数据形状。

通用 C 题规则以 `../_shared/cumcm/C题规范.md` 为唯一 S1 规范源；写作交接、RESAMPLE 与 manifest 字段见 `../_shared/cumcm/interfaces.md`，不改变下述选图和 Gate 逻辑。

流程图不属于本 Skill：收到 `brief_type: flowchart` 时路由到 `unflatten-ppt`，不得用 Matplotlib、Graphviz 或本 Skill 的普通绘图流程代画。`write_figure_manifest.py` 可以汇总并核验专用流程图 Skill 已交付的资产记录，这不构成流程图制作职责。

## 1. 不可变发布规则

1. 先写 Claim，再确认 Evidence，最后选 Chart Type。
2. 柱状图只服务离散类别的精确大小比较；时间、连续参数、分布、关系、区间和风险收益不得退化为柱。
3. 图名必须与证据对象一致；没有样本、模拟或重采样结果，不得称为“分布”。
4. 每张图选出基础图后都运行 Advanced Figure Candidate Gate；高级候选不由 Portfolio 多样性触发。
5. 图型正确后必须运行 Visual Information Density Gate；未完成 `RESAMPLE / RESCALE / RECHART` 不进入发布。
6. 同一 Claim 的互补证据可分层/分面；多 Claim、不同对象、独立或冗余证据不得硬拼。
7. 全文主要图完成后运行 Figure Portfolio Gate；`REVIEW` 只要求复核，不强制换图。
8. heatmap 只承担真实二维矩阵的单元格模式，不是重复折线/柱的默认替代。
9. 同一语义全篇固定同色；主方案、对照、基准、改进、风险和不确定性不得漂移。
10. 代码运行成功不等于成图完成；必须执行 `Render → Open → Visual Audit → Revise` 才能交付 `FINAL`。

若这些规则与旧模板冲突，以本节和确定性脚本为准。

## 2. 来源边界

当前样本包括 2021 C066/C085/C169/C283、2022 C155、2023 C050/C126/C228/C235、2025 C1–C4 及 2025 官方展示 C023/C132。

- 2025 官方展示和 2025/2023 样本用于提炼近年证据组织；
- 2022/2021 只吸收简洁、直接、信息优先的表达；
- 当前来源包没有 2024 C 题优秀论文全文。2024 只用于理解多期规划、不确定性、风险与相关性任务结构，不虚构其固定字体或配色习惯；
- `figures4papers` 与 BioLadder 只提供可迁移的 publication-style、multi-panel、视觉编码与候选组织思想，不成为运行依赖。
- 老师推荐的 ChiPlot、Flourish 与 Chart-tool 只作为图型发现和界面组织参考，不成为运行依赖；Map 与 Scheduling/Gantt 仍由真实证据结构、静态论文适配和本 Skill 的 Gate 决定。

## 3. Reference 按需读取路由

主文件只负责路由。不要一次加载全部 reference；先根据 Figure Brief 和当前阶段读取最少集合。

| Reference | 何时读取 | 唯一职责 |
|---|---|---|
| [chart-selection.md](references/chart-selection.md) | 选择或复核基础图 | `Claim → Evidence → Chart Type`、柱状图门禁、下尾证据边界 |
| [task-patterns.md](references/task-patterns.md) | 已识别预测/优化/评价/统计/分类/聚类/地理空间/生产调度/风险/灵敏度等普通图表任务 | 各任务详细图型、证据增强、最小图集与图后分析 |
| [advanced-figure-candidates.md](references/advanced-figure-candidates.md) | 轻量接口返回候选或边界不明确 | 高级候选证据合同、KEEP_STANDARD 条件与 A4 比较 |
| [visual-information-density.md](references/visual-information-density.md) | 基础图确定、正式编码前，或成图空/弱/看不清 | `PASS / RESAMPLE / RESCALE / RECHART` 与 fig6/7/10 型诊断 |
| [evidence-richness-portfolio.md](references/evidence-richness-portfolio.md) | 单图密度通过后，或全文主要图完成后 | Evidence Richness 与 Figure Portfolio，不设图型配额 |
| [publication-style.md](references/publication-style.md) | 图型与 Gate 决定已冻结，准备编码/统一视觉 | 字体、语义配色、线宽、柱宽、轴、图例、multi-panel 与渲染层 |
| [visual-audit.md](references/visual-audit.md) | 成图已生成、准备交付或插入论文 | A4 视觉闭环、常见错误、阻断条件与详细 Final QA |
| [figures4papers-fusion.md](references/figures4papers-fusion.md) | 维护视觉系统、复杂多面板或解释来源 | 外部 publication-style 的吸收/拒绝边界与真实 `figure_*` 案例 |

脚本职责：

- [cumcm_figure_style.py](scripts/cumcm_figure_style.py)：确定性 Gate、语义色板、统一渲染、风险图与 QA 辅助；
- [render_a4_preview.py](scripts/render_a4_preview.py)：按论文实际宽度生成 A4 预览；
- [write_figure_manifest.py](scripts/write_figure_manifest.py)：仅在现有 Gate 全部通过后核验来源 hash 并生成 `figure_manifest.json`。

## 4. Figure Brief

正式论文流水线优先直接读取写作输出的 `figure_briefs_all.md`：状态必须为 `READY_FOR_DRAWING`，上游 manifest、正文源文件与前后锚点、合同 ID、数据字段/单位/坐标语义、数据路径和 SHA-256 必须匹配共享接口。缺字段、空壳或旧 hash 时返回写作补齐，不猜正文或数据。独立画图任务仍可在内部建立以下最小 Figure Brief：

```text
Figure ID:
Task Type:
Claim: 一句话、一个主结论
Evidence Object: 样本 / 时间序列 / 成对观测 / 区间 / 矩阵 / 离散类别 / 网络 / 地理要素 / 排程时段 / 组成
Evidence Roles: 原始数据 / 趋势 / 区间 / 阈值 / 基准 / 风险区域 / 决策点
Structure: 时间连续性、参数连续性、类别大小、二维单元格、分布形态、成对变化等
Standard Chart Candidate:
Advanced Candidate Inputs: 原始样本、边权、SHAP、响应网格等是否真实存在
Scale & Density: 点数、样本数、区间/轴跨度、数据占轴比、边界标注
Semantic Roles: 主方案、对照、基准、改进、风险、不确定性
Final Width: full / half / custom
Outputs: PDF / PNG / code / caption / analysis
```

若 Claim 与 Evidence 不能各用一句话写清，先不要画。Brief 只提供证据与交接，不覆盖本 Skill 的 Chart Type、Advanced、Density、Richness、Portfolio 或 A4 判断。

## 5. Claim → Evidence → Chart Type 主链

```text
Claim（要证明什么）
  ↓
Evidence（真实支撑对象与结构）
  ↓
Chart Type（最直接的视觉编码）
```

不得从“代码最容易画什么”“上一问用了什么图”或“全文缺什么图型”反推 Chart Type。

### 5.1 基础分流

```text
随时间变化                 → line / prediction interval / small multiples
连续参数变化               → sensitivity curve / 2D heatmap or contour
两变量关系                 → scatter + fit/LOESS + CI
样本分布或尾部             → histogram + KDE / ECDF / quantile band
组间样本差异               → box / dot + interval / violin（谨慎）
多变量相关结构             → correlation/cluster heatmap
模型预测                   → actual–predicted + boundary + interval + residual
评价与排序                 → horizontal bar/dot + stability
风险—收益折中              → Pareto / sample distribution / ECDF
效应或估计区间             → forest / point-interval
离散类别精确大小           → bar/dot（先过柱状图门禁）
多期多对象决策             → trajectory 用 line；cell pattern 用 matrix/heatmap
地理位置、区域差异或空间流动 → point / choropleth / proportional-symbol / route-flow map
生产、机器或任务排程         → resource-row Gantt / scheduling timeline
分类性能                   → confusion matrix / ROC / PR / threshold curve
聚类                       → PCA / silhouette / dendrogram / profile matrix
不确定性                   → distribution / interval band / ECDF / convergence
生存或达标时点             → KM + CI / forest / residual check
```

详细矩阵与误用见 `chart-selection.md`，具体任务规则见 `task-patterns.md`。

### 5.2 line / bar / heatmap 不可互换

- 时间、距离、阈值、权重等具有连续或自然顺序时，趋势证据保留 line；
- 离散类别的精确大小比较可用 bar/dot；bar 必须从 0 起，且类别数量与标签适合正文；
- 对象 × 时间、对象 × 指标等真实二维矩阵，且单元格模式是主证据时才用 heatmap；
- 多系列 line 重复不自动改 heatmap；bar 重复不自动改 heatmap；heatmap 重复同样接受 Portfolio 复核；
- 图型重复若由证据结构重复造成，可保留并设置 `selection_confirmed=True`。

2023 式边界：补货量随日期变化的主证据是轨迹，保留 line；品类 × 日期定价的主证据是二维矩阵，使用 heatmap。差异来自 Evidence，不来自避重。

### 5.3 分布与汇总指标

“分布”必须有原始、Monte Carlo、Bootstrap、重复运行样本或可恢复经验分布。均值、分位数、CVaR、极值等少量统计量不是样本；无样本时使用 forest/point-interval/table，并改名“风险指标比较”或“收益区间比较”。

### 5.4 核心 Evidence 合同速查

以下只确定证据边界，不替代 `chart-selection.md` 或任务 reference。

#### 时间与连续参数

- 时间序列的顺序、相位、拐点和预测分界由 x 位置表达，首选 line；
- 多对象时间轨迹若相互遮挡，先 small multiples，不先改 heatmap；
- 对象 × 时间单元格模式若是 Claim，才使用 matrix/heatmap；
- 连续参数扫描必须有足够真实计算点；少于 5 个通常 `RESAMPLE` 或降级为离散情景比较；
- 双连续参数默认 2D heatmap/contour；3D 只走现有响应面窄门槛。

#### 样本、关系与区间

- 样本形态、偏态、多峰和尾部必须由观测/模拟样本支撑；
- 两变量关系必须有成对观测，首选 scatter + fit/LOESS + CI；
- 只有相关系数矩阵时使用 correlation heatmap；需要同时看边际分布和两两形态时才检查 Corrgram；
- 点估计 + CI/分位区间使用 forest/point-interval；
- 区间在当前轴跨度下不可见时诚实聚焦，并说明图外基准，不改成截断柱。

#### 离散类别与排名

- 少量离散类别的大小比较使用 bar/dot；
- 类别长或需要排序时优先 horizontal bar/dot；
- 约 10–30 个有序类别只有在 Lollipop 确实减轻阅读负担时才候选；
- 排名稳定性需要扰动、重复方法或时序证据，不能只用静态雷达；
- 雷达继续受维度/对象数量窄门槛约束，不能承担精确排名。

#### 分类、组成与类别结构

- 分类性能由混淆计数、概率或阈值扫描支撑，不以单一 Accuracy 柱结束；
- 组成图要求部分之和闭合为整体；独立指标不得堆叠；
- Mosaic 需要真实列联频数与边际/联合结构；残差 Bubble 需要已计算标准化残差；
- Alluvial 需要可追踪的类别映射和真实流权；Marimekko 同时需要总量与闭合内部组成；
- UpSet 需要对象级集合成员关系；Chord 需要真实边及关系权重；证据缺一即 `KEEP_STANDARD`。

#### 风险与不确定性

- 风险—收益折中由多方案点集、样本分布或区间证据表达，不用两根柱概括；
- 下尾分布至少检查经验样本、均值、VaR、CVaR 和尾部区域；
- KDE 是否出现由样本量与数据性质决定，不作为装饰层；
- 只有汇总风险统计量时使用风险 forest/point-interval/table；
- Monte Carlo 尾部样本不足时增加真实模拟或报告不确定性，不平滑伪造。

#### 地理空间

- 只有地理位置、边界或空间路径本身支撑 Claim 时才使用 Map；只有距离矩阵或拓扑关系时用 matrix/network；
- 点位、区域、总量和流向分别进入 point、choropleth、proportional-symbol 与 route/flow map，不用同一种地图替代；
- 正式绘制前必须核对坐标参考系与经纬度顺序、边界来源/版本、区域连接键、聚合层级及单位；详细门禁见 `chart-selection.md` 与 `task-patterns.md`。

#### 生产调度与排程

- 真正的 Gantt 必须有任务/工序、机器/资源、`start`、`end` 或 `duration`；对象 × 时间数值矩阵仍按 heatmap 处理；
- x 轴表达时间，行表达机器/资源，条段表达任务占用区间；颜色只编码作业/订单或必要状态；
- 发布前必须回查工期恒等式、同资源不重叠、作业内 precedence、释放/交期及 makespan 等模型约束；Gantt 不是流程图、Sankey/alluvial 或算法收敛图。

#### 改进、组合与全文

- baseline/improved、before/after 必须同口径、同尺度或明确差值；
- 原始数据、趋势、区间、阈值和风险区域只有共同核验同一 Claim 才能复合；
- 不同量纲使用对齐面板，不用双 Y 轴硬拼；
- 多个弱证据不因放进 2×2 就变强；无核验职责的面板应删减；
- 全文多样性只发现机械套图，不能推翻单图的证据、信息与可读性决定。

### 5.5 图与表的边界

- 图用于趋势、关系、比较、稳定性和不确定性；
- 表用于精确数字、最终方案、参数和完整统计量；
- 只有 3–5 个无关系、区间或分布的汇总值时，先考虑三线表或正文数字；
- 不为“每问有图”把弱证据图形化，也不为“图少”启用高级候选。

## 6. Gate 执行顺序

### Gate 0：Figure Brief 完整性

确认 Claim、Evidence Object、结构、标准图候选、最终尺寸与输出。证据不足时先补数据、改表或停止，不通过视觉设计掩盖。

### Gate 1：标准图选择

读取 `chart-selection.md`，选择最少且最匹配的基础图。若是具体任务，再只读取 `task-patterns.md` 的对应章节。

柱状图只有同时满足以下条件才可选：

1. 横轴是离散类别而非时间/连续参数；
2. Claim 是大小比较而非分布、关系、区间或轨迹；
3. 类别与标签适合正文；
4. 从 0 起不会破坏主要比较；
5. 多系列仍有清楚组间空白。

### Gate 2：Advanced Figure Candidate Gate

每张图都调用 `advanced_figure_candidate_gate()`：

- `KEEP_STANDARD`：无结构候选、无信息/可读性增益或 A4 不可读，保留标准图；
- `CONSIDER_ADVANCED`：证据合同完整、确有增益且最终尺寸可读，才比较候选；
- `REJECT_ADVANCED`：候选会制造错误结构，尤其是不满足合同的 3D。

只有返回候选或边界不明确才读取 `advanced-figure-candidates.md`。Ridgeline、Raincloud、Bubble Matrix、Hexbin/2D KDE、Parallel Coordinates、Network、Slope/Dumbbell、Bump、Ternary、SHAP、Mosaic/Association、残差 Bubble、Parallel Sets/Alluvial、Marimekko、UpSet、Corrgram、Chord、Lollipop、Diverging Bar 及受限 3D 的合同保持不变。

高级图不得由“高级感”或 Portfolio 多样性触发。Mosaic/Alluvial/Marimekko、BioLadder 候选和 3D 继续服从原有窄门槛。

### Gate 3：Visual Information Density Gate

调用 `visual_information_density_gate()`：

- `RECHART`：证据对象不能支撑图型，换图/表；
- `RESAMPLE`：回模型、优化器、Bootstrap 或 Monte Carlo 获取真实新点；
- `RESCALE`：诚实聚焦数据/区间，0 或基准在图外时明示；
- `PASS`：信息密度与可见度足够。

优先级为 `RECHART > RESAMPLE > RESCALE > PASS`。禁止复制、插值、平滑或抖动后冒充新证据。具体阈值和 fig6/7/10 纠正见 `visual-information-density.md`。

`RESAMPLE` 在流水线中必须转成 `RESAMPLE_REQUIRED` 并停止该图：记录缺失证据后交回“数模审题”重新计算、求解、验证并冻结结果，再由写作阶段依据新结果同步结果表、正文、摘要、数据 hash 与 Brief revision，之后才从 Gate 0 重新开始。绘图 Skill 不静默补算，写作 Skill 不自行重算，也不允许旧正文配新图。

### Gate 4：Evidence Richness Gate

密度通过后调用 `evidence_richness_gate()`：

- `PASS`：单一证据足够或互补层已完整；
- `COMPOSE_LAYER`：同一对象、同一坐标的互补证据克制叠加；
- `COMPOSE_PANEL`：同一 Claim 但量纲/编码不同，使用对齐面板；
- `KEEP_SEPARATE`：多 Claim、不同对象、独立或冗余证据分开、改表或删减。

例如下尾风险可组合经验分布、样本允许时的 KDE、均值、VaR 阈值、CVaR 与尾部区域。组合后仍只允许一个主 Claim；每层都必须说明删除后会失去哪项核验证据。

组合或换图后重新运行 Gate 2–3。

### Gate 5：Publication Style

图型和数据结构冻结后才读取 `publication-style.md`。应用固定语义色、字体/字号、线宽、柱宽、轴、图例、multi-panel 与统一渲染层。样式不得改变 Chart Type 或制造不存在的结构。

### Gate 6：Render 与 Visual Audit

导出 PDF 与 400 dpi PNG，用 `render_a4_preview.py` 按最终论文宽度生成 A4 预览，实际打开检查。读取 `visual-audit.md`，发现任何阻断项必须修改、重新渲染并复检。未打开最终预览不得标记 `FINAL`。

### Gate 7：Figure Portfolio Gate

全文或章节主要图基本确定后，按顺序调用 `figure_portfolio_gate()`：

- 同一家族至少约 3 次且占主要图约一半或连续 3 次，并跨越不同 Evidence 时返回 `REVIEW`；
- 连续两张结构相近的多系列 line/bar 也要求比较保留原图、small multiples、matrix、dot/dumbbell、distribution；
- heatmap 与 line/bar 使用同一重复审查规则；
- `REVIEW` 只触发重新执行 Gate 1–6。若原图仍最匹配，保留并记录理由；不设置多样性配额。

## 7. 核心工作流

### Step 1：读取数据与上下文

确认变量语义、单位、对象、时间/类别/连续参数结构、样本层级、模型结果和论文位置。不猜测缺失结果。流水线任务同时核对 `paper_ready_manifest.json`、Figure Brief、绘图时正文源文件/前后锚点与数据 hash；若收到 Flowchart Brief，停止普通绘图并路由到 `unflatten-ppt`。

### Step 2：填写 Figure Brief

冻结一个 Claim、Evidence Object、Evidence Roles、标准图候选、最终宽度和输出要求；写作已提供完整 Brief 时直接复用其字段。

### Step 3：选择标准图

读取 `chart-selection.md`；识别任务后按需读取 `task-patterns.md`。默认一张主图，只有比较必须时用 2–4 面板。

### Step 4：运行 Advanced Candidate Gate

每张图主动检查一次高级候选；不能增加真实信息或降低阅读负担时 `KEEP_STANDARD`。

### Step 5：运行 Density 与 Evidence Richness

先完成 `RECHART / RESAMPLE / RESCALE`，复检至 `PASS`；再判断互补证据应分层、分面或分开。组合后再次复检密度。

### Step 6：确定视觉编码

只给有意义的变量分配位置、长度、颜色、线型、marker、alpha 和面板。编码优先级：位置 > 长度 > 颜色 > 形状。

### Step 7：应用 Publication Style

读取 `publication-style.md`，调用 `cumcm_figure_style.py`，保持全文语义色和 A4 几何。

### Step 8：加入证据增强

只加入 Claim 需要的基准、阈值、分界、CI、最优/膝点、before/after 或 baseline；禁止装饰层。

### Step 9：Render → Open → Audit → Revise

导出并生成 A4 预览，读取 `visual-audit.md` 完成详细 QA。修订后重新运行受影响的 Gate。

### Step 10：全文 Portfolio 与输出

在主要图完成后运行 Portfolio；处理完全部 `REVIEW`，再交付图、代码、格式、图题和必要分析。正式论文流水线按共享接口整理普通图表 `records`；专用流程图 Skill 的资产记录可在最后一并汇总，再以 `--project-root / --records / --paper-ready-manifest / --out` 运行 `write_figure_manifest.py`。只有全部资产为 `FINAL` 且正文适配、QA/hash 无旧状态时生成 `FIGURES_READY`。

## 8. 输出要求

按用户需求输出以下最小集合：

1. 可直接进入论文的成图；
2. 可复现代码；
3. 适合时的 PDF 矢量版；
4. 400 dpi PNG；
5. 论文图题，格式“图 X 对象 + 内容”；
6. 必要时 3–4 句图后分析：读图结论、量化信息、模型解释、后续作用；
7. 正式论文流水线的 `figure_manifest.json`，记录每张普通图的 Brief、正文上下文快照、数据字段、脚本、最终文件 hash 与 QA 状态；若统一汇总流程图，只核验专用 Skill 给出的可编辑源文件和最终导出物。

文件名使用 `fig_p2_sensitivity_lambda.pdf` 等有意义名称；图文件不得包含学校、队员或赛区信息。若用户只要求画图，不额外输出长教程。

## 9. FINAL 阻断摘要

出现任一情况不得输出 `FINAL`：

- Claim、Evidence 与 Chart Type 不一致；
- Advanced 候选、Density、Evidence Richness 或 Portfolio 有未处理状态；
- “分布”无样本；连续曲线点数不足或新点不是重新计算；
- Figure Brief、上游 manifest 或数据 hash 失配，或仍有 `RESAMPLE_REQUIRED`；
- 正文源文件 hash、图前/图后锚点、合同 ID、数据字段、单位或坐标/分组语义缺失或不一致；
- heatmap 被当作避重默认；bar/line/heatmap 分流被破坏；
- Map 缺少有效坐标/边界/连接键，或把原始总量误读为空间强度；
- Gantt 缺少真实任务时段，或存在工期、资源重叠、precedence、释放/交期约束不一致；
- CI、文字、标注、图例在最终尺寸不可读；
- 语义色漂移；柱形粗重；面板过密；
- Mosaic/Alluvial/Marimekko、满幅组成边界、BioLadder 候选或 3D 未满足原合同；
- 满幅组成图存在 100% 外白带或为标签扩大坐标；
- PDF/PNG 裁字、缺字、乱码、损坏；
- 未实际打开最新 A4 预览。

详细阻断条件、20 类常见错误与完整清单只在交付阶段读取 `visual-audit.md`。

## 10. 最终行为

1. 优先读取用户数据、模型结果和上下文；
2. 不盲目套模板，不为图型多样或高级感换图；
3. 不复刻获奖论文原图，不虚构来源支持；
4. 用最少视觉元素表达最多可核验证据；
5. 关键参数主动考虑连续灵敏度，关键改进主动考虑 baseline/before-after；
6. 风险图严格区分样本分布与汇总指标；
7. 新采样必须真实计算；
8. 所有图共享语义色与 publication layer；
9. 详细规则从 8 个 reference 按需读取，不重新塞回主文件；
10. 只有完整走完 Gate 与 A4 审计才交付最终图。

最终目标：

> **让评委通过图表更快确认：模型为何这样建、结果是否可信、改进是否有效、方案是否稳定。**

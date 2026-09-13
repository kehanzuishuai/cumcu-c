# Advanced Figure Candidate Gate

每张图在标准图通过 `Claim → Evidence → Chart Type` 后都运行轻量接口；只有接口返回结构候选或边界不明确时才读取本文件。高级图是候选，不是升级目标，Portfolio 多样性不能触发高级图。

## 1. 启用门槛

按固定顺序判断，前一项不成立即停止；同时满足以下条件才返回 `CONSIDER_ADVANCED`：

1. 数据结构满足候选图的证据合同；
2. 相比标准图，候选图至少多表达一个与 Claim 相关的真实信息维度，或以明显更低的阅读负担揭示同一结构；
3. 所需原始样本、网络边、SHAP 值或响应网格真实存在；
4. 缩放到 A4 最终宽度后仍可辨认；
5. 不改变原 Claim，不增加数据无法支持的视觉暗示。

这对应 `证据匹配 > 信息表达 > 可读性 > 全文多样性 > 高级感`。若结构支持但没有实质增益，或高级候选降低最终尺寸可读性，返回 `KEEP_STANDARD`；若企图用不满足合同的 3D 响应面，返回 `REJECT_ADVANCED`。候选结果之后仍执行现有 Visual Information Density Gate、语义配色和最终视觉 QA。

## 2. 候选图与证据合同

| 候选图 | 必需证据结构 | 适合表达 | 关键限制 |
|---|---|---|---|
| Ridgeline | 3 组以上有序分组的真实样本，单组通常不少于约 30 个观测 | 多期/多组分布形态迁移 | 共享横轴；小样本、需要精确跨组读数时改 raincloud/箱线 |
| Raincloud | 2–6 组真实样本，单组通常不少于约 20 个观测 | 分布、区间和原始点同时核验 | 半小提琴、箱/区间和点必须来自同一批样本；汇总值不能伪装成云雨图 |
| Bubble Matrix | 两个离散轴及单元格量值，可有第二个定量通道 | 品类 × 日期、对象 × 指标矩阵 | 颜色与面积最多分别承担两个明确量；只有一个量时优先普通热力图 |
| Mosaic / Association Plot | 两个分类变量的真实列联频数；边际与联合占比均有解释价值 | 分类 × 分类关联、边际结构与联合结构 | 只有单元格读数时保留 heatmap；只有边际总量时保留 bar/dot；面积必须来自频数/比例，不得等宽伪装 |
| Standardized-residual Bubble Plot | 列联表及同一独立性模型下计算的标准化残差 | 哪些类别组合贡献主要正/负偏离 | 面积编码 `|residual|`，颜色或填充编码符号；原始频数不是残差，未计算残差时 `KEEP_STANDARD` |
| Parallel Sets / Alluvial | 至少两个类别阶段、可追踪的类别映射及真实流量/权重 | 类别映射、迁移、去向与保留 | 流带宽度必须来自真实权重；若只比较各阶段边际数量，保留对齐 bar/dot；不作为装饰性 Sankey |
| Marimekko | 每组有真实总量，组内分量闭合为整体，且同一 Claim 同时需要总量与组成 | 总量差异 + 内部组成 | 宽度编码总量、高度编码组内比例；只看组成用 100% stacked bar，只看总量用 bar/dot，单元格模式优先 heatmap |
| UpSet Plot | 3–12 个集合的真实对象成员关系，可计算非空交集大小 | 多模型共同入选特征、多方案共同对象、多条件集合交集 | 2 个集合或非常简单的 3 集合关系保留 Venn/表格；不得只拿集合总量伪造交集矩阵 |
| Corrgram / Pairwise Relationship Matrix | 4–8 个连续变量、至少约 30 行成对观测，且 Claim 同时需要分布与两两关系 | 对角分布、散点/密度、相关系数的联合核验 | 只需相关系数时保留 correlation heatmap；变量过多时筛选变量或拆面板，禁止缩成不可读小格 |
| Chord Diagram | 3–12 个类别节点、真实边与关系权重，Claim 关注共享关系强度或互联结构 | 商品互补/替代、地区流向、供应商—品类关系 | 路径/阶段是重点时用 network/alluvial；关系过密时用矩阵；禁止无权重彩带和不可追踪的彩虹扇区 |
| Lollipop Plot | 约 10–30 个可排序类别及单一可比较量，圆点/短杆能降低柱形视觉重量或标签拥挤 | 排名、敏感性指标、变量重要性、中等数量类别比较 | 它是克制的 dot/bar 替代而非“高级图”；少类别精确比较可保留 bar/dot，没有明确可读性增益则 `KEEP_STANDARD` |
| Bidirectional / Diverging Bar | 2–30 个类别、真实有符号数值及有意义的零基准 | 正负变化、增减、方案相反效应、贡献拆解 | 两个无关绝对量不得强行置于零线两侧；正负颜色服从业务语义，不自动把所有负值染成风险红 |
| Hexbin / 2D KDE Contour | 大量二维连续成对观测；通常分别不少于约 200/300 点 | 密集关系、聚集区、非线性联合结构 | 小样本保留散点；KDE 不得掩盖原始范围和边界效应 |
| Parallel Coordinates | 约 4–10 个可比较的连续维度 | 方案的多指标画像、约束模式 | 先标准化并注明尺度；主体灰化，只高亮关键方案，禁止彩色线团 |
| Network Graph | 有实际节点、边和边权/方向 | 供应、传播、协作或依赖结构 | 相关矩阵不能未经阈值依据冒充网络；布局不代表距离，除非模型如此定义 |
| Slope / Dumbbell | 同对象成对的前后、基准—改进或两方案数值 | 变化方向与差值 | 未配对样本不得连接；对象多时排序、分面或仅保留关键对象 |
| Bump Chart | 至少 3 个有序时点的真实名次 | 排名随时间的升降与交叉 | 它表达排名而非绝对值；控制实体数量并直接标注关键线 |
| Ternary | 恰好 3 个非负组成部分，且和为固定常数 | 三元配比、混合方案与可行域 | 任意三个独立指标不得强制归一化后画三元图 |
| SHAP | 已拟合模型和真实计算的 SHAP 值 | 全局贡献、特征依赖、单样本解释 | beeswarm 用于全局，dependence 用于关系，waterfall 用于局部；普通特征重要性不能改名为 SHAP |
| 3D Response Surface | **恰好两个连续输入参数 → 一个连续响应**，且有真实网格或足够密集的计算结果 | 峰、谷、鞍点、交互形状 | 先与证据匹配的 2D 等高线/矩阵图比较；只有三维几何增加不可替代信息时才启用，禁止 3D 柱或类别型“曲面” |

## 3. 标准图与高级候选的复核顺序

1. 先保留标准图作为基线版本。
2. 用相同数据生成候选版本，不改变筛选口径、坐标语义和色彩角色。
3. 在论文实际宽度比较：结论核验是否更快、遮挡是否更少、是否增加可读证据。
4. 仅当答案明确为“是”时采用候选；否则保留最匹配的折线、柱/条、点、区间、矩阵或分布等标准图。

典型判断：

- 品类 × 日期只有一个数值且目标是读取单元格模式：可用普通热力图；若目标是各品类轨迹，则折线或 small multiples 可能更合适；
- 品类 × 日期同时有价格和销量且两者都服务同一 Claim：可比较 bubble matrix 与分面对齐热力图；
- 列联表若 Claim 只是“哪个单元格最多”，保留 heatmap；若还需同时看边际占比与联合占比，才比较 mosaic；若结论指向“哪些组合显著偏离独立性”，且已有标准化残差，才比较 residual bubble；
- 类别映射若只有各阶段总量，保留对齐 bar/dot；只有真实个体/权重可跨阶段追踪时才比较 parallel sets/alluvial；
- 组成数据若只比较比例，保留 100% stacked bar；只有总量差异和内部组成都服务同一 Claim 时才比较 Marimekko；
- 多组真实利润样本：raincloud/ridgeline 可能补充组间分布结构，但下尾风险结论仍优先保留阈值和尾部证据；
- 双参数灵敏度：2D 热力/等高线优先；曲面确有峰谷或交互几何且静态视角能读清时才考虑 3D。
- 多模型入选特征若只比较各模型入选数量，保留 bar/dot；只有对象级成员关系和多个交集本身是证据时才比较 UpSet；
- 4–8 个变量若需同时核验边际分布、非线性形态和相关强度，可比较 Corrgram；只需系数矩阵时不从 heatmap 升级；
- 类别关系若边权及共享结构是证据，可比较 Chord；若读者需要追踪方向路径、阶段迁移或大量稠密边，则分别改用 network/alluvial 或关系矩阵；
- 10–30 个有序类别若柱形过重、标签拥挤，可用水平 Lollipop；这属于可读性优化，不构成高级感奖励；
- 正负效应只有围绕真实零点才使用 Diverging Bar；没有方向语义时保持 grouped bar、dot 或 dumbbell。

## 4. Publication-style 与 multi-panel 规则

从 `figures4papers/scientific-figure-making` 的真实 `figure_*` 案例中只吸收可迁移的编码思想：

- `figure_ophthal_review`：品类矩阵使用单元格热力编码和克制标注；趋势与构成分面时共享事件语义，而不是把所有变量叠到一个轴；
- `figure_RNAGenScape`：多个矩阵使用对齐面板、统一刻度、单元格文字对比和一致色阶；
- `figure_ImmunoStruct`、`figure_Cflows`：多指标比较采用共享布局与独立图例区，图例只出现一次；
- `figure_VIGIL`：密集雷达轴会造成标签和多边形拥挤，说明“看起来高级”并不等于结构更匹配，因此雷达图不进入本候选清单。

来源仓库没有把 Mosaic、Alluvial 或 Marimekko 作为现成范例；本 Skill 只把上述真实案例的 publication-style 组织法迁移到这些新候选，不宣称复制了同型原图。

BioLadder 公共工具页可核验到相关性矩阵与和弦关系类工具；本次同时依据用户给出的候选清单补入 UpSet、Lollipop 和 Diverging Bar。这里吸收的是“按数据结构选图、参数化组织、示例驱动”的方法，不宣称五类图都是 BioLadder 当前公开工具，也不把在线平台变成运行依赖。

转化到 CUMCM A4 论文时：

- 面板必须共同服务一个主 Claim，采用共享轴或可比较尺度；
- 主方案、对照、基准、改进、风险继续沿用现有语义色板，高级图不得自创另一套彩虹配色；
- 颜色之外使用位置、面积、线型、明度或边界作为必要的备份编码；
- 图例、色条和面板标签统一放置，避免每个子图重复；
- Mosaic/Marimekko 的面积与流带宽度承担定量编码，颜色只保留语义/符号；residual bubble 使用克制的正负双向色，Alluvial 只高亮关键迁移，其余流带灰化；
- UpSet 的交集大小用排序条形、成员组合用黑灰点阵，集合总量放在独立对齐轴；只保留有解释价值的主要交集，其余合并说明；
- Corrgram 对角线放单变量分布，下三角放散点/hexbin 或克制拟合，上三角放相关系数；各面板来自同一批完整成对行，变量次序全图一致；
- Chord 固定扇区顺序、限制节点和带数，普通关系灰化、关键关系用语义色高亮；方向仅在真实且静态缩放后仍可辨时编码；
- Lollipop 默认水平排序，杆使用中性细线、圆点使用语义色；Diverging Bar 明示零线，需要可比时使用对称范围，按有符号效应或绝对贡献排序；
- Marimekko 与 100% stacked bar 的比例轴锁定 `0–1` 或 `0–100`，禁止 autoscale/margin 白带；边界标签用向图内 annotation，不扩大坐标范围；
- 不照搬超宽画布、超大字体、粗线或全部数值标注。

## 5. 明确禁止的“炫技升级”

- 不因全文图型普通而主动加入雷达、3D 或 Sankey；
- Sankey 仅在有守恒的真实流量、方向和节点层级时另行论证，本门禁不自动推荐；
- 雷达图继续受现有窄门槛约束，不用于精确排名、多方法密集比较或高维拥挤数据；
- 3D 只接受上表的双连续参数响应面合同，不接受 3D 柱、饼或类别散点；
- 不用插值、平滑或面积编码制造原数据不存在的结构。

## 6. 代码接口

```python
from cumcm_figure_style import advanced_figure_candidate_gate

candidate = advanced_figure_candidate_gate(
    "dense_bivariate",
    observations=1200,
    material_gain=True,
    readable_at_final_size=True,
)
# candidate.status == "CONSIDER_ADVANCED"
# candidate.candidates == ("hexbin", "2d_kde_contour")

association = advanced_figure_candidate_gate(
    "categorical_association",
    categorical_dimensions=2,
    contingency_table=True,
    standardized_residuals_available=True,
    material_gain=True,
    readable_at_final_size=True,
)
# 只有边际/联合结构及残差贡献都服务 Claim 时，才考虑两个类别结构候选

intersections = advanced_figure_candidate_gate(
    "set_intersection",
    set_count=6,
    intersection_membership_available=True,
    material_gain=True,
    readable_at_final_size=True,
)
# intersections.candidates == ("upset_plot",)

ranking = advanced_figure_candidate_gate(
    "variable_importance",
    groups=18,
    ordered_categories=True,
    readability_gain=True,
    readable_at_final_size=True,
)
# Lollipop 仅因最终尺寸阅读负担确实降低而进入候选
```

普通 `time_series`、`category_comparison`、`point_estimate` 等也要调用接口；没有受支持的高级结构时会直接 `KEEP_STANDARD`。接口同时识别 `dense_scatter`、`before_after`、`ranking_over_time`、`category_time_matrix` 等常用别名，避免只因命名不同漏掉候选。

类别结构候选可使用 `categorical_dimensions`、`contingency_table`、`standardized_residuals_available`、`flow_stages`、`has_flow_weights`、`has_total_and_composition` 与 `composition_closes` 描述证据合同。新增候选使用 `set_count`、`intersection_membership_available`、`paired_observations_available`、`ordered_categories`、`signed_values_available` 与 `meaningful_zero`。`material_gain=True` 必须确认候选比 bar/dot/heatmap 多表达至少一个真实信息维度；只有 Lollipop 可改用 `readability_gain=True` 表示已在 A4 尺寸确认阅读负担明显降低。`readable_at_final_size=True` 必须来自实际尺寸检查，不能因为候选名称更“高级”或全文缺少图型变化而设置。

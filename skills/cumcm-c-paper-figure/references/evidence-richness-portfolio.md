# Evidence Richness / Figure Portfolio Gate

只在单图已通过 `Claim → Evidence → Chart Type` 与 Visual Information Density Gate，或全文主要图已基本确定时读取本文件。

## 1. 目的与边界

本门禁解决两个问题：

1. 一个结论确实依赖多个互补证据时，不再把它们压成一条普通折线、一组柱或几个点；
2. 全文图型明显重复时，检查是否把不同证据结构机械套进同一模板。

它不设“至少使用几种图”的指标，也不把复合图当成高级图。所有组合、拆分与换图都必须服从：`证据匹配 > 信息表达 > 可读性 > 全文多样性 > 高级感`。Portfolio 是末位诊断，不能推翻前三项。

## 2. 单图 Evidence Richness Gate

先列出证据角色，并判断它们的关系：

- `complementary`：共同核验同一主结论，缺一层会显著削弱解释；
- `independent`：各自回答不同问题，即使来自同一数据也不应硬合并；
- `redundant`：重复表达同一信息，优先删减而不是增加面板。

只有同时满足下列条件，才允许生成复合科研图：

1. 仍只有一个主要 Claim；
2. 证据指向同一对象或同一决策；
3. 各层互补而非重复；
4. 组合后仍能在 A4 最终宽度下清楚阅读；
5. 每一层都有真实数据、模型结果或阈值依据。

输出动作：

| 状态 | 适用情形 | 动作 |
|---|---|---|
| `PASS` | 单一证据已足够，或互补层已完整 | 保持当前图，不为丰富而继续加层 |
| `COMPOSE_LAYER` | 同一对象、同一坐标可承载互补证据 | 在一个轴上克制叠加数据、趋势、阈值、区间或风险区域 |
| `COMPOSE_PANEL` | 同一 Claim 需要不同坐标/编码 | 使用 1×2 或上下对齐面板，共享颜色和图例语义 |
| `KEEP_SEPARATE` | 多 Claim、不同对象、独立或冗余证据 | 分图、改表、删减；禁止为“复合感”硬拼 |

### 优先的复合证据结构

- 分布结论：经验分布/ECDF + KDE（样本允许时）+ 阈值线 + 风险尾部着色；
- 预测结论：真实值 + 预测值 + 阶段分界 + 预测区间，诊断若量纲不同用相邻面板；
- 关系结论：原始散点 + LOESS/拟合 + CI + 理论/零基准；
- 优化折中：Pareto 点集 + 选定解 + 理想点/膝点；若需要解释稳健性，另设对齐的小面板，而非双 Y 轴；
- 改进有效：baseline 与 improved 同尺度对照 + 差值/区间证据。

以下不构成 Evidence Richness：给每个点贴数字、增加无依据拟合、重复画同一统计量、用双 Y 轴拼接无关指标、把四张弱图塞进 2×2 面板。

## 3. 全文 Figure Portfolio Gate

正文主要图确定后，按论文顺序建立轻量清单：

```python
portfolio = [
    {"figure_id": "fig3", "chart_family": "line", "evidence_kind": "time_series", "series_count": 4},
    {"figure_id": "fig6", "chart_family": "line", "evidence_kind": "parameter_sweep", "series_count": 3},
    {"figure_id": "fig7", "chart_family": "distribution", "evidence_kind": "tail_samples"},
]
```

`chart_family` 使用折线、柱/条、散点、分布、区间、热力/矩阵、流程等高层家族；`evidence_kind` 写时间序列、连续参数、离散比较、样本分布、效应区间、相关矩阵等证据结构；多系列折线或柱可增加 `series_count`，省略时按 1 处理。

默认在同一家族至少出现 3 次，且占全文主要图约一半或连续出现 3 次，并跨越多种 Evidence 时返回 `REVIEW`。折线、柱/条、点图和 heatmap 使用同一规则；heatmap 不因常被当作“替代图”而豁免。该状态只表示需要复核，不表示必须换图：

1. 对被标记图重新执行 `Claim → Evidence → Chart Type`；
2. 若图型仍是该证据的最佳编码，保留并记录一句选择理由，可将 `selection_confirmed=True` 后复检；
3. 只有发现 Evidence 与 Chart Type 不匹配时才换图；
4. 若同类图反复出现是因为证据结构真的相同，例如多个品类的同口径时间序列，则允许保留，优先统一尺度或改 small multiples，而不是追求图型花样。

### 连续多系列图的额外复核

若全文或同一章节连续出现至少两张结构相近的多系列折线图或柱状图，即使 `evidence_kind` 表面相同，也返回 `REVIEW`，并逐张平等检查：

- 趋势连续性是主要证据：保留 line；
- 少量离散类别的精确大小是主要证据：保留 bar 或 dot；
- 多条趋势必须保留但相互遮挡：比较共享尺度的 small multiples；
- 对象 × 时间或对象 × 指标确为二维矩阵，且单元格模式是主要证据：比较 heatmap；若两个定量通道都服务同一结论，再比较 bubble matrix；
- 同对象的基准—改进或前后变化：比较 dot/slope/dumbbell；
- 结论依赖真实样本的形态或尾部：使用 distribution，而非把均值画成多系列折线/柱。

这仍不是强制换图规则。若趋势连续性或离散量级比较就是主要证据，原折线/柱经过复核后设置 `selection_confirmed=True` 即可保留。

全文检查传入按论文顺序排列的主要图；章节检查则把每章清单分别调用一次，避免跨章的非连续图产生误报。

2023 C 题式例子：图8“各品类补货量随日期变化”的证据是时间轨迹，可保留折线；图9“品类 × 日期定价矩阵”的证据是二维矩阵，热力图比另一张多系列折线更直接。更换的依据是证据结构，不是为了让相邻图看起来不同。

## 4. 代码接口

```python
from cumcm_figure_style import evidence_richness_gate, figure_portfolio_gate
```

- `evidence_richness_gate(...)`：返回 `PASS / COMPOSE_LAYER / COMPOSE_PANEL / KEEP_SEPARATE`；
- `figure_portfolio_gate(...)`：返回 `PASS / REVIEW`，并列出需要复核的图型家族；
- 两个接口只做决策提示，不生成不存在的数据，也不自动修改图型。

每张图在 Portfolio 之前都应运行轻量 `advanced_figure_candidate_gate()`；只有返回结构候选或边界不明确时才按需读取 [advanced-figure-candidates.md](advanced-figure-candidates.md)。高级图和 heatmap 都不是 Portfolio Gate 的默认整改项。

完成组合或换图后，必须重新运行 Visual Information Density Gate，并执行 A4 `Render → Open → Visual Audit → Revise`。

# figures4papers 融合说明

只在维护视觉系统、处理复杂多面板或解释风格来源时读取本文件。

## 已吸收

| figures4papers 方法 | 在本 Skill 中的转化 |
|---|---|
| 深蓝、绿、红、灰构成的稳定色族 | 改为“主方案/改进/风险/基准”语义映射，并增加柔和橙作为对照 |
| top/right spine 隐藏、frameless legend | 收敛为 0.8 pt A4 渲染层；矩阵/生存/检验图允许保留四边 |
| 多面板统一字体、线宽与颜色 | 由 `apply_publication_style`、`style_axis`、`add_panel_labels` 统一 |
| 独立图例区 | 仅在图例确实遮挡复杂数据时使用；普通图优先共用图例或图外图例 |
| 直接数值标注 | 只保留少量关键柱、极值、膝点和阈值，避免 A4 缩放后变成文字墙 |
| hatch 和边界增强灰度可辨性 | 作为颜色的备份通道，不作为装饰；边界降为 0.4–0.6 pt 深灰 |
| `tight_layout`、高 DPI、PDF/SVG | 使用 constrained layout、PDF 可编辑文字和 PNG 400 dpi 双输出 |
| 先生成再看成图 | 升级为 `Render → Open → Visual Audit → Revise` 发布门禁 |

## 未照搬

- 超宽 `figsize=(28, 6)`、`(45, 12)`：它适合论文跨栏大面板，不适合国赛 A4 单页。遇到拥挤应分面、换图或移附录。
- 24–36 pt 字号和 2–3 pt 轴线：缩小后视觉过重。本 Skill 按最终物理字号控制在约 7.5–10.5 pt。
- 所有柱使用纯黑粗边：改为无边或细灰边。
- 对每根柱标值：只标论文真正需要读出的关键值。
- 柱状图截断纵轴：普通柱从 0 起；微小差异改点图/森林图。
- `text.usetex=True` 与固定 Helvetica：默认使用可移植字体 fallback，避免比赛电脑缺依赖。
- 将对照方法固定为红色：红色在本 Skill 中专用于风险/异常，对照改为柔和橙。

## 维护原则

后续吸收外部科研绘图仓库时，优先提取“信息编码、几何、排版和验证方法”，不要把某篇论文的配色顺序、具体尺寸或数据形状写成普遍真理。

## 真实 `figure_*` 案例的增量吸收

- `figure_ophthal_review`：矩阵热力图的单元格编码、克制数值标注，以及趋势/构成分面时共享事件语义；
- `figure_RNAGenScape`：多矩阵面板对齐、统一刻度、色阶和文字对比；
- `figure_ImmunoStruct`、`figure_Cflows`：多指标面板共享版式，复杂图例独立但只出现一次；
- `figure_VIGIL`：密集雷达图暴露出轴多、标签拥挤和精确比较困难，因此不能把 radar 当作“高级感”默认来源。

v1.4.2 将这些组织方法继续用于类别结构候选：Mosaic/残差气泡沿用矩阵对齐与克制标注，Parallel Sets/Alluvial 沿用共享语义与关键对象高亮，Marimekko 沿用统一图例和面积编码纪律。来源仓库没有这些图型的现成 canonical demo，因此只迁移 publication-style、multi-panel 与 annotation 方法，不复刻或虚构参考案例。

满幅组成图另增加边界收敛：100% 比例轴和 Marimekko 总量轴使用显式 limits + zero margins；边界文字通过向图内 annotation 解决，而不是扩大坐标范围。该处理补足了 `tight_layout` / `bbox_inches='tight'` 无法消除的轴内 autoscale 白带。

这些方法只用于 [advanced-figure-candidates.md](advanced-figure-candidates.md) 中证据合同成立的候选，并继续服从现有 CUMCM A4 尺寸、语义配色与视觉 QA。

# CUMCM Publication Style 与渲染层

只在图型与 Gate 决策已经确定、准备编码或统一全文视觉时读取。本文件承接原主 `SKILL.md` 的字体、配色、几何、图例、multi-panel、Matplotlib/MATLAB 和输出规范；不得用样式规则反向改变 Chart Type。

## 1. 来源边界与总体风格

历史 PDF 中部分图为栅格，不能可靠反推出精确字体和 pt。以下是结合近年优秀论文视觉比例、A4 最终可读性及中文论文常见字体形成的操作性标准，不宣称所有获奖论文采用同一数值。

默认总体风格：白底、低装饰、有限色彩、二维直角坐标、浅灰主网格、短图例、图题置于图下。预测要区分历史/预测阶段；统计图优先“原始数据 + 趋势/拟合 + 基准/阈值”；不确定性使用浅色区间带。

`figures4papers` 的来源取舍与真实 `figure_*` 案例见 [figures4papers-fusion.md](figures4papers-fusion.md)。本文件只保存已收敛到 CUMCM A4 的执行规范。

## 2. 字体与字号

### 2.1 字体

- 中文：宋体/SimSun；fallback 可用 STSong、Songti SC；
- 英文与数字：Times New Roman；
- 数学公式：STIX/Times 风格；
- 不用手写、圆体或艺术字体。

宋体在小字号明显发虚时，纯图内中文可统一改为微软雅黑/黑体；同篇论文不得漂移。

### 2.2 最终 A4 物理字号

| 元素 | 默认 | 范围 |
|---|---:|---:|
| 图内主标题 | 默认不放 | 10–11 pt |
| 坐标轴标题 | 9.5 pt | 9–10.5 pt |
| 刻度 | 8.5 pt | 8–9 pt |
| 图例 | 8.5 pt | 8–9 pt |
| 注释/阈值 | 8 pt | 7.5–9 pt |
| 子图短标题 | 9 pt | 8.5–10 pt |
| `(a)(b)` | 9 pt | 8.5–10 pt |

最终插入论文后任何有效信息文字不得小于约 7.5 pt。若必须继续缩小，说明图型或布局应重构。

## 3. 固定语义配色

颜色绑定论文语义，不按系列序号机械循环：

```text
主方案 / 真实值      #0F4D92
同族辅助 / 预测值    #3775BA
对照方案             #E3A06A
改进 / 正向变化      #7FAE79
风险 / 异常 / 下尾   #B64342
基准 / 理论线        #767676
背景 / 次要类别      #CFCECE
不确定性带           #DCE8F3
风险尾部带           #F2D7D5
网格                 #D9D9D9
```

硬规则：

- 主方案深蓝、对照柔和橙、基准灰、改进低饱和绿、风险克制红；
- 实际与预测同对象时可用深蓝实线/中蓝虚线；若预测用橙，全篇保持；
- 颜色只承担一个主要通道，不再同时表示置信度或参数量；
- 6 类以上优先 small multiples、直接标注或“关键着色 + 其余灰化”；只有真实二维矩阵才使用 heatmap；
- 灰度打印增加线型、marker 或稀疏 hatch，不能只靠红绿；
- 用户已有合格的全文配色合同时保留，不强制替换。

Heatmap：单向强度用白—浅蓝—深蓝；双向相关用低饱和红—白—蓝且中心固定 0；密度用浅蓝—深蓝。禁用 `jet`、彩虹、霓虹、黑底科技蓝和无含义渐变。

## 4. 线条、点与不确定性

- 主曲线 1.6–1.9 pt；次曲线 1.2–1.5 pt；阈值/参考 1.0–1.2 pt 虚线；
- 散点通常 18–28 pt²，alpha 0.45–0.70；密集点缩小并降 alpha；
- marker 只在需辨识离散采样点时使用；
- 实线表示主要估计/真实，虚线表示阈值/理论/对照/外推，点划线表示第二类基准；
- 基准、0 线和分割线使用黑/深灰，不与数据争色；
- CI/PI 与主线同色，alpha 0.12–0.22，不用渐变或厚重边框；多组带重叠时降低 alpha 或拆面板。

## 5. 柱形几何

仅在柱状图门禁通过后应用：

- 单系列竖柱 `width=0.52`，允许 0.45–0.60；
- 分组柱整组占位不超过类别间距 0.72，保留约 0.28 组间空白；
- 默认 `edgecolor='none'`；灰度确需分隔时用 0.4–0.6 pt 深灰细边或稀疏 hatch；
- 类别超过约 6 个先比较水平条、lollipop/dot 或分面；只有真实二维离散轴才比较 heatmap；
- 只有部分—整体关系使用 stacked bar；独立指标不得堆叠；
- 只标关键柱、极值或最终方案，不给每根柱默认贴数；
- 普通柱轴从 0 开始。零点压扁微小差异时改 dot/forest，不截断柱轴。

统一几何函数：`bar_width()`、`grouped_positions()`。

## 6. 坐标轴、边框与网格

### 6.1 坐标轴

- 轴名必须包含变量语义；有单位时写 `销量 / kg`、`时间 / d`、`利润 / 元`；
- 禁止 `Value`、`Number`、`x`、`y` 等占位名；
- 不滥用双 Y 轴，量纲不同优先上下对齐面板；
- 日期过密时减少刻度，不把所有日期旋成文字墙；
- Marimekko、100% stacked bar 的比例轴精确锁定 `0–1` 或 `0–100` 且 margin 为 0；Marimekko 总量轴贴合真实累计边界；边界标签用向图内 annotation，不扩大坐标。

满幅组成图调用 `lock_full_span_composition_axis()`、`annotate_composition_boundary()` 与 `audit_full_span_composition_axis()`。

### 6.2 边框

默认保留左/下，去除上/右；统计检验、矩阵、生存图若矩形框更利于读数可保留四边。边框 0.7–0.9 pt 深灰，不用纯黑粗框。

### 6.3 网格

只用 major grid，`#D9D9D9`，alpha 0.35–0.55，线宽 0.5–0.7 pt。时间序列、灵敏度、残差可开；heatmap、混淆矩阵、PCA 通常关闭。禁用密集主次交叉网。

## 7. 图例、图题与注释

### 7.1 图例

- 2–5 组优先图例，放空白角或图外右侧；
- 不遮峰值、异常、区间或尾部；
- 标签短且有语义，如“实际值”“预测值”“基准模型”；禁用 `Series 1`、`data1`；
- 边框去除或极浅；超过 5 类时重构图，不缩小图例解决。

### 7.2 图题

论文图题置于图下，格式为“图 X 研究对象 + 展示内容”，短而具体，不写空泛“结果图/分析图”。结论留给正文。图内标题默认删除；只有区分子图、独立导出或用户明确要求时保留短标题。

### 7.3 注释

只标阈值、最优、膝点、切换点、极值或异常。边界点使用 `annotate_point_safely()` 向图内偏移，不通过扩大坐标制造空白。

## 8. A4 尺寸与 multi-panel

建议尺寸：单图 `(6.4, 3.6)`；时间序列 `(6.5, 3.4)`；1×2 `(6.8, 3.0)`；2×2 `(6.8, 5.2)`；heatmap `(5.8, 4.8)`；forest 高度按条目动态增加。

原则：宁可多占半页，不把关键图缩成邮票。

- 1×2：baseline/improved、before/after、两个对象/情景/相关指标；尽量共享范围和图例，不重复相同 y 标签；
- 1×3：仅用于简单、同量纲、同尺度关系；复杂图例或长标签改 2×2/分图；
- 2×2：四个同类结果、消融或情景；共享刻度、统一语义色和间距；
- 超过 6 面板：矩阵证据才比较 heatmap；轨迹使用分批 small multiples；离散比较用水平条/dot；正文只留关键 4–6 个，其余附录；
- 禁止 3×4、4×4 后缩小字体；
- multi-panel 必须共同服务一个 Claim，图例/色条统一放置且只出现一次；量纲不同用对齐面板，不用双 Y 轴。

高级候选的面板组织仍以 [advanced-figure-candidates.md](advanced-figure-candidates.md) 为准。

## 9. 禁止的 AI/网红感

默认禁止霓虹渐变、深色大背景、发光/玻璃拟态、3D 柱/饼、彩虹 heatmap、大圆角卡片、emoji 代替符号、无信息阴影、视觉性截断 y 轴、八种以上颜色、邮票式多图、大标题 + 副标题 + slogan、全粗刻度和纹理背景。

## 10. Matplotlib publication rendering layer

用户未指定工具时优先 Python + Matplotlib，直接复用 [scripts/cumcm_figure_style.py](../scripts/cumcm_figure_style.py)：

```python
from cumcm_figure_style import (
    SEMANTIC_COLORS,
    apply_publication_style,
    create_subplots,
    finalize_figure,
    style_axis,
)

apply_publication_style()
fig, axes = create_subplots(1, 2, width="full", height=3.0)
ax = axes[0]
ax.plot(x, y, color=SEMANTIC_COLORS["primary"], label="主方案")
style_axis(ax, grid="y")
finalize_figure(fig, "figures/fig_p2_result", formats=("pdf", "png"))
```

该层统一字体 fallback、0.8 pt spine、向外 tick、主次线宽、浅网格、frameless legend、面板标签、语义色板、A4 宽度、constrained layout、PDF 可编辑文字、PNG 400 dpi、白底、柱宽、风险分布/forest 及轻量静态审计。

复杂数据确需时可使用共享图例或独立图例区，不为图例制造空白面板。统计检验、生存和矩阵可覆盖 `style_axis` 保留四边。

输出：线、柱、流程等优先 PDF 矢量；PNG 400 dpi 用于兼容与 QA；超密散点可只 rasterize 点层，保留轴、文字和拟合线为矢量。

## 11. MATLAB 等价规范

用户指定 MATLAB 时：英文/数字 `Times New Roman`，中文用可用宋体；字号 8–10，线宽 1.4–1.8；默认 `Box off`，矩阵例外；开启网格后降低 `GridAlpha`；手动使用本语义色板；`exportgraphics(...,'Resolution',400)`；可矢量时优先 PDF/EPS。禁用默认高饱和 `jet`。

## 12. 输出前样式核对

样式应用后仍必须读取 [visual-audit.md](visual-audit.md) 并执行 A4 `Render → Open → Visual Audit → Revise`。代码运行、原尺寸截图或单独 PDF 好看都不能替代最终物理尺寸审计。

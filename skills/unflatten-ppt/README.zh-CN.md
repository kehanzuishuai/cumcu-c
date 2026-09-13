# unflatten-ppt

[English](README.md) | **简体中文**

把压扁的 PNG 示意图还原成完全可编辑的 PowerPoint 幻灯片——每个方框、箭头、标签都是原生形状，而不是贴上去的位图。

`unflatten-ppt` 是一个面向 [Codex](https://github.com/openai/codex)、[Claude Code](https://claude.com/claude-code) 等编程智能体的 **agent skill**。给智能体一张技术图的光栅图片——论文插图、架构草图、流程图、截图——它会用原生 PowerPoint 对象（文本框、形状、连接线、表格、组合）把图重建成 `.pptx` 幻灯片，然后把幻灯片导出回 PNG、与参考图对比，迭代到重建结果与原图一致。

## 为什么

把 PNG 贴到幻灯片上，得到的是"图的照片"；重建它，得到的才是图本身：

- **随处可改** —— 改措辞、换颜色、重新布线箭头，不必回到原绘图工具。
- **随处可用** —— 把形状复制到其他幻灯片，按你的模板重新配色。
- **可持续迭代** —— AI 生成的概念图变成可以讨论、修改的草稿，而不是死胡同。

## 工作原理

1. **读图** —— 智能体分析源 PNG：区域划分、文本块、形状、箭头、颜色、重复结构。像素坐标就是布局坐标系。
2. **重建** —— 把每个重要元素重建为可编辑 PPT 对象；可以直接在 PowerPoint 中制作，也可以在需要可复现生成时使用 `python-pptx`。可编辑 `.pptx` 必须保留，生成代码仅在实际使用时保留。
3. **导出** —— `scripts/export_ppt_slide.ps1` 通过 PowerPoint COM 自动化把幻灯片渲染成 PNG。
4. **对比** —— `scripts/compare_pngs.py` 生成左右并排对比图，并输出 RMS / 平均差异指标。
5. **迭代** —— 先修布局，再修文字，最后修连接线，直到没有结构性错误。交付前用 `references/quality-checklist.md` 把关。

## 安装

### Claude Code

```bash
git clone https://github.com/Feng-Y-28/unflatten-ppt.git ~/.claude/skills/unflatten-ppt
```

遇到"把这张 PNG 转成可编辑 PPT"、"每个元素都要可编辑"之类的请求时，skill 会自动触发。

### Codex

克隆到你的 Codex skills 目录（如 `~/.codex/skills/`）；`agents/openai.yaml` 提供接口元数据。

## 环境要求

- 仅在代码辅助重建或图片对比时需要 Python 3.9+，并安装 [`python-pptx`](https://python-pptx.readthedocs.io/) 和 [`Pillow`](https://pillow.readthedocs.io/)
- **PNG 导出**：Windows + 本机 PowerPoint（COM 自动化）。其他平台可用任意 office 渲染器（如 LibreOffice `soffice --convert-to png`）——skill 会说明该限制并继续执行。

## 仓库结构

```
SKILL.md                        # skill 定义（工作流 + 重建规则）
agents/openai.yaml              # Codex 接口元数据
references/quality-checklist.md # 交付前验收清单
scripts/export_ppt_slide.ps1    # PPTX 幻灯片 -> PNG（PowerPoint COM）
scripts/compare_pngs.py         # 并排对比图 + 差异指标
```

## 许可证

[MIT](LICENSE)

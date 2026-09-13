# unflatten-ppt

**English** | [简体中文](README.zh-CN.md)

Turn flat PNG diagrams into fully editable PowerPoint slides — every box, arrow, and label becomes a native shape, not a pasted bitmap.

`unflatten-ppt` is an **agent skill** for coding agents such as [Codex](https://github.com/openai/codex) and [Claude Code](https://claude.com/claude-code). Give the agent a raster image of a technical figure — a paper diagram, an architecture sketch, a flowchart, a screenshot — and it rebuilds the figure as a `.pptx` slide made of native PowerPoint objects: text boxes, shapes, connectors, tables, and groups. Then it exports the slide back to PNG, compares it against the reference image, and iterates until the reconstruction matches.

## Why

Pasting a PNG onto a slide gives you a picture of a diagram. Rebuilding it gives you the diagram itself:

- **Edit anything** — reword a label, recolor a block, reroute an arrow, without touching the original drawing tool.
- **Reuse everything** — copy shapes into other slides, restyle them to match your deck's theme.
- **Iterate on ideas** — a generated concept figure becomes a draft you can discuss and refine, not a dead end.

## How it works

1. **Inspect** — the agent reads the source PNG: regions, text blocks, shapes, arrows, colors, repeated structures. Pixel coordinates become the layout coordinate system.
2. **Reconstruct** — rebuild every important element as an editable PPT object, either directly in PowerPoint or with `python-pptx` when reproducible generation is useful. The editable `.pptx` is required; generation code is optional.
3. **Export** — `scripts/export_ppt_slide.ps1` renders the slide to PNG via PowerPoint COM automation.
4. **Compare** — `scripts/compare_pngs.py` produces a side-by-side comparison and RMS/mean-difference metrics.
5. **Iterate** — layout first, then text, then connectors, until there are no structural errors. `references/quality-checklist.md` gates the final delivery.

## Install

### Claude Code

```bash
git clone https://github.com/Feng-Y-28/unflatten-ppt.git ~/.claude/skills/unflatten-ppt
```

The skill triggers automatically on requests like *"convert this PNG into an editable PPT"* or *"make every element editable"*.

### Codex

Clone into your Codex skills directory (e.g. `~/.codex/skills/`); `agents/openai.yaml` provides the interface metadata.

## Requirements

- For code-assisted rebuild or image comparison only: Python 3.9+ with [`python-pptx`](https://python-pptx.readthedocs.io/) and [`Pillow`](https://pillow.readthedocs.io/)
- **PNG export**: Windows with a local PowerPoint installation (COM automation). On other platforms, use any office renderer (e.g. LibreOffice `soffice --convert-to png`) — the skill states the limitation and continues.

## Repository layout

```
SKILL.md                        # the skill definition (workflow + reconstruction rules)
agents/openai.yaml              # Codex interface metadata
references/quality-checklist.md # pre-delivery acceptance checklist
scripts/export_ppt_slide.ps1    # PPTX slide -> PNG via PowerPoint COM
scripts/compare_pngs.py         # side-by-side comparison + diff metrics
```

## License

[MIT](LICENSE)

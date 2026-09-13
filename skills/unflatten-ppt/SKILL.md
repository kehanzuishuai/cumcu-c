---
name: unflatten-ppt
description: >
  Rebuild an already-defined structured Flowchart Brief or raster diagram reference as a native, editable PowerPoint slide, then export, compare, and iterate. Use for CUMCM paper flowcharts and similar fixed-logic diagrams whose text, shapes, and connectors must remain editable. Do not use to interpret the modeling problem, decide whether a flowchart is needed, or redesign the paper's logic.
---

# Flowchart Reference to Editable PPT

Rebuild a fixed-logic reference image as an editable PowerPoint slide using native text boxes, shapes, connectors, arrows, tables, and grouped layout elements. Do not satisfy the request by pasting the reference as a slide-sized image or by replacing major logical regions with bitmap crops.

## Scope Boundary

- Start only after the user or an upstream workflow has fixed the diagram logic.
- Reconstruct the supplied nodes, labels, grouping, and dependencies; do not add models, delete steps, reinterpret the problem, or decide whether the paper needs a flowchart.
- For a CUMCM pipeline, accept `flowchart_briefs_all.md` in the schema at `../_shared/cumcm/interfaces.md`; treat node IDs, labels, roles, edge directions, interface IDs, and reading order as frozen logic.
- When both a raster and a Flowchart Brief exist, use the Brief for semantics and the raster for layout/style. Stop on a real conflict instead of silently choosing one.
- If a label or arrow is unreadable or genuinely ambiguous, preserve the visible structure and ask for confirmation rather than inventing logic.
- For a CUMCM paper flowchart, read `references/cumcm-flowchart-style.md` before construction and again before final QA.

## Core Workflow

1. Inspect the reference dimensions and content.
   - Identify the page size, major regions, text blocks, shapes, arrows, colors, and repeated structures.
   - Use the image pixel coordinate system as the first layout coordinate system.
   - Separate certain visual facts from unreadable or ambiguous details; do not treat OCR as authority.

2. Generate an editable PPT reconstruction.
   - Use native PowerPoint editing when direct manual construction is clearer; use `python-pptx` when deterministic regeneration is useful. Code is optional, not an entry requirement.
   - Set the slide size to match the reference aspect ratio unless the requested paper placement requires a different canvas.
   - Map pixels to EMUs with a simple helper such as `EMU_PER_PX = 9144` when using 96 dpi coordinates.
   - Recreate all major text, geometry, and relationships as native PowerPoint objects.
   - Always keep the editable `.pptx`; keep generation code only when code was actually used.

3. Export the slide and compare.
   - Use `scripts/export_ppt_slide.ps1` on Windows when PowerPoint is installed.
   - Use `scripts/compare_pngs.py` for a side-by-side comparison and basic image-difference metrics.
   - If PowerPoint export is unavailable, use an available office renderer and state the limitation.

4. Iterate.
   - Fix layout first: canvas, outer frame, main blocks, spacing, and section boundaries.
   - Then fix text: transcription, fonts, sizing, wrapping, alignment, and clipping.
   - Then fix connectors: direction, endpoints, routing, crossings, thickness, and dash style.
   - Finally fix restrained styling without changing the diagram's logic.
   - Repeat export and comparison until there are no obvious structural or actual-size reading errors.

5. Deliver artifacts.
   - Deliver the editable `.pptx` and retain generation code only when used.
   - Keep the latest export and comparison image when iterative comparison was requested.
   - For CUMCM use, report the checked paper insertion size, export format, and any known deviations.
   - For a CUMCM pipeline, provide the flowchart asset record for `figure_manifest.json`: `source` must point to the editable `.pptx`, while `script` is optional; set `human_approved: true` only after a team member confirms the node/arrow logic.

## Reconstruction Rules

- Editable means native PowerPoint objects, not one flattened image.
- Preserve diagram semantics and labels over pixel-perfect ornamentation.
- Major text boxes, shapes, and connecting lines must remain independently editable.
- Use native table/grid cells for matrices, queues, register files, and repeated boxes.
- Use native connectors for arrows whenever possible; patch OOXML only when the required arrowhead cannot be expressed reliably by `python-pptx`.
- Preserve identifiers exactly, including underscores, parentheses, operators, array indices, and capitalization.
- A small bitmap is allowed only for irreducible photographic or textured content, never for a major flowchart region or text-bearing panel.
- Keep generated filenames descriptive and versioned, such as `flowchart_editable.pptx`, `flowchart_export_r1.png`, and `flowchart_compare_r1.png`.

## References and Scripts

- Read `references/cumcm-flowchart-style.md` only for CUMCM or paper-insertion flowcharts; it defines the font, palette, native-editability, and A4 Visual QA contract.
- Read `references/quality-checklist.md` before every final delivery.
- Read `../_shared/cumcm/C题规范.md` as the sole S1 standard and `../_shared/cumcm/interfaces.md` for Flowchart Brief/manifest fields; neither changes the reconstruction workflow.
- `scripts/export_ppt_slide.ps1`: export one PowerPoint slide to PNG through local PowerPoint COM automation.
- `scripts/compare_pngs.py`: create a side-by-side comparison and print RMS/mean-difference metrics.

## Typical User Requests

- "Rebuild this fixed CUMCM flowchart as an editable PPT without changing its logic."
- "Make every node, label, and arrow editable; do not paste the whole image."
- "Export each version, compare it with the reference, and iterate at its paper insertion size."

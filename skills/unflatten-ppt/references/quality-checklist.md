# Quality Checklist

Use this checklist before final delivery.

## Editability

- The slide is not a single pasted PNG.
- Major text is editable text.
- Major geometry is editable shapes.
- Arrows and lines are editable connectors or line shapes.
- Repeated structures are editable cells/shapes, not cropped image fragments.

## Visual Match

- Slide aspect ratio matches the reference PNG.
- Outer frame and main regions align with the reference.
- Large blocks, tables, circles, callouts, and arrows are in the right relative positions.
- Text does not overflow or clip.
- Arrow direction is correct.
- Dashed/solid line styles are visually distinguishable.
- Colors are close enough to preserve grouping and semantics.

## Iteration Evidence

- At least one exported screenshot exists.
- A side-by-side comparison exists when requested.
- The latest export is named with the latest iteration number.
- Known deviations are stated clearly in the final response.

## Practical Acceptance

Prioritize correctness in this order:

1. Diagram meaning and labels.
2. Editability of all important elements.
3. Layout and arrow routing.
4. Font sizing and text wrapping.
5. Color polish and shadows.

## CUMCM Paper Flowcharts

When the target is a CUMCM paper flowchart, also run the complete gate in `references/cumcm-flowchart-style.md` at the intended A4 paper insertion size. Final delivery must confirm:

- Chinese uses 宋体 and English/digits use Times New Roman.
- The diagram uses only two to four low-saturation semantic colors and one consistent shape/connector system.
- Major text, shapes, group frames, and connectors are independently editable PowerPoint objects.
- No text overflow, wrong or detached arrow, frame penetration, node overlap, ambiguous crossing, ineffective whitespace, or unreadable final-size label remains.
- The final paper export is clear; a raster fallback is at least 300 ppi at the actual physical size.
- No neon, 3D, strong gradient, heavy shadow, or AI-infographic decoration remains.

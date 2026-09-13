# CUMCM Flowchart Style and Actual-Size QA

Read this reference only when rebuilding a CUMCM paper flowchart or another flowchart intended for insertion into an A4 academic paper. It styles an already-fixed logical diagram; it does not decide whether a flowchart is needed, select models, add or remove nodes, or redesign dependencies.

## 1. Entry Contract

Before reconstruction, confirm that the reference or upstream specification already fixes:

- node labels and hierarchy;
- arrow direction and dependency meaning;
- the distinction between a total workflow and a per-question workflow;
- the intended paper placement or approximate insertion width.

When any of these is unclear, mark the uncertainty and ask for confirmation. Do not repair a questionable modeling relationship through visual redesign.

## 2. Native-Editability Contract

- Rebuild all major text as PowerPoint text runs or text boxes.
- Rebuild nodes, group frames, decision diamonds, separators, and repeated cells as native shapes or tables.
- Rebuild dependencies as native connectors or line shapes with editable endpoints and arrowheads.
- The reference image may be retained as a separate comparison artifact, but it must not cover the reconstructed slide or serve as a slide-sized background.
- Do not use screenshot crops for text-bearing panels or grouped logical regions.
- Use a small raster object only when the reference contains irreducible photographic content; keep it independent from the logical structure.

## 3. CUMCM Paper Style Tokens

### 3.1 Typography

- Chinese text: `宋体` (`SimSun`).
- English letters, abbreviations, and Arabic numerals: `Times New Roman`.
- Split mixed Chinese/Latin content into separate runs when needed so both font rules survive PowerPoint fallback.
- Keep node labels concise, normally one or two lines. Reflow or shorten only with user-approved wording; do not shrink long paragraphs until they merely fit.
- Use one text hierarchy per diagram: main stage, ordinary node, and secondary annotation. Avoid unrelated font-size changes between adjacent nodes.
- Judge the font at the final paper insertion size, not only on the full-screen PowerPoint canvas. As a practical target, keep ordinary node text around 9–11 pt after insertion and avoid going below 8 pt; if it does not fit, revise layout or confirm wording instead.

### 3.2 Low-Saturation Palette

Use a white background and only two to four low-saturation semantic colors. A restrained default set is:

| Role | Line/accent | Light fill | Typical use |
| --- | --- | --- | --- |
| Primary | `#4F6D7A` | `#E7EDF0` | main workflow and primary nodes |
| Secondary | `#789995` | `#E8EFED` | auxiliary processing or validation |
| Support | `#B09A68` | `#F1EDE3` | inputs, constraints, or intermediate evidence |
| Emphasis | `#A66D6A` | `#F1E7E6` | one genuinely important warning or terminal result |

- Use only the colors required by the diagram's semantics; do not use all four merely for variety.
- Keep the same semantic role in the same color throughout one paper.
- Prefer dark neutral text such as `#273238` and restrained connector gray such as `#59636B`.
- Do not use neon colors, rainbow palettes, strong gradients, glass effects, or decorative color changes without semantic meaning.

### 3.3 Shapes and Connectors

- Use a small technical vocabulary: rectangle, rounded rectangle, decision diamond, group frame, and connector.
- Use one rounded-rectangle family for ordinary nodes; reserve diamonds for real decisions or branching conditions.
- Keep corner treatment, border color, border width, arrowhead style, and internal padding consistent across the diagram.
- Use approximately 1.0–1.5 pt lines at final paper scale; increase only when downscaling would otherwise make them disappear.
- Prefer one arrowhead family. Dashed connectors are allowed only for a defined secondary or optional relationship.
- Connect at the intended shape boundary and route around text and nodes. Never let an arrow terminate ambiguously near two nodes.
- Default to no shadow. If a slight shadow is needed to separate overlapping groups, keep it subtle and consistent; never use heavy shadows, glow, bevel, or 3D extrusion.

### 3.4 Layout

- Preserve the reference logic and reading order before optimizing spacing.
- Use alignment and equal-spacing tools for repeated nodes; keep comparable nodes at comparable sizes.
- Let whitespace separate logical groups, but remove large empty bands that do not encode hierarchy or improve reading.
- Avoid decorative icons, characters, ribbons, pseudo-dashboard cards, or obvious AI-infographic ornaments.
- A total workflow should emphasize inter-question data transfer; a per-question workflow should emphasize the fixed input, processing/model, solution, validation, and output chain supplied by the reference.

## 4. A4 / Actual-Insertion-Size Visual QA

Run this QA after the ordinary reference comparison. The reference comparison checks reconstruction fidelity; actual-size QA checks whether the reconstructed figure works inside the paper.

1. Determine the intended insertion width from the actual paper or template. If it is not fixed, test both a typical single-column/partial-width placement around 8 cm and a full-text-width placement around 15–16 cm.
2. Export or place the figure at that physical size on an A4 proof page. Inspect it at 100% and, when possible, print or render the complete PDF page.
3. Check every item below; a full-screen PowerPoint inspection is not a substitute.

### Required checks

- **Text overflow:** no clipped glyphs, hidden lines, accidental wrapping, or text touching shape borders.
- **Arrow correctness:** every arrow starts and ends at the intended nodes; no reversed arrow, detached endpoint, frame penetration, or connector through text.
- **Crossings and overlap:** no node overlap, label collision, ambiguous line crossing, or arrowhead hidden behind a shape.
- **Whitespace:** no unexplained empty band or oversized canvas margin; remaining whitespace must express grouping or improve reading order.
- **Readability:** Chinese, English, digits, subscripts, and symbols remain legible at the actual insertion size without zooming.
- **Consistency:** fonts, fills, borders, corner treatment, line widths, arrowheads, and node padding remain uniform.
- **Export clarity:** prefer SVG, EMF, or PDF when the target workflow supports it. If raster export is unavoidable, use at least 300 ppi at the final physical size and inspect the final paper PDF for blur or broken thin lines.
- **Editability:** reopen the delivered `.pptx` and confirm that representative major labels, nodes, group frames, and connectors can be selected and edited independently.

### Failure handling

- If text is unreadable, shorten only with approval, enlarge the insertion size, reflow the layout, or split a genuinely over-dense diagram; do not hide the failure by shrinking fonts.
- If arrows cross frames or nodes, adjust connector anchors and routing before changing the logical order.
- If the page has large ineffective whitespace, tighten the canvas or redistribute existing nodes without inventing content.
- If visual similarity conflicts with native editability or paper readability, preserve logic and editability first, then actual-size readability, then decorative similarity.

## 5. Delivery Gate

A CUMCM reconstruction is ready only when:

- the logical content matches the fixed reference;
- all major logical elements are native and independently editable;
- the exported comparison has no obvious structural mismatch;
- the A4 actual-size proof passes every required check;
- the final file contains no neon, 3D, strong gradient, heavy shadow, or AI-infographic decoration.

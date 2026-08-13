# Prompt templates

Use only the sections relevant to the task. Replace brackets; do not leave placeholders in a final prompt.

## A. Generate or redesign a scientific figure

```text
Use case: scientific-educational
Asset type: publication-ready [framework / architecture / method] figure
Input images: Image 1: [edit target / structural reference]

Primary request:
Create or redesign [figure purpose]. Preserve the scientific logic while improving layout, hierarchy, typography, arrows, spacing, and color consistency.

Scientific invariants:
- Stage order: [ordered stages]
- Branches: [branch names and mapping]
- Symbols/formulas/dimensions, verbatim: [list]
- Required labels/caption, verbatim: [list]
- Relationships that must remain unchanged: [list]

Canvas and layout:
- [orientation and aspect ratio]
- [major container proportions]
- [grid, margins, gutters]
- [flow direction]
- [parallel-row geometry]

Visual grammar:
- [flat vector-like / shallow isometric cuboids]
- [shape rules]
- [connector rules]
- [typography]
- [palette with hex values]

Definition-driven icons/plots:
- [concept]: [function to encode and required silhouette]

Constraints:
- Preserve the model logic exactly.
- Keep all required text readable and correctly spelled.
- Use consistent arrowheads, corner radii, and branch colors.
- No overlaps, clipped labels, crossed connectors, extra modules, or watermark.

Avoid:
[misleading icons, repeated plots, glossy 3D, presentation-slide styling, formula stacking, tiny type]
```

## B. Targeted correction

```text
Use case: precise-object-edit
Input images: Image 1 is the edit target.

Primary request:
Change only [localized defect]. Keep [all invariants] unchanged.

Required correction:
- [exact replacement or geometry]
- [scientific definition/function]
- [text/symbols verbatim]

Constraints:
Change only [target region]; preserve layout, colors, typography, arrows, caption, dimensions, and all other modules. No extra labels or watermark.
```

## C. Editable reconstruction specification

```text
Use [Visio / vector editor] to rebuild the figure using native editable shapes.

Reference image:
[absolute path]

Goal:
Match the reference's scientific content and visual hierarchy. Do not use the raster image as the final figure.

Page:
- Size/orientation: [value]
- Margins/grid: [value]
- Layers: Reference, Containers, Modules, Operators, Connectors, Text

Layout:
- Major regions and proportions: [values]
- Repeated rows/columns: [geometry]
- Caption/legend position: [value]

Reusable shape masters:
- [container]
- [2D card]
- [3D cuboid definition]
- [plot card]

Style tokens:
- Colors: [role = hex]
- Fonts/sizes: [values]
- Stroke weights: [values]
- Arrowheads: [values]

Objects and text:
[stage-by-stage inventory with exact labels, symbols, formulas, and dimensions]

Scientific plot requirements:
[definition-driven plot specifications]

Editing rules:
- Keep operands and operators as separate objects.
- Glue connectors to connection points.
- Group modules locally, never flatten the whole page.
- Remove or hide the temporary reference image.

Acceptance criteria:
[visual, scientific, editability, and export checks]

Outputs:
[VSDX/SVG/PDF/PNG paths and DPI]
```

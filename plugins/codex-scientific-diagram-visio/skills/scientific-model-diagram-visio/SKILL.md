---
name: scientific-model-diagram-visio
description: Rebuild, modify, audit, and export publication-ready scientific model diagrams as native editable Microsoft Visio (.vsdx) files. Use when Codex must turn a verified model/code/paper specification or a generated reference image into Visio shapes; repair an existing VSDX; enforce horizontal aligned branches, readable typography, non-overlapping connectors and objects, consistent 3D cuboids, correct equations and tensor dimensions; or export and verify PDF/300-DPI PNG while preserving independent editability.
---

# Scientific Model Diagram Visio

Create or revise a scientific architecture figure in Microsoft Visio using native editable objects. Treat scientific correctness, readable geometry, and editability as separate gates; pass all three before delivery.

## Choose the mode

- **Full rebuild:** construct the requested page from a verified model contract and visual reference.
- **Local revision:** back up the VSDX and change only the named stages, symbols, dimensions, connectors, typography, or spacing.
- **Audit/export:** inspect an existing VSDX, correct only authorized defects, reopen it, and export PDF plus 300-DPI PNG.

If the source logic has not been reconciled across code, configuration, manuscript, and old figures, first use `scientific-model-diagram-prompting` or perform the evidence pass in [handoff-contract.md](references/handoff-contract.md). Never infer a fusion operation or tensor dimension from visual appearance alone.

## Mandatory workflow

### 1. Freeze the target model

Create a model contract containing stage order, tensor shape at every boundary, operation semantics, learnable parameters, fusion rule, classifier widths, class count, and exact labels. Cite source files and line numbers when code or manuscript is available.

Apply this evidence priority unless the user explicitly chooses another target:

1. successfully constructed or executed model;
2. training implementation and experiment configuration;
3. manuscript equations and method text;
4. old VSDX or raster figure;
5. generated visual reference.

Stop and report unresolved contradictions before drawing when they would materially change the architecture. Read [handoff-contract.md](references/handoff-contract.md) for the required handoff schema.

### 2. Protect the source and isolate work files

- Resolve the source VSDX and exact output paths before editing.
- Use the user's named work directory. If none is given, create a sibling `_visio_work` directory.
- Keep screenshots, reference rasters, timestamped backups, temporary exports, QA renders, and helper output inside that work directory.
- Back up the source VSDX before the first mutation. Do not overwrite the only copy.
- Remove unrelated pages only when the user authorized it and after recording the page names in the work log.

### 3. Control Microsoft Visio deliberately

Use the `computer-use` Windows automation skill when available. Before the first UI action in a fresh session, initialize its runtime and read `sky.documentation("guidance")`; read `sky.documentation("confirmations")` before actions that may require confirmation. Target the Visio window by application/window identity and inspect screenshots rather than using blind coordinate sequences.

Open the VSDX in Microsoft Visio. Do not replace Visio execution with a raster, SVG screenshot, PowerPoint, or generic diagram editor when the user requested Visio.

Read [visio-execution.md](references/visio-execution.md) before controlling Visio.

### 4. Build geometry before detail

Set page size, orientation, margins, layers, stage containers, row baselines, and connector corridors before placing modules. Use a coordinate plan and repeated geometry for parallel branches.

Create reusable native masters or grouped shapes for repeated components. Keep operands, operators, dimensions, and connectors independent. A 3D cuboid must remain a group of editable front/top/side faces; never flatten the page.

Use [layout-and-style.md](references/layout-and-style.md) for layout tokens, font sizes, cuboid construction, connectors, grouping, and the user's publication standards.

### 5. Draw in passes

Perform these passes in order:

1. page, layers, and containers;
2. repeated row guides and connector corridors;
3. modules and reusable cuboids;
4. mathematical operands and independent operators;
5. connectors glued to connection points;
6. labels, dimensions, legend, and caption;
7. alignment, distribution, and local grouping;
8. visual cleanup at preview scale and original detail.

After each major pass, capture a screenshot in the work directory. If a local revision is requested, change only the affected region and re-check its incoming and outgoing connections.

### 6. Enforce routing and readability

- Prefer perfectly horizontal branch lines and orthogonal bends.
- Reserve empty connector lanes before placing text.
- Glue every functional connector to explicit connection points.
- Never run a line through text, an operator, a cuboid, a plot card, or another arrowhead.
- Keep parallel rows equal in height and spacing; use Align and Distribute rather than eye-balling.
- Shorten labels or widen containers before reducing text below the minimum size.
- Inspect both a full-page preview and a zoomed screenshot. Text that is only legible when zoomed in fails.

### 7. Save, reopen, and verify editability

Save the final VSDX to the requested path, close it, and reopen it in Visio. Individually select and edit at least:

- one face inside a grouped cuboid;
- one mathematical operator or symbol;
- one connector and both of its glued endpoints;
- one stage label.

Confirm that the reference image is removed or hidden on a locked Reference layer, unrelated pages are absent when requested, and no object became a single full-page bitmap.

Run `scripts/inspect_vsdx.py` after saving. This static check supplements but never replaces visual inspection.

### 8. Export and perform final QA

Export PDF and PNG from Visio. For a 16 × 9 inch page, a 300-DPI raster is at least 4800 × 2700 pixels. Inspect both exports for clipping, font substitution, thin/broken lines, shadow artifacts, and page-boundary errors.

Run the complete [qa-checklist.md](references/qa-checklist.md). Do not deliver while any scientific-fidelity, overlap, connector, text-integrity, export, or editability item fails.

## Local revision rules

- Preserve unaffected shapes, styles, layers, and page settings.
- Back up before editing and save the revision under a new version until accepted.
- Diagnose the smallest affected subgraph: incoming connector, edited objects, outgoing connector.
- Re-route adjacent connectors after moving any object.
- Re-run full-page preview QA; a local fix can create a global collision.

## Required handoff

Report:

1. target architecture and evidence basis;
2. source, backup, work-directory, and output paths;
3. pages removed or retained;
4. VSDX, PDF, and PNG paths plus PNG pixel size/DPI;
5. static VSDX inspection summary;
6. reopen/editability tests performed;
7. any remaining uncertainty.

Do not claim success merely because the file saved or exported.

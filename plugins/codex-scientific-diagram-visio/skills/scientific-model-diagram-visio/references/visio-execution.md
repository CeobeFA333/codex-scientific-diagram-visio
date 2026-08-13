# Microsoft Visio execution workflow

## 1. Initialize application control

When the Computer Use plugin is available:

1. initialize `@oai/sky` once in the JavaScript session;
2. read `sky.documentation("guidance")` before controlling Visio;
3. read `sky.documentation("api")` when method signatures are needed;
4. read `sky.documentation("confirmations")` before deciding whether an action needs confirmation;
5. target the Microsoft Visio window by application/window identity;
6. capture a screenshot before editing and after every major pass.

Do not rely on long blind click sequences. Re-observe the window after dialogs, zoom changes, page switches, paste operations, exports, or unexpected focus changes.

## 2. Preflight

- Confirm Microsoft Visio is installed and can open the source.
- Resolve source, backup, work, and final output paths.
- Copy the source to a timestamped backup before mutation.
- Inventory pages and record which page will be retained.
- If the document is already open, confirm the active document and page before editing.
- Set AutoSave expectations; do not let an unverified intermediate overwrite the source.

## 3. Page and layers

Recommended page for a wide journal architecture figure:

- landscape, 16 × 9 inches;
- white background;
- drawing scale 1:1;
- Snap, Glue, Dynamic Grid, and connection points enabled;
- layers: `Reference`, `Stage Containers`, `3D Blocks`, `Statistical Plots`, `Operators`, `Connectors`, `Labels`.

Place a raster reference only on the locked `Reference` layer. Remove or hide it before delivery.

## 4. Coordinate plan

Before detailed shapes, define:

- page margins;
- top title band;
- main diagram band;
- bottom legend band;
- caption band;
- stage x-ranges and gutters;
- repeated branch y-baselines;
- reserved horizontal and vertical connector corridors.

Use Visio Size & Position, Align, and Distribute commands for repeated geometry. Do not position four branches independently by eye.

## 5. Reusable shapes

Create reusable native shapes for:

- rounded stage container;
- 3D cuboid group with editable front/top/right faces;
- 2D operator text (`×`, `+`, `Σ`, `‖`);
- dimension label;
- statistical plot card;
- classifier block;
- output class marker.

Use duplicate-and-relabel for repeated modules so perspective, depth, stroke, and text padding remain identical.

## 6. Connector discipline

- Add explicit connection points at stable module edges.
- Glue both ends of functional connectors.
- Prefer straight horizontal connectors for parallel branches.
- Use orthogonal bends only in reserved corridors.
- Keep branch lines on the `Connectors` layer and behind blocks but never behind text.
- Avoid placing a junction on a container border.
- After moving a shape, inspect and re-glue adjacent connectors.
- Use consistent arrowheads and line widths; branch colors may identify branch lineage.

## 7. Text and formulas

- Use text boxes for operators and labels that must remain independent.
- Use Cambria Math for Greek letters and equations.
- Use real subscripts, superscripts, squared symbols, and primes; do not fake them with misaligned plain characters.
- Keep dimensions directly below the block they describe.
- Increase container width or wrap at deliberate line breaks before shrinking text.
- Use the Text Block tool to fix padding and alignment without moving the underlying shape.

## 8. Grouping and layers

- Group each cuboid locally while preserving editable internal faces.
- Group each logical module locally: block + label + dimension, excluding connectors.
- Do not group the entire page.
- Keep connectors outside module groups so routing remains editable.
- Assign groups and shapes to their semantic layers.

## 9. Full rebuild sequence

1. retain/create the target page and remove authorized extra pages;
2. configure page and layers;
3. draw containers and guides;
4. build one verified master of each repeated shape;
5. duplicate modules across equal row baselines;
6. add labels and dimensions;
7. add and glue connectors;
8. align/distribute and remove guides;
9. add legend and caption;
10. run preview-scale cleanup;
11. save, close, reopen, and test editability;
12. export and inspect PDF/PNG.

## 10. Local revision sequence

1. back up and open the correct page;
2. identify the smallest affected subgraph;
3. record current object positions and neighboring connection points;
4. edit or replace only authorized objects;
5. align the changed row with unchanged rows;
6. re-route and re-glue incoming/outgoing connectors;
7. inspect the whole page for new collisions;
8. save as a versioned revision until accepted.

## 11. Save and export

- Save the editable source as `.vsdx`.
- Close and reopen the saved path before export.
- Export PDF using the full page, not the current selection.
- Export PNG at 300 DPI or greater. A 16 × 9 inch page requires at least 4800 × 2700 pixels at 300 DPI.
- Save QA screenshots and exports inside the work directory; place final deliverables at the user-specified paths.

Do not report completion until the reopened VSDX and both exports have been inspected.

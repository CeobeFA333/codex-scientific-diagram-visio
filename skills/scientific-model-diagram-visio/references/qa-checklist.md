# Visio scientific figure acceptance checklist

Run after construction, after reopening the VSDX, and after exporting.

## Scientific fidelity

- [ ] Figure target is explicitly identified: executed code, manuscript, or proposed revision.
- [ ] Stage order and operation semantics match the frozen model contract.
- [ ] Every tensor/vector dimension is correct at both ends of each arrow.
- [ ] Matrix orientation matches the declared row/column convention.
- [ ] Fusion is correctly represented as concatenation, sum, weighted sum, or attention.
- [ ] Learnable weights and sample-dependent weights are not confused.
- [ ] Classifier widths, activations, class count, and labels match the target.
- [ ] Greek letters, subscripts, superscripts, primes, and equations are exact.

## Page and object structure

- [ ] Only requested pages remain.
- [ ] Page size, orientation, scale, margins, and white background are correct.
- [ ] Semantic layers exist and contain the intended objects.
- [ ] Temporary reference image is removed or hidden on a locked Reference layer.
- [ ] Repeated cuboids use one perspective, depth, outline, and light direction.
- [ ] Operators are independent 2D objects, not embedded in operand blocks.
- [ ] Logical modules are locally grouped; the entire page is not flattened/grouped.

## Alignment and spacing

- [ ] Parallel branches are perfectly horizontal and equally spaced.
- [ ] Repeated blocks have identical dimensions and baseline anchors.
- [ ] Stage gutters and outer margins are consistent.
- [ ] Dense junctions have sufficient whitespace.
- [ ] Legend and caption do not intrude into the main flow.

## Connectors

- [ ] Every functional connector is glued at both ends.
- [ ] Arrow direction matches data flow.
- [ ] Lines do not cross text, symbols, plots, blocks, borders, or arrowheads.
- [ ] Orthogonal bends use reserved corridors and do not create ambiguous junctions.
- [ ] Four branch connectors enter and leave corresponding modules consistently.
- [ ] Moving a connected block causes the connector endpoint to follow.

## Typography and visual quality

- [ ] Full-page preview text is readable without zooming.
- [ ] No required text is below 9 pt.
- [ ] No clipping, overflow, unintended wrapping, duplicated label, or spelling error exists.
- [ ] Mathematical glyphs render correctly in Cambria Math or equivalent.
- [ ] Shadows are subtle and do not muddy edges or text.
- [ ] Color contrast is sufficient and labels supplement color coding.
- [ ] Statistical plots remain functionally distinct at preview size.

## Reopen and editability tests

- [ ] Saved VSDX closes and reopens without repair warnings.
- [ ] One cuboid can be ungrouped or entered and an internal face selected.
- [ ] One mathematical operator can be selected and edited independently.
- [ ] One connector can be selected, rerouted, and remains glued.
- [ ] One label can be edited without raster artifacts.
- [ ] The page is not a full-page bitmap.
- [ ] `inspect_vsdx.py` reports expected pages, native shapes, connectors, and text.

## Export tests

- [ ] PDF uses the intended page bounds and contains no extra blank pages.
- [ ] PNG is at least 300 DPI; 16 × 9 inches means at least 4800 × 2700 pixels.
- [ ] Exported text, math symbols, strokes, arrowheads, and shadows match the reopened VSDX.
- [ ] No page-edge clipping or font substitution is visible.
- [ ] PDF and PNG are inspected at full page and zoomed detail.

Any unchecked scientific, connector, collision, text, or editability item blocks delivery.

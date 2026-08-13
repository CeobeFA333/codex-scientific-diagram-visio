# Scientific model figure QA

Run this checklist at original image detail after every generation or substantial edit.

## Scientific fidelity

- [ ] Stage order matches the source/model description.
- [ ] No module, branch, input, or output was added or removed unintentionally.
- [ ] Symbols, subscripts, superscripts, primes, equations, and dimensions are exact.
- [ ] Arrow direction and fusion/projection relationships remain correct.
- [ ] Each icon or miniature plot reflects the concept's definition/function.
- [ ] Distinct statistics do not reuse a misleading identical curve.

## Layout

- [ ] Major containers follow the intended proportions.
- [ ] Repeated branches share identical geometry and spacing.
- [ ] Text, equations, and icons have sufficient breathing room.
- [ ] Connectors do not cross, collide, or pass behind labels.
- [ ] Caption and legend are separated from the main flow.

## Visual consistency

- [ ] One coherent flat or isometric grammar is used.
- [ ] Cuboids share perspective, depth, shading, and light direction.
- [ ] Branch colors remain consistent across stages.
- [ ] Typography hierarchy and stroke weights are consistent.
- [ ] Color contrasts remain readable and are not the only semantic cue.

## Text integrity

- [ ] Required text is verbatim and legible.
- [ ] No clipped, duplicated, misspelled, or invented labels appear.
- [ ] Greek letters and mathematical glyphs are not visually corrupted.
- [ ] Small chart axes and legends remain readable at publication scale.

## Reconstruction readiness

- [ ] Each visual component can be described as a native vector shape.
- [ ] Operators are separable from data/module blocks.
- [ ] Shape grouping boundaries are clear.
- [ ] Palette, font, line, and dimension tokens are recorded.
- [ ] Acceptance criteria and output paths are specified.

## Iteration decision

If any scientific-fidelity item fails, revise before aesthetic polishing. If only one localized visual item fails, issue a targeted edit prompt rather than regenerating the entire figure.

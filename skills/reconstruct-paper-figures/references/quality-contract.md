# Publication figure quality contract

## Typography

- Required Latin font: Times New Roman.
- Required size when specified by the client: 8.5 pt in the final physical artwork, not merely an equivalent apparent size after scaling.
- Text must remain live `<text>` in SVG and Type objects in Illustrator.
- Do not outline or expand required text.
- Preserve rotation, color, weight, italic style, subscript/superscript, and alignment.
- Flag unsupported Chinese glyphs and record the approved fallback font.

## Geometry

- Convert 1 mm to 2.83465 pt for a literal stroke-width requirement.
- Rebuild axis/tick/marker lines removed by masking.
- Use consistent joins and caps. Prefer butt caps for axes and square/round caps only when the source requires them.
- Keep repeated panel borders and separators aligned to a shared grid.

## Raster cleanup

- Inspect the cleaned base with the vector overlay hidden.
- Reject visible glyph ghosts, antialiasing halos, repeated clone seams, blurred rectangles, broken scale bars, broken grids, or altered scientific content.
- Keep texture edits local. Do not apply generative fill across scientific measurements or features whose interpretation matters.
- Require byte-identical protected scientific regions when cleanup is intended to affect only exterior labels or review markup.
- For actual pixel cleanup, require a hash-bound `safe-text-cleanup-v1` plan, an opaque full-canvas binary mask, and exact decoded-RGBA proof that `changed_pixels_outside_mask == 0`. Use `[x, y, width, height]` consistently for cleanup and protected rectangles.
- Rerun `audit_text_cleanup.py` independently on the produced source/cleaned/mask files. Treat residue and halo checks as conservative screening; a machine pass never replaces review at 200%-400% with vector overlays hidden.
- Do not color-filter a region that may contain genuine curves, markers, contours, heatmap colors, stains, or spectral peaks.
- Treat `annotation_occlusion_masks` as an opt-in exception for immutable evidence atoms, not as the default cleanup method. The recipe must lock the normalized source crop SHA-256; the builder must prove that the referenced source and cleaned crops have identical normalized pixels and emit matching source/embedded crop digests.
- Permit only a local solid `plate` or `narrow_mask` on a visually uniform patch. Reject masks outside the referenced atom, above the declared area fraction, intersecting a protected region, or lacking a live-text replacement.
- Keep each occlusion in the `annotation-occlusion-masks` group below its replacement elements. A pending mask may be rendered for review, but the audit must fail until `old_annotation_risk=confirmed_occluded`, `approval_status=approved`, and `approved_by` plus `approval_note` are present.
- Inspect immutable evidence as two toggles: first the unaltered raster alone, then raster plus occlusion plate with replacement elements hidden. At 400%, reject texture discontinuity, glyph halo outside the plate, covered measurement marks, or a plate that changes the scientific reading.

## SVG audit

- XML parses successfully.
- Every object ID is unique.
- No scripts, event handlers, remote `<image>`, external `<use>`, `feImage`, CSS `url()`, or other external references exist.
- Required text objects carry Times New Roman and an effective 8.5 pt size. For a 96 dpi SVG user space imported into Illustrator, emit 11.3333 CSS px so Illustrator reads 8.5 pt; verify the resulting Type object instead of trusting the raw attribute token.
- Raster images are embedded and identify their source file.
- For every declared annotation occlusion, validate the mask rectangle against its recipe-derived source and canvas bounds, the maximum area fraction, parent layer, draw order, approval/risk metadata, referenced replacement IDs, and the embedded PNG pixel digest.
- Canvas width/height use physical units or the reconstruction spec records an unambiguous physical scale.
- Every required object ID and text string in the reconstruction spec is present; subscript/superscript runs retain their baseline shift.

## PDF audit

- PDF renders without clipping or substituted glyph boxes.
- Page resources contain font objects; separately verify embedding and Unicode mapping with a dedicated PDF font tool or Acrobat Preflight.
- Page content contains text operators (`BT` plus `Tj`/`TJ`), not only paths and images.
- Illustrator can select and edit representative text after reopening the PDF.
- Illustrator-specific editability is preserved when the delivery contract requires it.
- Recursively inspect Form XObjects: Illustrator may put each live text object and its font resource inside a Form rather than directly in the page content stream.
- Resolve any Times New Roman missing-font warning before acceptance; SVG declarations alone do not prove Illustrator used the intended font.

## Visual review checkpoints

1. Compare source and cleaned raster at 200%-400%.
2. Compare the overlay-only view against the object inventory.
3. Compare the composite at fit-to-page and at 200%.
4. Open the SVG, AI, and PDF independently; do not infer one format from another.
5. Test one Latin label, one rotated label, one axis, one marker, one group, and one raster panel.

Record every failed checkpoint as an actionable issue. Do not accept “looks similar” as proof of editability.

# Representative complex figure studies

These studies turn the generic taxonomy into concrete decomposition rules. Bounding boxes use source pixels with a top-left origin and must be rechecked against the original PDF asset before production.

## Microscopy and EDS composite

Class: `microscopy-eds-hybrid`, recovery level R3.

The current reference file is 1162 x 716 pixels and contains four specimen columns, not four indivisible pictures. Preserve 23 atomic evidence rasters: four overview SEM fields, four close-up SEM fields, and 15 elemental maps. Do not denoise, sharpen, trace, super-resolve, or generatively fill these fields.

Suggested evidence crops `(x0,y0,x1,y1)`:

- Overview: `(15,40,294,232)`, `(300,40,580,232)`, `(584,40,864,232)`, `(869,40,1148,232)`.
- Close-up: `(15,240,294,433)`, `(300,240,580,433)`, `(584,240,864,433)`, `(869,240,1148,433)`.
- 0Er maps: Al `(15,438,155,541)`, Cu `(155,438,295,541)`, Zr `(15,543,295,645)`.
- 0.15Er maps: Al `(300,438,440,541)`, Cu `(440,438,580,541)`, Zr `(300,543,440,645)`, Er `(440,543,580,645)`.
- 0.3Er maps: Al `(584,438,724,541)`, Cu `(724,438,864,541)`, Zr `(584,543,724,645)`, Er `(724,543,864,645)`.
- 0.6Er maps: Al `(869,438,1009,541)`, Cu `(1009,438,1149,541)`, Zr `(869,543,1009,645)`, Er `(1009,543,1149,645)`.

Rebuild scale bars and their `200 µm`, `10 µm`, and `8 µm` labels; red dashed ROIs; A/B/C arrows; the three EDS composition tables; map element labels; panel captions; gutters and borders. Copy scale-bar pixel lengths exactly rather than recalibrating them.

EDS manifest truth values:

- A: Al 36.15, Cu 8.18, Zr 13.67, Er 41.99.
- B: Al 59.03, Cu 34.53, Zr 0.23, Er 6.21.
- C: Al 60.73, Cu 34.74, Zr 0.20, Er 4.34.

Annotation cleanup is not scientific recovery. Keep a locked source-reference layer and an `annotation_occlusion_mask`; require zero pixel changes outside that mask. Table glyphs and arrows overlap evidence, so never claim inpainted texture is original microscopy. The current whole image is only 1160 px wide and may fall below 300 ppi at publication width; report this honestly and request original SEM/EDS assets.

## Experimental setup composite

Class: `experimental-setup-hybrid`, recovery level mixed R1/R3.

Use seven atomic rasters: the panel-a robot arm, panel-a surface/texture field, the panel-c device photograph, and four panel-d photograph/inset fields. Panel b should be fully vector. Most of panel a can also be vector except the two declared fields.

- Panel a: rebuild frame, panel letter, laser table, laser box, lens, beam, zoom connectors, LSP/MA-LSP schematics, magnets, sample, scale bar and XY axes. Keep the robot and ambiguous texture field atomic.
- Panel b: rebuild the workpiece Bézier outline, shock/leading-edge lines, inset frame, two beams, foil/confinement/absorption layers, normal, angle bisector and both 60-degree relationships.
- Panel c: retain one cleaned machine field; rebuild every red/yellow/white annotation, numbers 1/2/4/5, A/B points and leaders.
- Panel d: retain four independent photograph fields; rebuild red inset frames, cross-image leaders and all seven labels.

Do not interpret the visible `1 mm` scale-bar value as a requested one-millimetre stroke. It denotes specimen-space scale. Keep callout relationships explicit in the spec and verify every target against the original high-resolution asset rather than guessing in dark photograph regions.

## Circular mechanism infographic

Class: `circular-infographic`, recovery level R2, delivery mode `full-vector`.

The reference bitmap is only a placement guide. Rebuild the outer frame, five annular sectors, radial separators, central mechanism circles, five icon groups, arrows and all live text. The final SVG/AI should contain zero image objects.

All sectors must share one declared center, inner/outer radii and angle boundaries. Use explicit closed paths, user-space gradients and explicit arrowhead polygons. Avoid SVG filters, `foreignObject`, external `use`, object-bounding-box gradients and deep clipping stacks. Arc text needs phrase-level editability; do not fake it with one text object per character. Illustrator 2025 has now been observed to import a valid SVG `<textPath>` as reversed, per-character point text, so SVG structure alone is insufficient. Use an Illustrator-native `PATHTEXT` post-import step and require a single full-phrase Type frame in the Illustrator audit.

The current reconstruction schema still needs a second geometry phase for `path`, `polygon`, `sector`, `annulus`, `arc`, `group`, `text_path`, semantic parent/layer/z-order, gradients, explicit arrowheads, OCR confirmation state and circular tolerances. Do not add these types to the executable enum until the renderer and negative tests support them.

Acceptance must reject transparent off-canvas text decoys, a complete PNG covering incorrect vectors, swapped sector semantics, non-concentric rings, gaps hidden by separators, reversed N/S polarity or force direction, and path text that reverses after Illustrator import.

## Three-dimensional response-surface composite

Class: `3d-response-surface-hybrid`, recovery level R1 or R3 depending on whether the fitted model/source data exists.

When source data or a plotting script is available, regenerate the surface and projected contours as true geometry. When only the publication bitmap exists, preserve each continuous field as a separate locked raster atom and rebuild only the three-dimensional axes, projected grids, ticks, labels and confirmed operating-point markers. Do not trace a color field into invented numeric data or claim an occluded field region has been recovered.

The current three-panel reference retains three field atoms and rebuilds 125 paths, including explicit tick shafts/tick ellipses and three black operating-point paths. Its current Illustrator SVG/AI/PDF round-trip is stable at 74 Type / 125 Path / 3 Raster. This does not approve the three marker cutouts, four source review-box footprints, provisional 1.5 mm marker diameter, or the ambiguous `坐标轴1mm` instruction. Treat the last phrase as unresolved until it is classified as stroke width, tick length, marker dimension, or scale-bar length.

## Eight-panel statistical plot suite

Class: `statistical-plot-suite`, recovery level R1 when source data exists.

TOmicsVis Figure 2 is the executable representative: A normal Q-Q plots, B box plots with observations, C violin plots with inner box summaries, D Kaplan-Meier curves with censor marks and risk table, E a 15 by 15 Pearson correlation heatmap, F PCA, G t-SNE, and H a Ward hierarchical dendrogram. The publication JPEG is a locked visual reference only; do not trace it or embed it in the candidate.

Bind every input by SHA-256 and record algorithm/library parameters. Require 225 editable heatmap cells plus 225 live values, 15 uniquely labelled PCA points, the same 15 t-SNE samples, and 15 dendrogram leaves with 14 merges. Recompute symmetry/diagonal properties, survival monotonicity, quartile order, sample inventories, and linkage-height monotonicity in a statistical semantic auditor; generic SVG structure checks are insufficient.

Preserve actual Times New Roman 8.5 pt text by expanding the physical layout when necessary. Do not use SVG `textLength` to squeeze sample identifiers: Illustrator/PDF can distort spacing and drop visible glyph detail. For confidence regions, prefer ordinary bounded polygons over `clipPath`; Illustrator Tiny round-trip can warn about lost clipping paths. The current rev2 Illustrator SVG/AI/PDF stages are stable at 488 Type / 1600 Path / 0 Raster / 0 Placed with zero warnings.

Version provenance is part of the scientific gate. The local data are byte-bound to repository commit `7a12a864...`, whose package version is 0.99.0, while the paper reports TOmicsVis 2.0.0. The current t-SNE is a documented sklearn seed/perplexity approximation, so this remains `publication_ready=false` until the paper-version equivalence or an approved R output is supplied and human scientific/editorial review passes.

## Cross-cutting font decision

Times New Roman does not cover Chinese. Use Times New Roman 8.5 pt for Latin, numerals and symbols it supports. Chinese must use a client-approved installed CJK font at 8.5 pt, or be translated with explicit approval. Never convert Chinese to outlines and then claim it remains editable text.

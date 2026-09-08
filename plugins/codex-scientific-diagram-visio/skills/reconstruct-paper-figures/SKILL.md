---
name: reconstruct-paper-figures
description: Extract figures from paper PDFs and reconstruct raster, mixed, chart, schematic, microscopy, experimental-setup, and infographic figures as editable SVG/AI/PDF deliverables. Use when text, axes, ticks, arrows, tables, labels, borders, or diagram components must remain live and editable in Adobe Illustrator while photos or complex textures are preserved only in the smallest necessary raster regions.
---

# Reconstruct Paper Figures

Produce a traceable figure package whose typography and vector overlays can be edited after delivery. Optimize for publication fidelity, not for a misleading “100% vector” label.

## Required workflow

1. Extract before redrawing.
   - Run `scripts/inventory_pdf_figures.py INPUT.pdf OUTPUT_ROOT --workspace WORKSPACE` before using screenshots or OCR. It renders every page, extracts original embedded image bytes, records page-level native text/vector/image counts, effective image PPI, word boxes, caption candidates, source SHA-256, and a conservative page classification.
   - Use a new output directory by default. The inventory tool refuses non-empty outputs and paths outside the declared workspace unless `--force` is explicit.
   - Build the figure manifest from `03_inventory/pages.json`, `embedded_images.json`, `text_words.json`, `image_placements.json`, and `caption_candidates.json`; do not infer source quality from the page render alone.
2. Classify each figure using `references/decision-matrix.md`; consult `references/figure-taxonomy.md` for cross-disciplinary examples, `references/representative-type-studies.md` for complex decomposition cases, `references/regression-paper-corpus.md` for route-level regression targets, and `references/open-paper-example-corpus.json` for primary-source figure examples whose access and redistribution status are recorded separately. When publisher data or author code exists, read `references/source-data-reconstruction-contract.md` before plotting. The JSON index is discovery evidence only until an allowed asset is downloaded, hashed, and admitted to the executable corpus.
3. Record a reconstruction spec before editing.
   - Set the final physical width in mm or pt.
   - Record every text string, bounding box, rotation, color, alignment, and confidence.
   - Record every raster-preserve region and every object to redraw.
   - Declare data-bearing `protected_regions_px`; masks must not intersect them.
   - When OCR results exist, normalize them with `scripts/build_text_detection_manifest.py` and read `references/text-detection-manifest.md`. Treat OCR agreement as transcription evidence only; its manifest never authorizes cleanup.
   - To turn reviewed OCR into a cleanup plan, read `references/reviewed-ocr-cleanup-bridge.md` and run `scripts/build_reviewed_text_cleanup_plan.py` with a separate `text-cleanup-review-v1` file. Require an explicit decision for every detection; default to glyph-aware `foreground_delta`, not the full OCR rectangle.
4. Remove original raster text before placing new text.
   - Expand each text mask enough to remove antialiasing halos.
   - For actual pixel removal on a flat non-evidence patch, read `references/safe-text-cleanup-contract.md` and run `scripts/apply_safe_text_cleanup.py` from an approved, hash-bound plan. Require the emitted proof that decoded pixels outside the combined binary mask did not change.
   - Independently rerun `scripts/audit_text_cleanup.py` using `references/text-cleanup-audit.md`. Require the source, cleaned raster, mask, optional replacement SVG, config, and report to be distinct files; a machine pass still requires 200%-400% human review.
   - After the executor audit passes, run `scripts/build_cleaned_text_overlay_svg.py`. It must reject stale plan/executor hashes and compute SVG user-unit typography from the physical millimetre canvas so Illustrator reports actual 8.5 pt.
   - Multiple masks may be executed together only when every region independently has a non-evidence rationale, a hash-bound binary mask, non-overlapping protected regions, and a guarded cleanup method. One safe region never authorizes adjacent photographic or scientific pixels.
   - Use flat fill only on a known uniform background; use guarded border median or linear interpolation only when their local statistics pass. Do not use this tool on scientific evidence or textured measurements.
   - Treat clone, inpainting, and content-aware fill as separate experimental operations. Never describe generated or inferred texture as recovered source evidence.
   - Repair any axis, gridline, border, or marker removed by cleanup.
   - For an immutable scientific evidence atom whose baked annotation lies on a locally uniform patch, use the opt-in `annotation_occlusion_masks` contract in `references/annotation-occlusion-contract.md`. Keep the source pixels unchanged, render the audited plate below its live-text replacement, and leave the result unaccepted until risk is `confirmed_occluded` and a human approval is recorded.
5. Rebuild vectors in semantic layers: `raster-base`, `axes-grid`, `data-marks`, `annotations`, `live-text`.
6. Export an editable SVG first. Open it in Illustrator and save AI plus PDF with Preserve Illustrator Editing Capabilities enabled. Never convert required text to outlines.
7. Run the quality contract in `references/quality-contract.md`; visual similarity alone is not acceptance.

## Tool routing

- Use `scripts/inventory_pdf_figures.py` as the deterministic PDF-only entry point. Treat the page renders as review previews and the extracted embedded files as source assets. Its vector-operator census is a routing signal, not proof that a specific figure is natively vector; inspect the figure bbox and PDF objects before deciding R0/R1/R2/R3.
- Route statistical charts with publisher observations through `references/source-data-reconstruction-contract.md`. Hash-bind and keep the original workbook read-only; reproduce source selections, transforms, thresholds, bins and tests before drawing; attach source-row identity to editable observations; and fail closed for any plotted group absent from the supplied data.
- Use `scripts/build_hybrid_svg.py` for recipe-driven raster cleanup plus live SVG overlays.
- Use `scripts/build_text_detection_manifest.py` to merge existing Tesseract TSV or generic local OCR exports into one source-hash-bound, review-gated detection manifest. The script imports results read-only and does not invoke an OCR runtime.
- Use `scripts/apply_safe_text_cleanup.py` only for approved, flat, non-evidence patches. It emits a lossless cleaned PNG, combined binary mask, and an audit proving zero decoded-pixel changes outside the mask; it never marks publication readiness.
- Use `scripts/audit_text_cleanup.py` as the separate read-only verifier for mask geometry, protected regions, exact pixel differences, residue/halo screening, and live replacement text. Do not let its JSON overwrite any evidence input, even with `--force`.
- Use `scripts/bind_illustrator_roundtrip_evidence.py` after Illustrator and PDF audits to hash-bind the current SVG, AI, editable PDF, render and all three stage audits. For hybrid figures whose protected scientific pixels remain as independent Illustrator `PlacedItem` objects, pass both `--expected-placed-count N` and `--placement-manifest <shell.placements.json>`; pass `--expected-path-count` and `--expected-group-count` when those counts are known. The binder validates each atom ID, linked file, PNG SHA-256, raw pt bounds and millimetre placement in all three Illustrator audits, and requires a hash-bound portable SVG plus authoritative atomic manifest that both prove scientific pixels were not modified. Do not reuse an evidence manifest after any bound file changes.
- Read `references/annotation-occlusion-contract.md` before hiding baked labels in atomic evidence. This route is a reversible visual occlusion, not raster inpainting or proof that the old glyph was deleted from the embedded pixels.
- For a full-vector circular infographic, set `contract.require_zero_rasters=true`; compose semantic `group` objects from `annular_sector`, `arc`, `polygon`, typed-command `path`, `ellipse`, and phrase-level `text_path` elements. Define linear/radial gradients in top-level `gradients`; the builder emits `userSpaceOnUse` paint servers and does not embed or generate a cleaned raster for this contract.
- Use `scripts/audit_editability.py --recipe ...` on every SVG so the audit contract comes from the same reconstruction spec; audit every exported PDF separately.
- For surface plots, circular infographics, and other complex publication candidates, create an independent gate JSON using `references/publication-gate.schema.json`, read `references/cross-type-publication-acceptance.md`, and run `scripts/audit_publication_gate.py`. Keep Illustrator evidence explicitly `required-but-missing` and status prototype/blocked until a real import/save/reopen audit exists.
- Run `scripts/export_active_document_pdf.jsx` in Illustrator to create a non-overwriting editable PDF from the active document.
- Run `scripts/audit_active_document.jsx` in Illustrator to export actual Type, path, raster/placed-object, font-size, font-name, stroke-width and artboard measurements from the active AI/SVG/PDF document. Treat documented subscript/superscript sizes as allowed exceptions to the global 8.5 pt rule.
- For one arbitrary SVG candidate, run `scripts/roundtrip_selected_svg_in_illustrator.jsx`. It refuses to overwrite, creates sibling AI/editable-PDF artifacts, closes and reopens both formats, and records separate SVG-import, AI-reopen, and PDF-reopen object audits. A successful round-trip proves persistence only; it must not change `publication_ready` while scientific, typography, translation, or measurement blockers remain.
- If Illustrator warns that SVG path text will be flattened and imports it as unnamed single-character Point Type, run `scripts/repair_text_paths_from_recipe.jsx` on the still-open imported document and select its recipe JSON. The repair is fail-closed, supports only phrase-level `text_path` with `anchor=middle`, `start_offset_percent=50`, uniform `#RRGGBB` styling, and an exact fragment set either beside the recipe curve or inside one direct anonymous wrapper below the curve's parent group. It creates one Illustrator `PATHTEXT` object without outlining or auto-saving. Then rerun `audit_active_document.jsx`, validate that audit JSON with `scripts/audit_illustrator_text_paths.py`, save a new AI copy, close/reopen it, and repeat both audits.
- Use PowerPoint, draw.io, Visio, or Scientific Illustrator for framework-heavy geometry when they accelerate authoring; finish and validate publication deliverables in Illustrator.
- Read `references/backend-integration.md` before selecting Visio or Scientific Illustrator as an authoring backend. For Scientific Illustrator, also read `references/scientific-illustrator-native-verification.md`; an ordinary `.drawio` structural pass is not native runtime evidence.
- For backend generation, use `scripts/export_drawio_scene.py` or `scripts/export_visio_scene.py`; validate either with `scripts/audit_backend_scene.py`. Use `scripts/run_visio_scene_mcp.mjs` only after explicit authorization to open Visio, and keep VSDX/Visio SVG/PDF evidence separate from final Illustrator publication evidence.
- Before packaging this skill for GitHub, read `references/github-release.md` and run `scripts/build_skill_release.py`. Publish the source-only skill archive by default; never sweep adjacent manuscripts, publisher assets, extracted figures, source data, generated evidence, or bytecode into the archive. A code release does not upgrade any figure's publication status.

## Reconstruction rules

- Preserve continuous-tone photography, microscopy, heatmaps, and 3D rendered surfaces as raster unless the underlying data exists.
- Split retained evidence into atomic raster regions with a reason, crop, decomposition note, and `contains_reconstructable_content=false`; never hide a complete source figure under a token vector overlay.
- Redraw axes, ticks, scale bars, black marker points, borders, arrows, dashed boxes, tables, legends, and labels as vector objects.
- Digitize curves only when the source data is unavailable, and label the resulting CSV as digitized rather than original data.
- Prefer hash-bound publisher observations over JPEG tracing. Record the exact sheet/range, selection predicates, transforms, statistical method and runtime/version gap. A visual match is not method parity, and a missing source group may not be synthesized.
- Do not invent occluded geometry or numeric values.
- Do not place new text directly over old raster text. A pixel-cleaned non-evidence base must pass with all overlays hidden. An immutable evidence atom must pass with its audited `annotation-occlusion-masks` plate visible and the replacement elements hidden; the original glyph intentionally remains recoverable below the plate.
- Bind every OCR import, cleanup source, and cleanup mask to SHA-256. Keep text detection, cleanup authorization, pixel execution, live-text replacement, and publication acceptance as separate gates.
- Keep scientific notation as structured live text, including `<tspan>` subscript/superscript runs; never flatten `HV₀.₅` into baseline `HV0.5`.
- Use Times New Roman at exactly 8.5 pt when the job contract requires it. Chinese text requires a user-approved CJK fallback unless the client explicitly demands Times New Roman for unsupported glyphs.
- Express the final page size physically. An arbitrary pixel canvas cannot prove an Illustrator font size.
- Treat an unqualified “1 mm” requirement as unresolved until the client classifies it as `stroke_width`, `tick_length`, `marker_dimension`, or `scale_bar_length`. If and only if `stroke_width` is confirmed, convert 1 mm to 2.83465 pt; never silently promote a provisional source-matched stroke to that value.

## Deliverable layout

For each figure keep:

```text
figure-id/
  source/          original extracted image
  cleaned/         text-removed raster base
  spec/            OCR and reconstruction recipe
  vector/          editable SVG and AI
  pdf/             editable publication PDF
  preview/         rendered QA image
  qa/              audit JSON and review notes
```

Keep source images immutable. Never overwrite a source PDF, extracted image, SVG, AI, or PDF during an experiment.
The scripts fail on existing generated outputs by default; use `--force` only after confirming that the target is a reproducible intermediate file.

## Mandatory acceptance evidence

- A rendered before/after comparison at 200% or higher.
- Illustrator inspection showing that representative labels are Type objects and representative shapes are paths/groups.
- SVG audit with recipe object IDs, exact text content and runs, font size/family, physical size, unique IDs, and no external references.
- PDF audit showing text operators and embedded font resources.
- A human review of text cleanup seams, alignment, character correctness, and axis continuity.

If any item is missing, report the figure as a prototype or partial reconstruction, not complete.

# Cross-type publication acceptance

Use `scripts/audit_publication_gate.py` with a gate JSON conforming to `references/publication-gate.schema.json`. The gate supplements, rather than replaces, recipe-derived SVG audit, Illustrator object audit, editable-PDF audit, and visual review.

## Shared gate

- Require a declared status: `prototype`, `blocked`, `candidate`, or `approved`.
- Keep `prototype` or `blocked` when Illustrator evidence is `required-but-missing`, visual review is pending/failed, or any automated blocker remains.
- Never claim `approved` while `documented_blockers` is non-empty.
- Require every SVG text object to remain live Times New Roman 8.5 pt. List structured subscript/superscript exceptions by exact contents, actual point size, and reason; an Illustrator warning alone is not an exception.
- Reject `<marker>`, `marker-start`, `marker-mid`, and `marker-end` in publication SVG. Illustrator may preserve an arrowhead while losing or changing its shaft; use explicit path/polygon geometry and audit both components.
- Forward every undeclared or unapproved annotation occlusion as a publication blocker.
- Require independent Illustrator audit JSON for `svg_import`, `ai_reopen`, and `pdf_reopen` before approval. Use `partial` while only some stages exist and `required-but-missing` before the first real audit. SVG structure cannot prove Type, Path Type, raster count, imported font, or saved/reopened editability.
- For a revision-specific candidate, populate `illustrator_evidence.source_documents` with the exact SVG, AI, and editable-PDF files used at those three stages. The gate compares each audit's `source_document` to that inventory and rejects predecessor or cross-revision evidence. Add `illustrator_evidence.pdf_audit` so the gate also verifies that the structural PDF audit passed and names the same editable PDF.
- Inventory critical named vectors in `required_vector_object_ids`. For Illustrator approval, every listed ID must survive as a native vector object in all three stage audits; a visually similar raster substitute does not count.
- Require a passed visual-review report for approval.
- Use `expected_illustrator_counts` when a candidate has a measured exact Type/Path/Raster/Placed/warning inventory; any stage mismatch blocks publication.
- When a structurally passing PDF still has semantic text/font risk, use `pdf_text_expectations.required_extractable_text` and `forbidden_font_name_fragments`. Missing source-language text or an unapproved substitute font remains a blocker even when text operators exist.

## Detection matrices

- Declare each scientific cell as an independent evidence atom with matching source/embedded SHA-256 values, `byte_identical=true`, and SVG `data-evidence` / `data-atomic-raster-unit` metadata.
- Detection labels, boxes, masks, or review arrows baked into those atoms are scientific-source risks, not editable-vector claims. Keep publication blocked until clean upstream layers or explicit scientific-owner approval are available.

## Surface plots and scientific continuous fields

- Set `contract.require_atomic_rasters=true` and declare the minimum expected atomic panels in the gate. Reject a single whole-figure raster or raster tiles that collectively form an undeclared backdrop.
- List every scientific atom in `required_atomic_raster_ids` and, when applicable, provide `atomic_manifest`. Each matching SVG image must be embedded, named, marked `data-evidence="true"` and `data-atomic-raster-unit="true"`, and traceable to the manifest. An atom carrying `pending` annotation-occlusion status blocks publication even when its RGB/hash checks pass.
- Keep surfaces, contours, heatmaps, microscopy texture, and other continuous evidence as immutable atomic PNGs. Rebuild axes, ticks, labels, black points, borders, and approved markers as vectors.
- Reject legacy destructive `masks` in a publication surface candidate. Use an approved `annotation_occlusion_masks` contract only on a locally uniform, non-measurement patch.
- Declare exactly what “1 mm” means. Do not infer it from an earlier prototype:
  - `stroke_width`: verify recipe width is 1 mm and Illustrator reads 2.83465 pt.
  - `tick_length`: verify the physical line length is 1 mm; its stroke may remain much thinner.
  - `marker_dimension`: require `dimension_axis=width|height|diameter` and verify that physical dimension is 1 mm.
  - `scale_bar_length`: verify the line geometry is 1 mm, not its thickness.
  - `unresolved`: always blocks publication.
- Confirm that black dots requested as lines/axes were rebuilt as named vector objects and were not retained only inside the raster atom.

## Circular infographics

- Set `contract.require_zero_rasters=true`; require zero SVG `<image>`, `feImage`, Illustrator RasterItem, and PlacedItem counts.
- Inventory every required icon by ID. Each icon must contain vector geometry and no image, foreign object, or filter image. A zero whole-document raster count is necessary but does not replace icon-by-icon inventory.
- Keep curved phrases as a single recipe `text_path`. Require the Illustrator audit to show one named native Path Type object with non-degenerate path geometry and require the dedicated text-path audit to reject fragmented single-character Point Type.
- Visually verify curve direction, centering, glyph order, spacing, sector alignment, arrows, icon fidelity, and Chinese/translation policy after AI save and reopen.

## Final evidence matrix

| Evidence | Surface plots | Circular infographic |
|---|---:|---:|
| Recipe-derived SVG audit | Required | Required |
| Atomic raster inventory | Required | Must be zero |
| Marker-risk scan | Required | Required |
| TNR 8.5 pt live SVG text | Required | Required |
| Illustrator Type/Path/Raster audit | Required | Required |
| Revision-bound source paths and PDF structural audit | Required for revision-specific evidence | Required for revision-specific evidence |
| Phrase-level Path Type audit | When used | Required when `text_path` exists |
| Icon-by-ID vector audit | When icons exist | Required |
| Explicit 1 mm decision | Required when mentioned | `not_applicable` only if truly absent |
| Undeclared occlusion scan | Required | Required |
| Manual visual report | Required | Required |
| Publication status consistency | Required | Required |

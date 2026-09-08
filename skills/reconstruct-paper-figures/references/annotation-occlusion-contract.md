# Annotation occlusion contract

Use this contract only when a baked annotation inside an atomic scientific raster must be visually hidden but modifying evidence pixels would be unsafe. It produces a reversible Illustrator-friendly solid `<rect>` below live SVG `<text>` or other declared replacement vectors. It does not erase the old glyph from the embedded PNG.

## Required recipe declaration

Declare `annotation_occlusion_masks` at the top level. Coordinates in `rect_px` are absolute pixels in the referenced atom's `source_file`, not crop-local or canvas coordinates.

```json
{
  "annotation_occlusion_masks": [
    {
      "id": "old-label-plate-a",
      "atomic_raster_id": "micrograph-a",
      "rect_px": [412, 86, 38, 13],
      "mode": "narrow_mask",
      "fill": "#F2F2F2",
      "max_area_fraction": 0.02,
      "evidence_change_contract": "source_pixels_immutable",
      "source_crop_sha256": "<64 lowercase hex digits for the normalized RGBA atomic crop>",
      "old_annotation_risk": "confirmed_occluded",
      "approval_status": "approved",
      "approved_by": "QA editor",
      "approval_note": "Reviewed at 400%; halo removed and no measurement feature covered.",
      "rationale": "Hide the baked panel label on a uniform margin.",
      "replacement_element_ids": ["panel-label-a"]
    }
  ]
}
```

The referenced atomic raster must use source and cleaned images whose selected crops are pixel-identical after normalization to RGBA. Lock that normalized crop in the recipe with `source_crop_sha256`; the builder recomputes and verifies it before writing the SVG. It maps the source rectangle into the atom's canvas rectangle, renders a solid `plate` or `narrow_mask` in `annotation-occlusion-masks`, and places normal recipe `elements` above it.

## Status model

- Set `old_annotation_risk` to `not_reviewed` or `residual_risk` while inspecting. The audit must fail.
- Set `approval_status` to `pending` to generate a review artifact. The audit must fail.
- Never build a `rejected` mask. The builder fails closed.
- Set `approval_status=approved` only with `old_annotation_risk=confirmed_occluded`, a named reviewer, and an actionable review note. The builder and audit enforce these fields.

## Bounds and evidence safety

- Keep `rect_px` fully inside the referenced atom's `source_bbox_px`.
- Declare a real `max_area_fraction` no larger than 0.25. Prefer the smallest value that contains the antialiasing halo; the builder compares actual mask area with the declaration.
- Keep mapped mask geometry outside every top-level `protected_regions_px` rectangle.
- Reference at least one existing `text` or `text_path` element in `replacement_element_ids`. Add repaired lines, scale bars, or borders as additional IDs when needed.
- Use only solid `#RRGGBB` fills. Do not use opacity, blur, filters, patterns, `foreignObject`, external images, generative fill, or clone/inpaint operations on evidence.
- Use this method only on a locally uniform patch. If a texture, curve, marker, cell, spectrum, heatmap, or measured feature crosses the glyph, stop and obtain a clean source or human-approved scientific reconstruction.

## Acceptance evidence

Run `scripts/audit_editability.py --recipe ...` and require an empty `annotation_occlusion_issues` list. The audit checks declared/missing masks, `<rect>` type and parent, recipe-derived geometry, solid paint, metadata, area contract, risk/approval state, live-text replacement existence and draw order, referenced atom existence, and equality among the recipe-locked source digest, embedded pixel digest, and both recorded source/embedded crop digests.

In Illustrator, verify that the plate is an editable rectangle and the replacement is a Type object. Toggle the replacement off and inspect raster plus plate at 400%; then toggle the plate off to confirm that the original evidence atom is recoverable and unchanged.

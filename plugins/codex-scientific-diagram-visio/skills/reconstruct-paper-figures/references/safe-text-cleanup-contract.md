# Safe text-cleanup contract

Use `scripts/apply_safe_text_cleanup.py` only for old annotations on visually
flat, non-scientific background. It is a deterministic raster operation, not
content recovery or generative inpainting. Keep microscopy, plots, spectra,
maps, scale bars, specimen boundaries, instrument geometry, and other evidence
in `protected_regions` or leave them untouched.

## Plan

Store paths relative to the plan when practical. Run from the paper workspace:

```powershell
python skills/reconstruct-paper-figures/scripts/apply_safe_text_cleanup.py `
  organized/examples/example/cleanup-plan.json
```

```json
{
  "schema_version": "safe-text-cleanup-v1",
  "source_image": "source.png",
  "source_sha256": "<64 lowercase hex>",
  "output_image": "cleaned.png",
  "combined_mask_output": "cleanup-mask.png",
  "audit_output": "cleanup-audit.json",
  "scientific_evidence": false,
  "risk_class": "non_evidence_flat_background",
  "approval_status": "approved",
  "approved_by": "reviewer name or role",
  "approval_note": "Why this patch is non-evidence and safe to alter.",
  "max_mask_area_fraction": 0.02,
  "protected_regions": [
    {"id": "plot", "bbox_px": [20, 20, 760, 500]}
  ],
  "regions": [
    {
      "id": "old-panel-letter",
      "bbox_px": [4, 4, 14, 16],
      "mask_file": "old-panel-letter-mask.png",
      "mask_sha256": "<64 lowercase hex>",
      "method": "border_median",
      "parameters": {"ring_px": 2, "max_border_stddev": 6.0}
    }
  ]
}
```

Coordinates use the same `[x, y, width, height]` integer-pixel convention as
`build_hybrid_svg.py` and `audit_text_cleanup.py`. Each mask must be a full-canvas mode `1` or `L` image
containing only 0 and 255. Every selected pixel must lie inside its region bbox.
Masks must not overlap or touch a protected rectangle.

## Methods

- `solid_fill`: require `parameters.color_rgba` with three or four integer
  channels. Use only when the expected background color is known exactly.
- `border_median`: sample an external ring, reject the operation when any RGBA
  channel standard deviation exceeds `max_border_stddev`, then fill with the
  channel medians. Use for a uniform patch.
- `horizontal_linear`: interpolate per row between the pixels immediately left
  and right of the bbox. Reject when the largest channel difference exceeds
  `max_boundary_delta`.
- `vertical_linear`: interpolate per column between pixels immediately above
  and below the bbox with the same boundary-delta guard.

Do not use these methods to invent texture. If a glyph overlaps evidence,
retain the original raster and use the reversible annotation-occlusion contract
or reconstruct the affected geometry from an authoritative source.

## Fail-closed guarantees

The executor accepts only single-frame, unsigned integer `1`, `L`, `LA`, `P`,
`RGB`, or `RGBA` sources whose file-level PNG/TIFF/BMP precision is explicitly
supported. It checks PNG IHDR depth, TIFF `BitsPerSample` and `SampleFormat`, and
BMP pixel depth. It refuses 16-bit-per-sample, signed, and float images rather than silently
reducing evidence precision. It also refuses JPEG sources, stale hashes, unapproved plans, evidence
regions, non-binary or wrong-size masks, mask overlap, protected-region
collision, excessive mask area, unsafe border statistics, path escape, and
existing output files. Existing paths are compared by file identity so a hard
link cannot make an output alias a source, plan, mask, or another output.
`--force` is an explicit overwrite operation; use it
only after resolving exact targets.

The audit records source/plan/mask/output hashes, decoded RGBA hashes, per-region
method evidence, mask area, changed pixels inside the mask, and changed pixels
outside the mask. The last count must equal zero. The tool always emits
`publication_ready: false`: a separate cleanup audit must check halos/residue,
and the final SVG/AI/PDF must prove live replacement text and editability.

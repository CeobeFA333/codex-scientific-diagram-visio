# Text-cleanup audit contract

Use `scripts/audit_text_cleanup.py` after a deterministic, non-generative cleanup has produced a cleaned raster and a full-canvas binary mask. The auditor is read-only: it never repairs pixels and never interprets a machine pass as publication approval.

## Safety boundary

- Run this audit only for old labels on a demonstrably non-evidence, locally simple background. Do not use its heuristic result to authorize edits to microscopy, spectra, heatmaps, contours, measured curves, scale bars, specimens, or apparatus details.
- The source, cleaned raster, mask, optional replacement SVG, config, and JSON output must resolve inside the current workspace. Symlinks and `..` traversal are resolved before the boundary check.
- Those paths must also resolve to distinct files. In particular, `--json-out` can never overwrite the source, cleaned raster, mask, replacement SVG, or config, even when `--force` is present.
- The source and cleaned raster must have identical pixel dimensions. Pixel comparisons normalize both to RGBA; file-byte SHA-256 and normalized pixel SHA-256 are recorded separately.
- The mask must cover the complete canvas, have the same dimensions, and contain only opaque black `(0)` or opaque white `(255)` pixels. White means “cleanup was allowed here.” Any non-binary/transparent pixel fails the audit.
- Every source-to-cleaned pixel difference must be inside the white mask. One changed pixel outside the mask is a failure.
- A declared protected rectangle fails if the mask touches it, even if the cleanup happened to leave those protected pixels unchanged. It also fails independently if any protected pixel changed.
- Mask and changed-pixel area limits are independent. Defaults are 25% of the canvas and should normally be tightened for label removal.
- `publication_ready` is always `false`. A human editor must still inspect the cleaned raster at 200%-400%, with the vector overlay hidden, and record explicit approval elsewhere.

## CLI

```powershell
python skills/reconstruct-paper-figures/scripts/audit_text_cleanup.py `
  organized/figures/figXX/source.png `
  organized/figures/figXX/cleaned.png `
  organized/figures/figXX/cleanup-mask.png `
  --replacement-svg organized/figures/figXX/replacement-labels.svg `
  --config organized/figures/figXX/text-cleanup-audit.config.json `
  --json-out organized/figures/figXX/text-cleanup.audit.json `
  --require-pass
```

`--require-pass` exits with status 1 when the machine audit fails. Without it, the command still writes the findings so a blocked candidate can be reviewed. Existing JSON is not overwritten unless `--force` is supplied.

## Optional config

Only the following keys are accepted; unknown keys fail closed.

```json
{
  "protected_regions": [
    {
      "id": "measured-curve",
      "bbox_px": [120, 48, 310, 160]
    }
  ],
  "max_mask_area_fraction": 0.03,
  "max_changed_area_fraction": 0.02,
  "residual_pixel_fraction_limit": 0.05,
  "halo_pair_fraction_limit": 0.10,
  "expected_font_family": "Times New Roman",
  "expected_font_size_pt": 8.5,
  "required_text_ids": [
    "panel-label-a",
    "axis-title-x"
  ]
}
```

`bbox_px` is `[x, y, width, height]` in full-canvas pixels. Every rectangle must have a unique non-empty ID, positive size, and stay inside the canvas.

## Machine checks

The JSON report uses schema marker `text-cleanup-audit-v1` and records:

- byte and normalized-pixel hashes for source and cleaned images;
- byte hash, mode, selected-pixel count, and area fraction for the mask;
- exact changed-pixel count, changed area fraction, and outside-mask changed-pixel count;
- mask/change intersections for every protected region;
- residual-glyph and boundary-halo heuristic metrics;
- optional replacement-SVG hash, live-text inventory, visibility, IDs, effective font family, and effective physical font size;
- a stable issue code list, `pass`, `publication_ready: false`, and `manual_approval_required: true`.

For replacement SVGs, visible, non-empty `<text>` elements are required. By default the effective typography must be Times New Roman at 8.5 pt. The auditor accepts either `8.5pt` or the equivalent `11.3333px`/unitless CSS user-unit value. Inherited presentation attributes and inline `style` values are evaluated. Scripts, stylesheets, event handlers, `foreignObject`, `feImage`, and non-local references fail the audit. `required_text_ids` can lock the expected live labels.

## Residue and halo heuristics

These are deliberately conservative screening checks, not image understanding:

- The auditor samples a one-pixel ring immediately outside the mask, estimates its grayscale median and median absolute deviation (MAD), and flags an excessive fraction of cleaned pixels inside the mask that depart from that local background.
- It compares cleaned grayscale values across the mask boundary and flags an excessive fraction of high-contrast inside/outside neighbor pairs.
- The contrast threshold is `max(12, 4 * MAD + 4)` grayscale levels. Fraction limits are configurable, but weakening them requires a documented visual reason.

A flag may mean a glyph ghost, antialiasing halo, clone seam, or simply that the background is too structured for this cleanup method. In every case, fail closed and review the source; do not suppress the finding merely to obtain a pass.

## Important distinction

This contract audits a cleaned raster whose allowed edit area is explicit. It is different from `annotation_occlusion_masks`, which place reversible vector plates above immutable evidence atoms and do not change raster pixels. Do not use one contract's pass result as evidence for the other.

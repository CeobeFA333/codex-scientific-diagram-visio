# Reviewed OCR cleanup bridge

This bridge converts OCR evidence into a cleanup plan only after a separate human
review file explicitly decides every detection. OCR output is never authorization.

## Required gates

1. Build `text-detection-manifest-v1` with `build_text_detection_manifest.py`.
2. Create a separate `text-cleanup-review-v1` file. Bind both source SHA-256 and
   detection-manifest SHA-256; mark every detection `cleanup_replace` or `preserve`.
3. For each cleanup region, declare a flat non-scientific background, protected
   regions, replacement text, Times New Roman 8.5 pt, and translation status.
4. Run `build_reviewed_text_cleanup_plan.py`. The default `foreground_delta` mode
   estimates the local border colour, selects glyph pixels inside the OCR polygon,
   and applies only the reviewed small dilation. `full_polygon` is forbidden unless
   the review explicitly opts in with a reason.
5. Run `apply_safe_text_cleanup.py`, then the independent `audit_text_cleanup.py`.
   Require zero decoded-pixel changes outside the union mask and zero protected
   overlap. A machine PASS still requires 200%-400% visual review.
6. Run `build_cleaned_text_overlay_svg.py`. It refuses stale executor evidence and
   embeds the lossless cleaned PNG plus live replacement text. The embedded image
   must retain `data-source-file`/`data-source-sha256` for the original and
   `data-cleaned-file`/`data-cleaned-sha256` for the cleaned derivative.
7. Run the Illustrator close/reopen roundtrip and PDF structural audit. Bind the
   SVG, AI, editable PDF, three stage audits and rendered PDF with
   `bind_illustrator_roundtrip_evidence.py`.

## Physical 8.5 pt rule

Illustrator scales SVG text through the viewBox-to-physical-artboard transform. The
overlay builder therefore computes the required SVG user-unit font size from the
declared millimetre width instead of assuming `px * 72/96`. The SVG carries
`data-physical-font-scaling="viewBox-to-mm"`; both independent and editability audits
recompute the scale, and Illustrator must report actual 8.5 pt at all three stages.

## Scientific safety

- Do not inpaint microscopy, spectra, diffraction, maps, measured curves or texture.
- Prefer clean source atoms. If none exist, preserve the baked label and fail closed.
- Flat plates already covering a photograph may be recoloured only inside the
  reviewed glyph mask; the plate is not evidence recovery.
- Rebuild axes, borders and markers as vectors when cleanup would damage them.
- Keep `publication_ready=false` until translation and visual/scientific approval.

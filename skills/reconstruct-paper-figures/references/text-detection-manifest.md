# Text detection manifest

Use `scripts/build_text_detection_manifest.py` when OCR has already been run by
Tesseract, PaddleOCR, another local tool, or a manually corrected detector.  The
script imports results; it does not invoke an OCR runtime, download a model, edit
the source image, or authorize text removal.

## Command

```powershell
python skills/reconstruct-paper-figures/scripts/build_text_detection_manifest.py `
  organized/figures/fig01/source/figure.png `
  organized/figures/fig01/spec/text-detection-manifest.json `
  --workspace . `
  --tesseract-tsv tesseract=organized/figures/fig01/spec/tesseract.tsv `
  --generic-json paddle=organized/figures/fig01/spec/paddle.json
```

Every source, import, and output path must resolve inside `--workspace`.  Existing
outputs are refused unless `--force` is explicit.  Even with `--force`, the output
must not resolve to the source image or any OCR import.  The source and OCR imports
are opened read-only and bound to the manifest by SHA-256.

`ENGINE=PATH` is recommended, especially when more than one export of the same
format is supplied.  With no engine prefix, Tesseract TSV uses `tesseract`.
Generic JSON uses the CLI prefix first, then its top-level `engine` field, and
uses `generic` only when neither is present.

## Accepted inputs

Tesseract TSV must have the standard columns `left`, `top`, `width`, `height`,
`conf`, and `text`.  Empty text rows and structural rows with negative confidence
are ignored.  Tesseract confidence is always interpreted as 0-100, so `conf=1`
becomes `0.01`, not `1.0`.  Generic JSON confidence may use either 0-1 or 0-100.

Generic JSON may be a list or an object containing `detections`, `results`,
`items`, or `words`.  An object may declare `engine` and `source_sha256`; a
declared source hash must exactly match the selected image.  Each detection must
contain:

```json
{
  "id": "ocr-17",
  "text": "Voltage (V)",
  "confidence": 0.97,
  "bbox_px": {"x": 120, "y": 80, "width": 94, "height": 18},
  "polygon_px": [[120, 80], [214, 80], [214, 98], [120, 98]],
  "rotation_deg": 0
}
```

`bbox`, `box`, `polygon`, `points`, `score`, `conf`, `rotation`, and `angle` are
accepted aliases.  A polygon can replace a bbox and vice versa.  Coordinates
outside the source raster, invalid confidence, empty text, malformed geometry,
bad hashes, and path escapes fail closed.  When both bbox and polygon are present,
the bbox must match the polygon's axis-aligned bounds within the larger of 1 px or
2% of the detection size.

The same OCR export must not be imported twice under different engine aliases.
Duplicate resolved paths and byte-identical imports are rejected, so aliases
cannot manufacture multi-engine agreement.

## Agreement and manual gate

Detections are matched only when their NFKC-normalized, case-folded text is equal
and their bounding-box intersection-over-union reaches `--iou-threshold` (default
0.5) against every existing member of the cluster.  This complete-link rule
prevents a chain of partly overlapping boxes from merging distant endpoints.
Each cluster accepts at most one contributor from an engine.  The
highest-confidence contributor supplies the canonical text, bbox, polygon, and
rotation; every contributor remains recorded with its engine, source detection
ID, import path, import hash, and confidence.

Each canonical detection records `engine_agreement`.  A per-detection manual gate
remains pending for single-engine, low-confidence, or rotated results.  Even when
all detections agree, the manifest-level gate is always pending because OCR
agreement is evidence for transcription, not permission to erase pixels.

The following top-level values are invariant in a newly generated manifest:

```json
{
  "read_only_import": true,
  "ocr_runtime_invoked": false,
  "cleanup_authorized": false,
  "publication_ready": false,
  "manual_gate": {"required": true, "status": "pending"}
}
```

Review the source at high zoom, confirm text and geometry, classify protected
scientific evidence, and create a separate approved cleanup plan.  Do not edit
these flags to make the manifest serve as cleanup or publication evidence.

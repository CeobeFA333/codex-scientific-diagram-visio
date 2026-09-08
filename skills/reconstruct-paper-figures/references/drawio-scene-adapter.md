# draw.io / Scientific Illustrator scene adapter

`scripts/export_drawio_scene.py` converts the project’s Illustrator-friendly SVG subset into an uncompressed, standard `mxGraphModel`. The result is a staging artifact for a draw.io-based Scientific Illustrator backend: it remains structurally editable, but it is not evidence that the plugin imported or round-tripped the file.

## Contract

- The SVG must have a physical `width` and `height` in millimetres and a uniformly scaled `viewBox`. Coordinates are converted to draw.io points (`72 / 25.4` points per millimetre).
- Every supported drawable and group needs a unique SVG `id`. The corresponding cell ID is deterministic: `cell-<svg-id>` after conservative character normalization.
- The output root is a raw `mxGraphModel`, with separate `Background` and `Scientific editable content` layers. SVG groups become nested, editable group vertices.
- `rect`, `ellipse`, triangle/quadrilateral `polygon`, and embedded `image` elements become vertices. `line`, `polyline`, and rectilinear `path` elements become edges with explicit endpoints and waypoints.
- Recipe connections are checked against source IDs. When a connection ID names an edge primitive, its recipe `from` and `to` fields become actual mxGraph `source` and `target` references; all connections also retain semantic metadata.
- Text is plain cell text with `html=0`, `Times New Roman`, and `8.5 pt`. SVG `tspan` runs are flattened into one editable string because rich/HTML text is deliberately forbidden.
- Images are accepted only as inline, base64 `data:image/...;base64,...` URIs. Because semicolons delimit mxGraph styles, the adapter validates the base64 and writes diagrams.net's embedded `data:image/...,<payload>` style form. The Fig.07 regression has no images.

## Fail-closed exclusions

The adapter refuses output when it encounters unsupported SVG elements, missing or colliding IDs, non-uniform physical scaling, unsupported colors, curves or non-rectilinear path commands, polygons other than triangles/quadrilaterals, external image paths, external URLs, `foreignObject`, event attributes, URL paints, or recipe canvas/font/connection mismatches. It also enforces a recipe’s zero-raster contract.

Existing outputs are never replaced unless `--force` is supplied. The `.drawio`, manifest, and audit paths are checked together before conversion; unsupported input is rejected before any of them is written.

## Fig.07 regression command

```powershell
python skills/reconstruct-paper-figures/scripts/export_drawio_scene.py `
  organized/figures/fig07/vector/fig07_publication_tnr_8_5pt.svg `
  organized/figures/fig07/backend/fig07_scientific_illustrator.drawio `
  --recipe organized/figures/fig07/fig07_publication.recipe.json
```

The sibling manifest records source and recipe hashes, stable ID mapping, and object counts. The sibling audit checks the mxGraphModel structure, live-text contract, embedded-image contract, and absence of external or foreign content.

## Verification boundary

The adapter does not install, launch, or call Scientific Illustrator or draw.io. A passing audit means only that the generated XML satisfies this repository’s structural contract. A real plugin import/save/reopen test is still required before claiming backend compatibility or publication readiness.

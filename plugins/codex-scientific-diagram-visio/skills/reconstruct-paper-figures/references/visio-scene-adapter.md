# Visio Scientific SceneGraph adapter

`scripts/export_visio_scene.py` is an offline adapter from an Illustrator-friendly SVG plus an optional reconstruction recipe to the public Scientific SceneGraph consumed by TZ-mx/Visio-Illustrator. `scripts/run_visio_scene_mcp.mjs` is the separate, explicitly authorized runtime driver that can open Visio, draw the scene, save VSDX, validate fidelity, and export PNG/SVG/PDF. Neither script installs the plugin or overwrites an existing output by default.

## Contract source

The adapter was checked against public upstream commit `69df39c641f38574110563ee343f2a4d8fad30a3`:

- repository: <https://github.com/TZ-mx/Visio-Illustrator>
- SceneGraph schema: <https://github.com/TZ-mx/Visio-Illustrator/blob/69df39c641f38574110563ee343f2a4d8fad30a3/plugins/visio-scientific-illustrator/scripts/scene-schema.mjs>
- .NET contracts: <https://github.com/TZ-mx/Visio-Illustrator/blob/69df39c641f38574110563ee343f2a4d8fad30a3/plugins/visio-scientific-illustrator/bridge/VisioBridge.Contracts/SceneContracts.cs>
- execution planning: <https://github.com/TZ-mx/Visio-Illustrator/blob/69df39c641f38574110563ee343f2a4d8fad30a3/plugins/visio-scientific-illustrator/bridge/VisioBridge.Core/Scenes/SceneExecutor.cs>

At this revision, the SceneGraph has exactly `scene_id`, `canvas`, `style_tokens`, `layers`, `nodes`, `connectors`, and `regions` at the top level. Node kinds are `shape`, `text`, `path`, `image`, `component`, and `group`. Stable semantic IDs become Visio `User.CodexId`; `parent_id` supplies group membership; connectors refer to existing semantic node IDs. The upstream validator rejects unknown node kinds, duplicate IDs, missing parents/endpoints, parent cycles, undeclared layers, out-of-canvas bounds, unsupported path commands, and scenes without a checkpoint.

## Coordinate and typography mapping

The adapter uses the SVG viewBox as top-left SceneGraph pixels. It derives DPI independently from physical width and height and requires both results to agree. For FIG07:

```text
1800 px / (180 mm / 25.4) = 254 dpi
1000 px / (100 mm / 25.4) = 254 dpi
```

Thus SVG geometry remains in the same numeric coordinate system while the 180 × 100 mm physical size is preserved. SVG font units are converted through `font_size_user_units × 72 / dpi`. When a recipe is supplied, values within 0.01 pt of the recipe main/subscript contract are snapped to the exact declared values. FIG07 therefore emits 33 Times New Roman 8.5 pt main runs and 16 documented 5.95 pt subscript runs.

## Supported SVG subset

- `<rect>` → editable `shape` (`rectangle` or `rounded_rectangle`)
- `<ellipse>` / `<circle>` → editable ellipse `shape`
- `<polygon>` / `<polyline>` / `<line>` → native editable `path`
- absolute SVG path commands `M`, `L`, `C`, `A`, `Z` → native SceneGraph `path`
- `<text>` and `<tspan>` → editable text plus UTF-16-indexed rich-text runs
- leaf `<g>` containers → top-level SceneGraph groups with stable IDs; higher container hierarchy is represented by layers
- recipe `connections` plus recognized grouped arrow shafts → glued SceneGraph connectors
- solid fills, no fill, #RRGGBB strokes, opacity, common caps/joins, numeric dash arrays, and rounded corners

Semantic layers are `background`, `structure`, `connectors`, `live-text`, and `annotations`. Every emitted node, leaf group, and connector retains a stable semantic ID derived from the SVG or recipe. The adapter intentionally omits global `z_order`: the pinned bridge applies z positions relative to the current Visio group, so a global SVG index can exceed the sibling count after grouping. Deterministic node-array creation order and layers are used instead.

Every connector carries normalized `source_anchor` and `target_anchor` values derived from the original SVG endpoints. This is required for visual fidelity: Visio's automatic center anchors preserved topology but produced visibly wrong diagonal arrows and displaced return paths in the first real runtime.

## Fail-closed exclusions

The adapter rejects rather than approximates:

- `foreignObject`, external or embedded `href`/`xlink:href`, `<image>`, `<use>`, paint-server URLs, CSS imports, DOCTYPE/ENTITY, event attributes;
- transforms, masks, filters, clipping, gradients, patterns not represented by the supported inline style subset;
- unsupported/relative/implicit path commands;
- missing or duplicate IDs, mismatched physical X/Y DPI, nonzero viewBox origins, fractional canvas dimensions;
- recipe/SVG canvas mismatch, connection mismatch, missing endpoints, unexpected fonts or font sizes;
- any output overwrite unless `--force` is explicit.

These constraints are intentional. They avoid silently flattening text, converting unknown geometry to raster, guessing connector topology, or importing remote content.

## CLI

```powershell
python skills/reconstruct-paper-figures/scripts/export_visio_scene.py `
  organized/figures/fig07/vector/fig07_publication_tnr_8_5pt.svg `
  organized/figures/fig07/backend/fig07_visio_scene.json `
  --recipe organized/figures/fig07/fig07_publication.recipe.json `
  --scene-id fig07-visio-scene
```

The command also creates adjacent `.manifest.json` and `.audit.json` files. Use `--check` to compare deterministic committed outputs without writing. Default generation refuses if any target already exists; `--force` only replaces the three explicitly resolved adapter outputs.

After separately obtaining and building the pinned upstream plugin, the authorized runtime form is:

```powershell
node skills/reconstruct-paper-figures/scripts/run_visio_scene_mcp.mjs `
  --plugin-root '<absolute plugin root>' `
  --scene organized/figures/fig07/backend/fig07_visio_scene.json `
  --output organized/figures/fig07/backend/fig07_visio_backend_runtime_v2.vsdx `
  --audit organized/figures/fig07/backend/fig07_visio_backend_runtime_v2.audit.json `
  --preview organized/figures/fig07/backend/fig07_visio_backend_runtime_v2_preview.png `
  --svg organized/figures/fig07/backend/fig07_visio_backend_runtime_v2_export.svg `
  --pdf organized/figures/fig07/backend/fig07_visio_backend_runtime_v2_export.pdf `
  --step-delay-ms 100
```

## Acceptance boundary

`structural_pass: true` proves deterministic translation, hashes, the mirrored/upstream SceneGraph contract, unique IDs, declared layers, live text runs, required connector IDs, requested `glued: true`, and fail-closed input handling. It does **not** prove that Visio drew the scene, that connector endpoints acquired two real `GlueTo` records, that groups survived VSDX save/reopen, or that Visio and Illustrator render identically.

Those claims require a separate authorized plugin run: `visio_live_draw_scene`, save/reopen, `visio_validate_fidelity`, and exported PNG/SVG/PDF inspection. The runtime driver deliberately skips the bridge's 30-second live/file `inspect` calls by default because the 150-object FIG07 page exceeds that fixed timeout; saved-file `validate_fidelity` has a 120-second limit and is the authoritative deep check.

## Verified FIG07 runtime

The pinned bridge was built in a temporary directory and run against desktop Visio 16.0 without installing or registering a permanent plugin. The accepted V2 evidence is under `organized/figures/fig07/backend/`:

- `fig07_visio_backend_runtime_v2.vsdx`
- `fig07_visio_backend_runtime_v2_preview.png`
- `fig07_visio_backend_runtime_v2_export.svg`
- `fig07_visio_backend_runtime_v2_export.pdf`
- `fig07_visio_backend_runtime_v2.audit.json`
- `fig07_visio_backend_runtime_v2.evidence.json`
- `fig07_visio_backend_runtime_v2.visual_review.md`

The runtime applied 267 steps with one checkpoint and no failed index. Saved-file validation reports one page, 116 shapes and 34 connectors. Fidelity reports 150/150 semantic IDs, 150/150 primitives, 34/34 glued connectors, zero text mismatches, zero errors and zero warnings. The first center-anchor runtime is retained as a visual counterexample; V2 is the authoring-backend result.

This does not supersede Illustrator publication evidence. VSDX, Visio SVG, and Visio PDF prove the Visio authoring backend only; final AI/live-Type/editable-PDF acceptance remains in the Illustrator workflow.

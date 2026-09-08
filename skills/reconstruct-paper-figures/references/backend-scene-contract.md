# Backend scene structural audit contract

Use `scripts/audit_backend_scene.py` to audit editable scenes emitted for Visio or draw.io. This gate is intentionally independent from the authoring adapters. It verifies the interchange structure before a native application is trusted, and it never treats a generated JSON/XML file as proof that Visio or draw.io opened and preserved it.

## Command

```powershell
python skills/reconstruct-paper-figures/scripts/audit_backend_scene.py <scene.json-or.drawio> `
  --contract <scene.audit-contract.json> `
  --json-out <scene.audit.json>
```

An existing audit JSON is never replaced unless `--force` is explicit. Add `--require-pass` when a CI job must fail until both structural checks and native-backend runtime evidence pass. Without that flag a staging audit may be written with `structure_pass=true`, `backend_runtime_verified=false`, and `pass=false`.

The script uses only the Python standard library and confines scene, contract, source, runtime-evidence, and output paths to the current workspace.

## Companion contract

The audit contract is a separate JSON object. Keeping it separate prevents a backend from approving its own output.

```json
{
  "schema_version": "backend-scene-contract-v1",
  "backend": "visio_scenegraph",
  "source_svg": {
    "path": "../source/figure.svg",
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "canvas": {
    "width_mm": 180,
    "height_mm": 120,
    "tolerance_mm": 0.01
  },
  "texts": [
    {
      "id": "title",
      "text": "Experimental workflow",
      "font_family": "Times New Roman",
      "font_size_pt": 8.5
    }
  ],
  "connections": [
    {"id": "flow-a-b", "source_id": "node-a", "target_id": "node-b"}
  ],
  "object_counts": {
    "total_objects": 4,
    "text_objects": 1,
    "vector_objects": 2,
    "connector_objects": 1,
    "atomic_rasters": 1
  },
  "atomic_rasters": [
    {
      "id": "micrograph-a",
      "source_file": "../source/micrograph-a.png",
      "source_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
      "evidence": true,
      "raster_reason": "Immutable microscopy evidence.",
      "embedded_required": true
    }
  ],
  "backend_runtime": {
    "status": "not-run"
  }
}
```

`object_counts` may contain any subset of these computed metrics:

- `total_objects`: all content objects, excluding draw.io's structural cells `0` and `1`;
- `text_objects`: objects containing live text;
- `vector_objects`: non-connector, non-atomic objects; a text-bearing native shape is included;
- `edge_objects`: all mxGraph/SceneGraph edge objects, including geometric lines without declared semantic endpoints;
- `connector_objects`: semantic connector objects with declared endpoints;
- `atomic_rasters`: evidence image objects.

Text IDs in `texts` are an exact inventory. Content, font family, and point size are compared exactly, with a 0.01 pt size tolerance. Every connection is an exact `(id, source_id, target_id)` tuple, and endpoints must resolve to stable content-object IDs.

## Visio Scientific SceneGraph profile

The canonical JSON profile is:

```json
{
  "schema_version": "visio-scientific-scenegraph-v1",
  "backend": "visio_scenegraph",
  "metadata": {
    "source_svg": "../source/figure.svg",
    "source_svg_sha256": "...",
    "backend_runtime_verified": false
  },
  "page": {"width_mm": 180, "height_mm": 120},
  "objects": [
    {
      "id": "node-a",
      "kind": "shape",
      "text": {
        "content": "Input",
        "font_family": "Times New Roman",
        "font_size_pt": 8.5
      }
    },
    {
      "id": "flow-a-b",
      "kind": "connector",
      "source_id": "node-a",
      "target_id": "node-b"
    }
  ]
}
```

For compatibility, the auditor also recognizes common camelCase spellings, `shapes`/`nodes`, top-level `connectors`/`edges`, and page collections. Stable IDs must match `^[A-Za-z_][A-Za-z0-9_.:-]*$`; opaque numeric or regenerated IDs fail.

The strict TZ-mx / Visio-Illustrator adapter profile is also supported without adding fields that its upstream schema forbids:

```json
{
  "scene_id": "figure-07",
  "canvas": {"width_px": 1800, "height_px": 1000, "dpi": 254},
  "style_tokens": {},
  "layers": [],
  "nodes": [
    {
      "kind": "text",
      "semantic_id": "title",
      "text": "Experimental workflow",
      "rich_text": {
        "runs": [
          {"start": 0, "length": 21, "font_family": "Times New Roman", "font_size_pt": 8.499997}
        ]
      }
    }
  ],
  "connectors": [
    {"semantic_id": "flow-a-b", "source": "node-a", "target": "node-b", "glued": true}
  ],
  "regions": []
}
```

For this profile, physical millimetres are calculated from `width_px`, `height_px`, and `dpi`; missing or non-positive DPI leaves the canvas unverifiable. `semantic_id` is the stable object ID. For rich text, every run must resolve to one expected font family, while the largest run size is compared with the base 8.5 pt contract. This permits deliberately smaller scientific subscripts/superscripts but does not permit a fallback font to hide in them. The 0.01 pt tolerance accepts serialization noise such as `8.499997`; it does not change the requested type size.

When the strict scene cannot contain provenance fields, set `provenance_manifest` in the independent audit contract. The manifest must bind the exact `scene` / `scene_sha256` and `source_svg` / `source_svg_sha256`; stale or missing bindings fail closed.

An atomic object uses `kind="atomic_raster"` or `atomic_raster_unit=true` and declares `source_file`, `source_sha256`, `evidence=true`, and `raster_reason`. When a `data:image/...;base64,...` payload is present, its digest is checked. When `embedded_required=true`, absence of a decodable payload fails.

## draw.io mxGraph profile

Use an uncompressed `mxGraphModel`; compressed `<diagram>` text is rejected because its object and text contracts cannot be inspected safely.

Declare provenance and physical size on `<mxfile>` or `<mxGraphModel>`:

```xml
<mxfile data-source-svg="../source/figure.svg"
        data-source-svg-sha256="..."
        data-canvas-width-mm="180"
        data-canvas-height-mm="120"
        data-backend-runtime-verified="false">
```

If explicit millimetres cannot be emitted, the contract may set `canvas.drawio_page_unit="pt"`, or set `canvas.drawio_dpi` for pixel units. The auditor then converts `pageWidth`/`pageHeight`. Explicit millimetres are preferred.

An existing adapter manifest may carry the source/scene hashes instead of adding custom attributes to the tested mxGraph file. Set `provenance_manifest` in the independent contract. The auditor then requires that manifest's `source_svg` / `source_svg_sha256` and `drawio` / `drawio_sha256` bind the exact source and scene. An unbound or stale sidecar fails.

Each content `mxCell` needs a stable semantic ID. Live text must use plain `value`, `fontFamily=Times New Roman`, `fontSize=8.5`, and `html=0` in its style. `html=1`, tag-like content, `foreignObject`, compressed diagrams, external URLs, linked images, and other external references fail. Use native mxGraph `source` and `target` for semantic connectors when possible. The compatibility profile also resolves `data-source-svg-id` and `data-target-svg-id` through cells' `data-svg-id` mappings. Pure geometric edges remain countable `edge_objects` but do not satisfy a declared semantic connection.

An atomic cell declares these attributes or equivalent style keys:

```xml
<mxCell id="micrograph-a"
        data-atomic-raster-unit="true"
        data-evidence="true"
        data-source-file="micrograph-a.png"
        data-source-sha256="..."
        data-embedded-sha256="..."
        data-raster-reason="Immutable microscopy evidence." />
```

Data-URI image payloads are permitted; HTTP, file, and linked-image references are not.

## Native runtime evidence

`backend_runtime_verified` is false unless the contract sets `backend_runtime.status="verified"` and names an independent evidence JSON. A boolean written by the scene generator is never sufficient.

```json
{
  "backend": "drawio_mxgraph",
  "scene_sha256": "...",
  "runtime_version": "draw.io Desktop 26.x",
  "opened": true,
  "saved": true,
  "reopened": true,
  "object_counts": {
    "total_objects": 4,
    "text_objects": 1,
    "connector_objects": 1
  }
}
```

The evidence scene digest must match the audited scene, every checkpoint must be true, the runtime version must be recorded, and the evidence counts must exactly match the count keys selected by the companion contract. Missing, partial, stale, or backend-mismatched evidence keeps `backend_runtime_verified=false` and overall `pass=false`.

## Scientific safety boundary

- SceneGraph and mxGraph structure do not prove Illustrator Type objects or editable-PDF behavior.
- Embedded scientific atoms remain immutable evidence. The adapter may place them but may not inpaint, redraw, or silently convert them into a monolithic backdrop.
- A structural pass does not override translation approval, CJK font approval, annotation-occlusion approval, or other publication gates.
- Final SVG/AI/editable-PDF publication evidence still follows the shared quality and publication-gate contracts.

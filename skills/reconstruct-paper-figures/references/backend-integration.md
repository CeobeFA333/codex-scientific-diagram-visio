# Authoring backend integration

Use one backend-neutral reconstruction specification as the source of truth. The final publication proof still comes from Illustrator.

## Scientific Illustrator

Current upstream versions expose PowerPoint/WPS and draw.io backends, not Illustrator or Visio. They provide editable textboxes, shapes, connectors, tables, charts, groups, atomic images, staged drawing, audit, preview, and correction gates.

Use it for framework, mechanism, architecture, simple chart, and table geometry. Do not expect it to perform OCR, text removal, inpainting, or scientific texture reconstruction. Its draw.io text can use HTML/`foreignObject`, so do not accept exported draw.io SVG as Illustrator live text without conversion and inspection.

This Skill now includes `scripts/export_drawio_scene.py`, which writes a plain `html=0` mxGraphModel with stable SVG-ID mappings and fail-closed external-reference checks. FIG07's structural candidate contains 195 mapped objects, 33 plain TNR 8.5 pt text cells, 42 edges, 10 directly modeled semantic connectors, and zero images. The Scientific Illustrator/draw.io runtime was not installed or invoked, so this remains a structural backend candidate.

Before claiming native compatibility, follow [scientific-illustrator-native-verification.md](scientific-illustrator-native-verification.md). It requires a visible live session, inspection of stable cell IDs, one recorded edit, save/export, close, and reopen. Merely opening or pre-generating mxGraph XML is insufficient.

Primary sources:

- [Plugin MCP manifest](https://raw.githubusercontent.com/icebird1998/scientific-illustrator/main/plugins/scientific-illustrator/.mcp.json)
- [PowerPoint server](https://raw.githubusercontent.com/icebird1998/scientific-illustrator/main/plugins/scientific-illustrator/scripts/powerpoint-server.mjs)
- [Live draw.io server](https://raw.githubusercontent.com/icebird1998/scientific-illustrator/main/plugins/scientific-illustrator/scripts/live-server.mjs)
- [Figure recreation contract](https://raw.githubusercontent.com/icebird1998/scientific-illustrator/main/plugins/scientific-illustrator/skills/recreate-scientific-figure/SKILL.md)
- [Audit contract](https://raw.githubusercontent.com/icebird1998/scientific-illustrator/main/plugins/scientific-illustrator/skills/audit-scientific-figure/SKILL.md)

## Visio Illustrator

The public [TZ-mx/Visio-Illustrator](https://github.com/TZ-mx/Visio-Illustrator) project is a strong candidate for framework-heavy figures. It documents a Windows x64 Visio COM bridge, stable IDs, GlueTo connectors, rich-text runs, native Geometry, SceneGraph input, region checkpoints, fidelity validation, and SVG/PDF export.

Use it as a geometry backend for diagrams that benefit from Visio routing and semantic shapes. Visio fixed-format PDF is a static view; SVG/PDF export does not by itself prove Illustrator Type objects. Recreate or normalize final text from the shared spec in Illustrator-friendly SVG.

This Skill now includes `scripts/export_visio_scene.py`, `scripts/run_visio_scene_mcp.mjs`, and the shared `scripts/audit_backend_scene.py`. On 2026-08-26, the pinned upstream commit was cloned and built in a temporary directory, then exercised against registered desktop Visio 16.0. FIG07 V2 passed saved-file validation and fidelity at 150/150 semantic objects, 34/34 glued connectors and zero text mismatches. The plugin was not permanently installed.

Real execution exposed compatibility rules now enforced by the adapter: `kind` must serialize first for the .NET polymorphic reader; `LineJoin` is not universal; nested groups and global z-order are unsafe in the pinned executor; grouped text must be scheduled before its group; large live/file inspection can exceed 30 seconds; and connector endpoints need normalized anchors for visual fidelity. Use the V2 preview and visual review in `organized/figures/fig07/backend/` as the regression evidence.

## Illustrator

Use Illustrator for final physical sizing, exact font assignment, layered assembly, AI save, editable PDF save, and representative Type-object testing. Never enable Convert To Outlines for required editable text. Preserve Illustrator editing data in the PDF when the contract requires future editing.

## Recommended adapter architecture

```text
PDF inventory / OCR / cleanup
              |
      reconstruction_spec
        /        |        \
 Illustrator   Visio   Scientific Illustrator
      SVG       scene      scene
        \        |        /
             Illustrator QA
          AI + editable PDF + SVG
```

Adapters may differ in authoring behavior, but IDs, physical dimensions, text content, font properties, raster reasons, z-order, and acceptance checks must come from the same spec.

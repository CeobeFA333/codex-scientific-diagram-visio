# Figure reconstruction decision matrix

| Class | Typical content | Preserve as raster | Rebuild as vector | Preferred authoring path |
|---|---|---|---|---|
| Native PDF vector | PDF paths and live text already exist | None | Only damaged/missing items | Extract page region, normalize groups in Illustrator |
| Framework/schematic | Blocks, arrows, tensors, flow diagrams | Only photos or irreducible icons | All geometry and text | Scientific Illustrator / Visio / SVG generator, then Illustrator |
| Chart with data | 2D plots and legends | Optional heatmap/3D surface | Axes, ticks, labels, legend, curves from data | Plot from data; digitize only if data is absent |
| Microscopy/photo composite | SEM/TEM/EDS, photos, detection results | Continuous-tone panels | Scale bars, labels, arrows, boxes, tables, panel letters | Hybrid SVG recipe + Illustrator |
| Experimental setup | Photos mixed with CAD/line diagrams | Equipment photos and textures | Diagram lines, callouts, labels, borders, inset connectors | Panel-by-panel hybrid reconstruction |
| Circular infographic | Concentric rings, sectors, icons, curved labels | Only irreducible texture/icons | Rings, sectors, separators, arrows, live text | Full SVG/Illustrator redraw |
| 3D surface screenshot | Rendered surface without source data | Surface and contour projection | All axes, ticks, labels, markers, callout boxes | Hybrid SVG; never claim recovered numeric data |

## Choosing cleanup mode

- First import OCR exports with `build_text_detection_manifest.py`; OCR agreement proposes text and geometry but never authorizes erasure.
- `solid_fill`: use only for a known uniform, non-evidence background.
- `border_median`: use only when the external-ring variance gate passes on a locally flat, non-evidence patch.
- `horizontal_linear` / `vertical_linear`: use only when both boundary anchors belong to the same simple background and the boundary-delta gate passes.
- `clone`: keep as a separate, manually reviewed experiment on non-evidence texture. The safe cleanup executor intentionally does not implement it.
- External inpainting, content-aware fill, or generative fill: never use to claim recovery of microscopy, photographs, plots, specimens, equipment details, or other scientific evidence. Request a clean source, preserve the original atom, or use a reversible audited occlusion plate on a uniform annotation patch.
- Manual redraw: use when cleanup removes a gridline, axis, table rule, border, or repeated structure.

For actual pixel cleanup, require both the executor audit and the independent `audit_text_cleanup.py` report. Both must show zero changed pixels outside the declared binary mask; neither can grant publication readiness.

Treat OCR as a proposal generator. Confirm every scientific symbol, superscript, decimal point, unit, and panel label against the source.

## Tool boundaries

Scientific Illustrator is well matched to framework-heavy figures because it prioritizes native text, shapes, connectors, tables, and charts, and recommends retaining only minimal irreducible raster regions. It targets PowerPoint/WPS/draw.io, so use it as an authoring accelerator rather than the final proof of Illustrator/PDF editability.

Visio is similarly useful for block diagrams and connectors. It is not a text-removal or textured-image reconstruction engine. Validate its PDF/SVG exports in Illustrator because export paths and fonts can change.

Illustrator is the final assembly and acceptance application for this workflow because the client explicitly requires editable text and an editable high-resolution PDF.

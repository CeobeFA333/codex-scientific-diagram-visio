# Paper Figure Reconstruction Demo

This example demonstrates the actual `reconstruct-paper-figures` workflow added in v1.3.0. The animated GIF and MP4 are evidence-driven presentations assembled from committed reconstruction previews and machine-readable audits. They are not represented as a screen recording of Adobe Illustrator.

![Evidence-driven paper figure reconstruction demo](assets/paper-figure-reconstruction-demo.gif)

- [MP4 demo](assets/paper-figure-reconstruction-demo.mp4)
- [Portable editable SVG](assets/simpli-figure4-portable.svg)
- [Editable PDF](assets/simpli-figure4-editable.pdf)
- [Illustrator evidence JSON](assets/simpli-figure4-evidence.json)
- [Demo manifest](assets/demo-manifest.json)

## What is shown

- Native PDF inventory before reconstruction.
- Hybrid reconstruction with editable paths and live text while continuous-tone microscopy remains in three linked, hash-bound image atoms.
- Source-data-bound reconstruction of Q-Q, box, violin, Kaplan–Meier, heatmap, PCA, t-SNE, and Ward-clustering figures.
- Reviewed OCR cleanup constrained to 2,010 mask pixels, with 1,206 changed pixels inside the mask and zero outside-mask changes.
- Adobe Illustrator 29.8.2 three-stage evidence: SVG import, AI reopen, and editable-PDF reopen each report 102 text frames, 4,466 paths, 15 groups, 3 placed items, 0 raster items, and 0 warnings.
- A fail-closed publication gate. The showcased SIMPLI artifact remains `publication_ready=false` with six explicit blockers; machine QA does not claim scientific approval.

## Rebuild the GIF

The script needs Pillow and two local audit inputs. The cleanup audit is intentionally not redistributed because its source paths belong to the private reconstruction workspace.

```powershell
python scripts/make_workflow_demo.py `
  --simpli-preview assets/simpli-figure4-preview.png `
  --stats-preview assets/tomicsvis-statistical-suite-preview.png `
  --evidence assets/simpli-figure4-evidence.json `
  --cleanup-audit path/to/text-cleanup-audit.json `
  --output assets/paper-figure-reconstruction-demo.gif `
  --workspace path/to/a/common/safe/workspace
```

Convert the generated GIF to the committed browser-compatible MP4 with an FFmpeg build that includes `libx264`:

```powershell
ffmpeg -y -i assets/paper-figure-reconstruction-demo.gif `
  -an -c:v libx264 -pix_fmt yuv420p -r 30 -movflags +faststart `
  assets/paper-figure-reconstruction-demo.mp4
```

The prebuilt GIF, MP4, previews, editable outputs, public evidence JSON, and manifest are committed so users can inspect the demonstration without the private workspace.

## Source and license notices

The software and presentation code in this repository are MIT licensed.

The SIMPLI demonstration is adapted from Bortolomeazzi et al., “A SIMPLI (Single-cell Identification from MultiPLexed Images) approach for spatially-resolved tissue phenotyping at single-cell resolution,” *Nature Communications* 13, 781 (2022), <https://doi.org/10.1038/s41467-022-28470-x>, under CC BY 4.0. Typography, layout, and reconstruction structure were modified.

The statistical-suite demonstration is adapted from Miao et al., Figure 2, *iMeta* e137 (2023), <https://doi.org/10.1002/imt2.137>, under CC BY 4.0. Typography and layout were modified.

The third-party figure adaptations remain under CC BY 4.0; the repository's MIT license applies to the software and original project material, not as a relicensing of those adaptations.

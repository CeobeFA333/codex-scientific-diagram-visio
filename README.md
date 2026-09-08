# Codex Scientific Diagram Visio

<p align="right">
  <strong>English</strong> | <a href="README.zh-CN.md">简体中文</a>
</p>

Evidence-first Codex workflows for turning model code, manuscripts, paper PDFs, source data, and legacy figures into editable scientific graphics.

[Release v1.3.2](https://github.com/CeobeFA333/codex-scientific-diagram-visio/releases/tag/v1.3.2) · [MIT license](LICENSE) · [Research-group trial guide](TEAM-TRIAL.md)

> Verify the science before drawing. Preserve editability after export. Never let visual polish silently change the method.

## What you receive

This is a plugin containing **three focused skills**, not one giant context-heavy skill. Codex loads the skill that matches the task.

| Workflow | Typical input | Deliverables |
|---|---|---|
| Verify and design a model diagram | Code, configuration, equations, manuscript text, old figure | Evidence table, conflict list, tensor/model contract, visual-reference prompt, editable reconstruction specification |
| Build or revise native Visio | Verified contract, reference image, or existing VSDX | Native editable VSDX, reopened-object QA, PDF, 300-DPI PNG, inspection report, and versioned backup for revisions |
| Reconstruct a paper figure | Paper PDF, extracted assets, source data, OCR review, legacy raster/vector figure | Figure inventory, reconstruction recipe, editable SVG, optional AI/editable PDF, atomic raster evidence, QA reports, and explicit publication blockers |

The skills are:

- `scientific-model-diagram-prompting` — reconciles scientific evidence and produces the drawing contract.
- `scientific-model-diagram-visio` — constructs, revises, reopens, and exports native Microsoft Visio figures.
- `reconstruct-paper-figures` — rebuilds dense paper figures while preserving scientific pixels and source-data provenance.

## Install

Install the versioned plugin from this repository marketplace:

```powershell
codex plugin marketplace add CeobeFA333/codex-scientific-diagram-visio --ref v1.3.2
codex plugin add codex-scientific-diagram-visio@ceobefa-scientific-tools
```

Restart Codex or the ChatGPT desktop app and start a new task. To install all three skills with the open Agent Skills CLI instead:

```bash
npx skills add CeobeFA333/codex-scientific-diagram-visio
```

Individual skill URLs and group-rollout instructions are in the [trial guide](TEAM-TRIAL.md).

## Choose a workflow

### 1. Audit before drawing

```text
Use $scientific-model-diagram-prompting to compare my model code,
configuration, manuscript equations, and current figure. Return the
authoritative model contract, tensor audit, conflicts, and a reconstruction
specification. Stop before drawing if a material contradiction remains.
```

### 2. Build or revise an editable VSDX

```text
Use $scientific-model-diagram-visio to rebuild this verified contract as a
native editable VSDX. Keep repeated branches aligned, operators independent,
and connectors glued. Reopen the file, test editability, then export PDF and
a 300-DPI PNG.
```

### 3. Reconstruct a multi-panel paper figure

```text
Use $reconstruct-paper-figures to inventory this PDF and rebuild the selected
figure as editable SVG, Illustrator AI, and editable PDF. Preserve continuous-
tone scientific evidence as minimal hash-bound atoms, bind plots to supplied
source data, and keep unresolved review items as publication blockers.
```

## Verified demonstrations

### Paper/code to native Visio

This Microsoft Visio capture shows Codex reading a verified Transformer Encoder contract, generating an optional style reference, constructing the page from native shapes, reopening the VSDX, and selecting editable objects.

![Paper and code to editable Visio workflow](examples/transformer-encoder-demo/assets/workflow-demo.gif)

[Reproduce the example](examples/transformer-encoder-demo/) · [Download VSDX](examples/transformer-encoder-demo/assets/transformer-encoder-demo.vsdx) · [View PDF](examples/transformer-encoder-demo/assets/transformer-encoder-demo.pdf) · [Inspect the documented usage example](examples/transformer-encoder-demo/COST-EXAMPLE.md)

The documented `gpt-5.6-terra` + one medium `gpt-image-2` reference + local Visio scenario is approximately **$0.32 API-equivalent cost** under its stated assumptions. Local Visio automation itself uses no model tokens; subscription limits are not a fixed token-to-credit conversion.

### Evidence-preserving paper reconstruction

The v1.3.2 presentation below is assembled from committed reconstruction artifacts and machine-readable audits. It demonstrates a ten-panel hybrid biological figure, an editable statistical suite, reviewed OCR cleanup evidence, and three-stage Illustrator reopen counts. It is **not** presented as an Illustrator screen recording.

![Paper figure reconstruction capabilities](examples/paper-figure-reconstruction-demo/assets/paper-figure-reconstruction-demo.gif)

[Open the example](examples/paper-figure-reconstruction-demo/) · [Watch MP4](examples/paper-figure-reconstruction-demo/assets/paper-figure-reconstruction-demo.mp4) · [Inspect evidence JSON](examples/paper-figure-reconstruction-demo/assets/simpli-figure4-evidence.json)

The showcased artifact deliberately remains `publication_ready=false`: passing machine QA does not replace source-data, scale-bar, or human scientific approval.

## 64-family editable capability atlas

The repository's real recipe builder deterministically generated **8 full-size SVG sheets covering 64 figure families**. Every card has semantic IDs, live text, editable vector geometry, a recipe hash, an object count, and a real-task planning estimate; the manifest requires **zero embedded raster nodes**. These are synthetic capability tests, not claims that 64 papers were reproduced pixel-for-pixel.

Click the sheet below to open the original SVG and zoom without raster blur.

[![AI, machine-learning, and computer-vision capability sheet](examples/capability-atlas/assets/ai-computer-vision.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/ai-computer-vision.svg)

<details>
<summary><strong>Open all 8 full-size, click-to-zoom domain sheets</strong></summary>

### AI / machine learning / computer vision

[![AI and computer-vision figure families](examples/capability-atlas/assets/ai-computer-vision.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/ai-computer-vision.svg)

### Statistics / data science

[![Statistics and data-science figure families](examples/capability-atlas/assets/statistics-data-science.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/statistics-data-science.svg)

### Clinical / biomedical

[![Clinical and biomedical figure families](examples/capability-atlas/assets/clinical-biomedical.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/clinical-biomedical.svg)

### Cell / molecular / omics

[![Cell, molecular, and omics figure families](examples/capability-atlas/assets/cell-molecular-omics.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/cell-molecular-omics.svg)

### Chemistry / materials / electrochemistry

[![Chemistry and materials figure families](examples/capability-atlas/assets/chemistry-materials.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/chemistry-materials.svg)

### Engineering / physics

[![Engineering and physics figure families](examples/capability-atlas/assets/engineering-physics.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/engineering-physics.svg)

### Experimental systems / microfluidics

[![Experimental-system and microfluidic figure families](examples/capability-atlas/assets/experimental-systems.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/experimental-systems.svg)

### Earth science / geospatial

[![Earth-science and geospatial figure families](examples/capability-atlas/assets/earth-geospatial.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/earth-geospatial.svg)

</details>

[Open the local full-width gallery](examples/capability-atlas/gallery.html) · [Read the atlas guide](examples/capability-atlas/) · [Inspect the 64-family manifest and SHA-256 evidence](examples/capability-atlas/capability-manifest.json)

### Domains and detailed figure families

“Supported” means the workflow can classify the figure, choose an evidence-preserving route, and produce an editable specification or artifact. Lossless recovery still depends on source vectors/data, calibration, and scientific review.

| Domain | Figure families represented in the atlas |
|---|---|
| AI / machine learning / computer vision | Neural architectures; encoder–decoder and U-Net; feature maps; residual paths; Q/K/V attention; multimodal fusion; detection boxes/classes/keypoints; segmentation, depth, and probability maps |
| Statistics / data science | Line/scatter/fitted curves; error bars and confidence intervals; bar/box/violin/ROC; Kaplan–Meier/forest/risk tables; heatmaps and matrices; PCA/t-SNE; dendrogram/network/phylogeny; Circos-style rings |
| Clinical / biomedical | Cohort and randomization flows; forest plots; flow-cytometry gates; CT/MRI/PET/ultrasound overlays; histology; ROI/segmentation; risk tables; study timelines |
| Cell / molecular / omics | Fluorescence/confocal and multiplex microscopy; Western blots; electrophoresis; genomic matrices; phylogenetics; protein renders; ligand interactions |
| Chemistry / materials / electrochemistry | Chemical structures; reaction schemes; XRD/Raman/FTIR/XPS; MS/chromatography; DSC/TGA/DTA; CV/EIS/Nyquist; SEM/TEM/AFM; EDS maps |
| Engineering / physics | Circuits; control systems; wiring; FEA; CFD; response surfaces; CAD drawings; exploded assemblies and BOM callouts |
| Experimental systems / microfluidics | Experimental setups; microfluidic channels; layered devices; sensor chains; device-photo panels; composite figures; process principles; measurement layouts |
| Earth science / geospatial | GIS maps; remote sensing; DEM/terrain; geology; seismic maps; cross-sections; graticules/north arrows/scales; cartographic legends |

### Consumption labels

| Tier | Planning range for a real task | Typical scope |
|---|---|---|
| S | 15–35k agent tokens; 0–1 optional visual reference | Single-panel, mostly vector, limited evidence reconciliation |
| M | 35–75k; 0–2 references | Multi-layer figure, source inspection, one editor QA pass |
| L | 75–150k; 1–4 references | Dense or image-bearing figure, scientific review, editor roundtrips and rework |
| S/M or M/L | Spans adjacent tiers | Complexity depends on real data, source quality, linked panels, and acceptance requirements |

These are planning ranges, not prices or usage guarantees. Generating the committed atlas uses deterministic local Python and **0 model/API calls**.

## Editable objects and scientific symbols

The workflow constructs components from explicit vector primitives and semantic IDs rather than depending on a closed icon library.

<details>
<summary><strong>Browse the drawable object catalog</strong></summary>

| Family | Editable components |
|---|---|
| Core primitives | Rectangles, ellipses, polygons, lines, polylines, cubic/arc paths, annular sectors, groups, gradients, straight/path text, subscript and superscript runs |
| Flow and relationships | Straight/orthogonal arrows, glued connectors, branches, merges, residual/skip and feedback paths, leaders, brackets, ROI boxes, dashed enclosures, junctions |
| Model architecture | 3D tensor cuboids, encoder/decoder stages, projection/weight matrices, bias vectors, attention, normalization, convolution/pooling, classifier heads, parallel branches, multimodal fusion |
| Mathematics | Independent `×`, `+`, `Σ`, concatenation `‖`, equality, formulas, matrices, dimensions, Greek letters, primes, subscripts, superscripts |
| Statistics | Axes, ticks, grids, markers, error bars, confidence intervals, censor marks, fitted curves, legends, significance brackets, p-values, mean/variance/skewness/kurtosis mini-plots |
| Matrices, graphs, circles | Heatmap and confusion/correlation cells, dendrograms, networks, phylogenetic branches, rings, sectors, radial labels, color bars |
| Image/measurement overlays | Panel letters, channel labels, scale bars, orientation marks, ROIs, segmentation boundaries, gates, keypoints, class/confidence labels, peak/reference markers |
| Apparatus and engineering | Containers, pipes/channels, circuit wires, instrument blocks, boundary/load arrows, dimensions, section markers, exploded-view leaders, BOM identifiers |
| Chemistry and molecular | Bonds, rings, stereochemical wedges, reaction arrows, condition/yield text, residue/ligand labels, dashed interaction bonds |
| Maps | Boundaries, points, section lines, graticules, north arrows, scale bars, legends, fault traces, epicenters |

</details>

## Authoring backends and validation scope

| Backend | Current capability | Evidence level |
|---|---|---|
| Microsoft Visio | Native shapes, groups and glued connectors; VSDX save/reopen; SVG/PDF/PNG export | **Native runtime validated** with desktop Visio 16.0 on Windows |
| Adobe Illustrator | SVG import; AI save/reopen; editable-PDF export/reopen; object, font and path audits; constrained path-text repair | **Roundtrip validated** with Illustrator 29.8.2 on Windows |
| SVG + editable PDF | Portable vector/hybrid assembly, live text, physical sizing, hashes, and structural audits | **Portable core implemented**; target-editor inspection remains required |
| draw.io / diagrams.net | Supported SVG subset to editable `mxGraphModel` with stable IDs, layers, text, connectors, manifests, and fail-closed audit | **Structural adapter implemented**; live import/save/reopen validation pending |
| Scientific Illustrator | Backend-neutral scene contract for framework-heavy workflows | **Integration contract documented**; runtime is not bundled or claimed as validated |
| PowerPoint / WPS | Possible intermediate framework editor through compatible external workflows | **No direct controller**; not a publication-acceptance backend here |
| Inkscape / Figma / Affinity / CorelDRAW | May import exported SVG/PDF according to each editor's compatibility | **Not automated or regression-tested** |
| ChemDraw/RDKit / PyMOL/ChimeraX / CAD/GIS | Candidate semantic backends for chemistry, molecular rendering, assemblies, and maps | **Planned, not implemented** |

## Evidence and acceptance model

For paper figures, recovery is recorded per panel:

| Level | Meaning |
|---|---|
| R0 | Recover native PDF text/vector geometry |
| R1 | Regenerate from authoritative source data |
| R2 | Approximate digitization, explicitly labelled as such |
| R3 | Preserve immutable scientific pixels as minimal hash-bound atoms |

A single figure may mix several levels. The workflow separates inventory, reconstruction, editor roundtrip, visual QA, and scientific approval. Missing data, calibration, scale bars, fonts, or human review stay visible as blockers; machine audits never grant publication readiness by themselves.

## Requirements and project scope

- Codex with Agent Skills or Plugins support.
- Python 3.8+ for portable scripts; PDF inventory/rendering needs the optional packages documented by the skill.
- Windows + Microsoft Visio for native VSDX construction and GUI verification.
- Adobe Illustrator is optional and required only for the currently validated AI/editable-PDF roundtrip profile.
- Image generation is optional and used only as a visual reference, never as scientific ground truth.

The packaged plugin is local and skills-only: it runs no publisher-operated server, creates no account, and collects no telemetry. It may read only the artifacts placed in scope and may control Visio or Illustrator when the selected workflow requires it. Keep confidential papers, data, code, credentials, and model weights out of public issues.

See [DESIGN.md](DESIGN.md), [SECURITY.md](SECURITY.md), [PRIVACY.md](PRIVACY.md), [TERMS.md](TERMS.md), and [CHANGELOG.md](CHANGELOG.md) for engineering boundaries and release history.

## Repository layout

```text
skills/                                      canonical skill sources
plugins/codex-scientific-diagram-visio/      synchronized Marketplace package
examples/transformer-encoder-demo/           reproducible native-Visio example
examples/paper-figure-reconstruction-demo/   evidence-driven reconstruction demo
examples/capability-atlas/                    8-domain, 64-family editable SVG atlas
scripts/validate_release.py                   release and mirror validation
tests/                                        standard-library regression tests
```

## Version and license

The latest tagged plugin release is **v1.3.2**. The `main` branch also contains the newer deterministic capability atlas and homepage documentation queued under `Unreleased`; a code release does not change any figure's scientific or publication status.

Source code and original project material are released under the [MIT License](LICENSE). Third-party demonstration figures retain the licenses and attribution stated in their example directories.

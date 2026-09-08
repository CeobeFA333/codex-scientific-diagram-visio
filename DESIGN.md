# Design

## Goal

Provide reusable Codex workflows that turn model code, configuration, manuscript evidence, paper PDFs, source data, and legacy figures into scientifically verified editable scientific graphics with explicit application and publication gates.

## Why this repository exists

Raster image generation is effective for visual exploration but cannot guarantee model fidelity, exact tensor dimensions, connector semantics, or post-export editability. This project separates evidence verification, visual-reference design, native Visio reconstruction, and final quality assurance into explicit gates.

## Responsibilities

- Audit architecture logic and tensor dimensions before drawing.
- Produce a structured visual and reconstruction specification.
- Build or revise VSDX files with native Visio objects on Windows.
- Inventory PDF figure internals and rebuild hybrid SVG, Illustrator AI, and editable PDF outputs without replacing scientific evidence pixels.
- Bind statistical reconstructions to publisher source data and reviewed text cleanup to pixel-level audits.
- Verify routing, readability, exports, package structure, and reopened editability.
- Package the workflows for Agent Skills and Codex Plugin distribution.

The project does not train models, replace scientific peer review, provide a hosted service, or guarantee compatibility with every vector editor.

## Architecture

The plugin contains three focused skills:

1. `scientific-model-diagram-prompting` owns evidence reconciliation, scientific visual language, optional image-reference prompting, and the handoff specification.
2. `scientific-model-diagram-visio` owns Microsoft Visio construction, local revision, export, and editability QA.
3. `reconstruct-paper-figures` owns paper-figure inventory, hybrid vector/raster reconstruction, source-data plotting, reviewed OCR cleanup, editor roundtrips, and publication gates.

The repository root is the canonical development source. A compact mirrored plugin under `plugins/codex-scientific-diagram-visio` supports repository Marketplace installation. `scripts/validate_release.py` fails when the canonical and Marketplace copies diverge. `scripts/build_release.ps1` creates a compact plugin ZIP and a larger research-group trial ZIP.

## Key decisions

### Evidence before aesthetics

Executed model structure and training configuration outrank manuscript prose, old diagrams, and generated visual references. This prevents attractive figures from silently changing the implemented method.

### Skills-only plugin

The workflow needs packaged procedures and local application control, not a publisher-operated MCP server. A skills-only plugin reduces credential, network, privacy, and maintenance requirements.

### Three focused skills instead of one large skill

Architecture analysis, native Visio execution, and evidence-preserving reconstruction of published multi-panel figures have different triggers, tools, platform constraints, and completion criteria. Splitting them improves discovery and keeps each instruction file focused.

### Hybrid evidence preservation

Continuous-tone microscopy and other scientific pixels are retained as minimal, hash-bound atoms when vectorization would alter evidence. Text, diagram geometry, and source-data-bound plots are rebuilt as editable objects. Missing data and unresolved scale bars remain blockers instead of being inferred.

### Native Visio objects

Generated images are references only. Containers, cuboid faces, operators, labels, and connectors must remain independent editable objects, with functional connectors glued to connection points.

### Deterministic packaging and inspection

Repeated layout and packaging work uses scripts. Static VSDX inspection supplements, but does not replace, reopening the document and visually testing individual objects.

## Dependencies

- Codex with Skills or Plugins support.
- Windows and Microsoft Visio for native VSDX execution.
- Python 3.8+ for portable core scripts; optional PDF packages are required for PDF inventory and rendering workflows.
- PowerShell for the reproducible release builder and Visio COM example.
- Adobe Illustrator 29.8.2 on Windows for the currently validated SVG/AI/editable-PDF three-stage roundtrip.
- Image generation is optional and supplied by the user's existing environment.

## Security and privacy boundary

The packaged plugin does not operate a server or collect telemetry. It may direct the user's agent to read explicitly scoped artifacts and create files in a user-selected work directory. Users remain responsible for protecting manuscripts, code, datasets, credentials, and model weights. See `SECURITY.md`, `PRIVACY.md`, and `TERMS.md`.

## Known limitations

- Native construction and GUI editability testing require Windows and Microsoft Visio.
- Validated Illustrator roundtrip evidence currently covers Windows and Illustrator 29.8.2; other versions require fresh evidence.
- Static XML inspection cannot prove visual absence of overlap or correct routing.
- Model inconsistencies may require author judgment before drawing can continue.
- Image-generated references may corrupt text or formulas and must not become the source of truth.
- Machine audits do not grant publication readiness; source-data gaps, scale bars, and scientific interpretation may require authors or editors.
- The compact Marketplace plugin mirrors canonical skill files, so every release must run synchronization validation.

## Change history

### 2026-09-08 — v1.3.0 paper figure reconstruction

Added the `reconstruct-paper-figures` skill, deterministic standalone MIT package metadata, PDF inventory and hybrid reconstruction workflows, source-data and OCR safety contracts, Illustrator roundtrip evidence, CC BY demonstration artifacts, and an evidence-driven GIF/MP4 capability demo.

### 2026-08-13 — v1.2.0 Marketplace and team distribution

Added a repository Marketplace, compact plugin mirror, deterministic ZIP builder, research-group trial guide, public privacy/terms pages, and synchronization checks. This makes the project installable through native Codex Plugin commands while retaining direct Agent Skills distribution.

### 2026-08-13 — v1.1.x reproducible demonstration

Added a Transformer Encoder demonstration with native VSDX/PDF/PNG artifacts, Visio automation, animated workflow capture, straight-connector correction, and usage-cost documentation.

### 2026-08-13 — v1.0.0 initial design

Introduced the evidence-first prompting skill and native Visio reconstruction skill.

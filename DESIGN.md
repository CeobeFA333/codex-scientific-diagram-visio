# Design

## Goal

Provide a reusable Codex workflow that turns model code, configuration, manuscript evidence, and legacy figures into scientifically verified, publication-ready Microsoft Visio diagrams whose components remain natively editable.

## Why this repository exists

Raster image generation is effective for visual exploration but cannot guarantee model fidelity, exact tensor dimensions, connector semantics, or post-export editability. This project separates evidence verification, visual-reference design, native Visio reconstruction, and final quality assurance into explicit gates.

## Responsibilities

- Audit architecture logic and tensor dimensions before drawing.
- Produce a structured visual and reconstruction specification.
- Build or revise VSDX files with native Visio objects on Windows.
- Verify routing, readability, exports, package structure, and reopened editability.
- Package the workflows for Agent Skills and Codex Plugin distribution.

The project does not train models, replace scientific peer review, provide a hosted service, or guarantee compatibility with every vector editor.

## Architecture

The plugin contains two focused skills:

1. `scientific-model-diagram-prompting` owns evidence reconciliation, scientific visual language, optional image-reference prompting, and the handoff specification.
2. `scientific-model-diagram-visio` owns Microsoft Visio construction, local revision, export, and editability QA.

The repository root is the canonical development source. A compact mirrored plugin under `plugins/codex-scientific-diagram-visio` supports repository Marketplace installation. `scripts/validate_release.py` fails when the canonical and Marketplace copies diverge. `scripts/build_release.ps1` creates a compact plugin ZIP and a larger research-group trial ZIP.

## Key decisions

### Evidence before aesthetics

Executed model structure and training configuration outrank manuscript prose, old diagrams, and generated visual references. This prevents attractive figures from silently changing the implemented method.

### Skills-only plugin

The workflow needs packaged procedures and local application control, not a publisher-operated MCP server. A skills-only plugin reduces credential, network, privacy, and maintenance requirements.

### Two skills instead of one large skill

Analysis/prompting and Visio execution have different triggers, tools, platform constraints, and completion criteria. Splitting them improves discovery and keeps each instruction file focused.

### Native Visio objects

Generated images are references only. Containers, cuboid faces, operators, labels, and connectors must remain independent editable objects, with functional connectors glued to connection points.

### Deterministic packaging and inspection

Repeated layout and packaging work uses scripts. Static VSDX inspection supplements, but does not replace, reopening the document and visually testing individual objects.

## Dependencies

- Codex with Skills or Plugins support.
- Windows and Microsoft Visio for native VSDX execution.
- Python 3.9+ for the optional standard-library VSDX inspector and release validation.
- PowerShell for the reproducible release builder and Visio COM example.
- Image generation is optional and supplied by the user's existing environment.

## Security and privacy boundary

The packaged plugin does not operate a server or collect telemetry. It may direct the user's agent to read explicitly scoped artifacts and create files in a user-selected work directory. Users remain responsible for protecting manuscripts, code, datasets, credentials, and model weights. See `SECURITY.md`, `PRIVACY.md`, and `TERMS.md`.

## Known limitations

- Native construction and GUI editability testing require Windows and Microsoft Visio.
- Static XML inspection cannot prove visual absence of overlap or correct routing.
- Model inconsistencies may require author judgment before drawing can continue.
- Image-generated references may corrupt text or formulas and must not become the source of truth.
- The compact Marketplace plugin mirrors canonical skill files, so every release must run synchronization validation.

## Change history

### 2026-08-13 — v1.2.0 Marketplace and team distribution

Added a repository Marketplace, compact plugin mirror, deterministic ZIP builder, research-group trial guide, public privacy/terms pages, and synchronization checks. This makes the project installable through native Codex Plugin commands while retaining direct Agent Skills distribution.

### 2026-08-13 — v1.1.x reproducible demonstration

Added a Transformer Encoder demonstration with native VSDX/PDF/PNG artifacts, Visio automation, animated workflow capture, straight-connector correction, and usage-cost documentation.

### 2026-08-13 — v1.0.0 initial design

Introduced the evidence-first prompting skill and native Visio reconstruction skill.

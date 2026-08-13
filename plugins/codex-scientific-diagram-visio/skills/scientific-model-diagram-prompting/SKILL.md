---
name: scientific-model-diagram-prompting
description: Create, redesign, and iteratively improve publication-ready scientific model diagrams, architecture figures, method frameworks, neural-network pipelines, and research infographics from papers, sketches, screenshots, or textual model descriptions. Use when Codex needs to analyze scientific logic, preserve equations and dimensions, design a coherent layout and color system, generate or edit a reference image, correct scientifically misleading icons or plots, or produce a structured prompt/specification for later editable vector or Visio reconstruction. This skill covers the pre-Visio design and prompting phase, not GUI drawing execution.
---

# Scientific Model Diagram Prompting

Turn scientific model logic into a publication-ready visual reference and a precise reconstruction specification. Preserve scientific meaning before improving appearance.

## Scope

Handle the pre-production half of the workflow:

1. Analyze the model and source figure.
2. Freeze semantic invariants.
3. Design layout, hierarchy, shapes, colors, and typography.
4. Generate or edit a polished raster reference when image generation is available.
5. Inspect and iterate on scientific and visual defects.
6. Produce a structured prompt/specification for editable vector or Visio reconstruction.

Do not claim to have created editable Visio/vector objects unless the corresponding application or file-generation workflow was actually used.

## Workflow

### 1. Inventory the source

Identify:

- figure purpose and target venue;
- reading direction and stage hierarchy;
- modules, branches, equations, symbols, dimensions, inputs, and outputs;
- text that must remain verbatim;
- visual problems such as crowding, weak hierarchy, repeated icons, inconsistent depth, or crossed arrows.

If an image is supplied, inspect it at original detail before drafting or editing.

### 2. Freeze invariants

Write a compact invariant list before changing the design. Include:

- stage order and model logic;
- branch count and correspondence;
- exact mathematical symbols, subscripts, primes, and dimensions;
- required labels and captions;
- relationships that must remain connected.

Treat these as hard constraints in every generation or revision prompt.

### 3. Select the visual grammar

Choose one consistent grammar for the figure:

- flat vector-like scientific infographic for overview/framework figures;
- shallow isometric cuboids for tensor, feature-map, or architecture figures;
- restrained hybrid only when the distinction carries meaning.

Do not mix flat cards, glossy 3D blocks, and unrelated icon styles arbitrarily. Read [scientific-visual-language.md](references/scientific-visual-language.md) when selecting plots, cuboids, colors, typography, and connectors.

### 4. Build the layout specification

Define:

- canvas orientation and approximate aspect ratio;
- major container proportions;
- grid, margins, gutters, row heights, and alignment anchors;
- left-to-right or top-to-bottom flow;
- repeated geometry for parallel branches;
- caption and legend placement.

For parallel branches, require identical geometry and spacing. For dense equations, split operands and operators into separate objects rather than placing a full expression in one block.

### 5. Make scientific icons definition-driven

Never use the same generic bell curve for distinct statistics. Derive each miniature diagram from its definition or function.

For statistical moments:

- mean `μ`: emphasize central location with a center line or marker;
- variance `σ²`: emphasize spread with a wider curve and a width arrow;
- skewness `γ`: emphasize asymmetry with an unmistakable one-sided long tail;
- kurtosis `κ`: emphasize peakedness and tail weight with a symmetric sharp peak and heavier tails, optionally against a faint reference curve.

Apply the same principle to attention, projection, fusion, uncertainty, frequency, residual flow, or other domain concepts: encode the relevant function, not decoration.

### 6. Draft the generation/edit prompt

Use the structured recipe in [prompt-template.md](references/prompt-template.md). Label every input image as an edit target or reference. State:

- intended academic use;
- primary change;
- layout and visual grammar;
- exact text and symbols;
- scientific constraints;
- invariants and avoid list;
- output intent.

For edits, repeat `change only X; keep Y unchanged`. Prefer one image-generation call per figure. Save outputs non-destructively with versioned names.

### 7. Inspect and iterate

Inspect every result at original detail. Check scientific correctness before aesthetics. Use [qa-checklist.md](references/qa-checklist.md).

Revise with one targeted change per iteration, for example:

- differentiate four statistical plots;
- restore one consistent cuboid style;
- separate a projection formula into `Wᵢ`, `×`, feature, `+`, and `bᵢ`;
- correct a subscript or dimension;
- remove connector collisions.

Do not rewrite the full prompt when a localized correction is sufficient.

### 8. Produce the reconstruction prompt

After accepting the visual reference, produce a standalone specification that another Codex instance can execute in Visio or another vector tool. Include:

- reference image path;
- page dimensions and layers;
- coordinate/proportion guidance;
- shape types and reusable masters;
- exact colors, fonts, line weights, and arrowheads;
- text, formulas, dimensions, and grouping rules;
- instruction to use editable native shapes rather than embedding the raster as the final result;
- acceptance criteria and output paths.

Keep GUI/application execution outside this skill unless a separate application-control skill is explicitly used.

## Required deliverables

Return the relevant subset of:

1. A concise diagnosis of the source figure.
2. An invariant list.
3. A publication-ready generation/edit prompt.
4. Versioned generated reference image paths, if generated.
5. A short inspection report noting any residual uncertainty.
6. A structured editable-reconstruction prompt.

## Quality bar

Reject or revise an output when it contains scientifically misleading icons, repeated plots for different concepts, altered model logic, unreadable equations, inconsistent branch geometry, clipped labels, crossed connectors, decorative clutter, or unverified text corruption.

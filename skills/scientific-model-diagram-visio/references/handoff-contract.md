# Model-to-Visio handoff contract

Use this contract before drawing or substantially revising a model figure.

## Evidence table

Record one row per disputed architectural fact:

| Fact | Executed model | Training code/config | Manuscript | Existing figure | Selected target |
|---|---|---|---|---|---|
| Input shape | | | | | |
| Moment/statistic axes | | | | | |
| Projection operation | | | | | |
| Projection width | | | | | |
| Fusion operation | | | | | |
| Fused width | | | | | |
| Classifier widths | | | | | |
| Number of classes | | | | | |

Do not silently combine facts from different columns. State whether the figure represents the executed implementation, the manuscript method, or a proposed corrected method.

## Model contract

Freeze the following fields:

```text
Figure target: [executed code / manuscript / proposed revision]
Input: [name and shape]
Stage 1: [operation] -> [output shape]
Stage 2: [operation] -> [output shape]
...
Fusion rule: [concat / sum / weighted sum / attention / other]
Classifier: [ordered widths and activations]
Output: [class count and exact class labels]
Vector convention: [row / column]
Exact symbols: [Greek letters, subscripts, superscripts, primes]
Exact caption: [verbatim]
Source evidence: [absolute file paths and line numbers]
```

## Dimensional audit

Check every arrow as an interface contract. For example, with row-vector convention:

```text
m_i [1 × 768] × W_i [768 × 128] + b_i [128] -> h_i [128]
h_i [128] × V_i [128 × 768] -> D_i [768]
sum_i beta_i D_i -> D [768]
```

For column-vector convention, transpose both the formula and matrix labels consistently. Never display `W_i × m_i` alongside a `768 × 128` label unless dimensions support that convention.

## Visual handoff

Include:

- reference image path and its role: style reference, edit target, or temporary trace;
- canvas size and stage proportions;
- row count, baselines, and connector lanes;
- object inventory per stage;
- color, font, line, shadow, and grouping tokens;
- output paths and acceptance criteria.

If a generated image corrupts text or dimensions, use it only for visual direction; the frozen model contract remains authoritative.

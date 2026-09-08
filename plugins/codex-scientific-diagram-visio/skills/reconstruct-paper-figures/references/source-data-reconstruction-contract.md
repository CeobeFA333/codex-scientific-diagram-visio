# Publisher Source Data Reconstruction Contract

Use this route when a paper supplies the observations, tables, code or machine-
readable values behind a chart. It is safer and more editable than tracing the
published JPEG, but only if the numerical and statistical method provenance stays
auditable.

## Evidence precedence

Prefer, in order:

1. publisher or repository source data tied to the article;
2. author code at an exact commit/tag plus a locked runtime or recorded version gap;
3. native vector objects extracted from the publication PDF;
4. explicitly labelled digitisation from the rendered figure;
5. visual tracing only for non-quantitative decoration.

Never mix values from different levels without recording which objects came from
which evidence. A downloaded workbook is an immutable input: store its original
filename, URL, byte count and SHA-256, and read it without rewriting formulas,
headers, hidden rows or number formats.

## Method parity record

Before drawing, record for every panel:

- source sheet/range, row count, inclusion predicates and missing-value policy;
- transforms such as `log10(x + epsilon)`, normalisation and clipping;
- thresholds and whether inequalities are strict or inclusive;
- bin count and bin/domain definition for histograms or density displays;
- box, whisker, quartile, zero-value and point-jitter definitions;
- statistical test, pairing, sidedness, exact/asymptotic mode and correction;
- software/package version or an explicit `runtime_version_not_locked` blocker.

Recompute published cohort counts, proportions and representative statistics before
layout work. If the source rows cannot reproduce a plotted group, keep that panel
blocked; do not synthesize observations or infer coordinates from a low-resolution
image while presenting them as source data.

## Editable-object contract

- Emit one semantic group per panel and stable IDs for axes, thresholds, legends,
  data marks and annotations.
- Keep every required label as live text at the physical job size. For this project,
  Illustrator must report Times New Roman 8.5 pt rather than merely finding an
  `8.5` string in SVG markup.
- Preserve source row identity on editable observations when practical, for example
  `data-cell-number` or an equivalent source-key attribute.
- Curves, bins, wedges, boxes, whiskers and points must remain paths/shapes. Do not
  flatten a data-derived chart into a raster preview.
- Record computed values separately from display labels when reproducing a probable
  publication typo. The manifest must state the discrepancy and keep publication
  readiness false until scientific approval.

## Missing-data and mixed-panel gate

Track panel state individually:

- `source_data_verified_vector`: regenerated from hash-bound values and method;
- `native_pdf_vector_recovered`: preserved from native PDF objects;
- `digitized_vector_with_uncertainty`: geometry measured from a render;
- `protected_raster_atom`: scientific pixels retained without tracing;
- `blocked_missing_source`: required values or clean pixels are unavailable.

A complete-looking composite does not clear a blocked panel. Protected microscopy,
photography, heatmaps and rendered surfaces remain minimal raster atoms unless their
underlying data exists. Generative cleanup cannot be used to manufacture scientific
evidence.

## Required evidence

The package is still a candidate until it contains:

1. source hashes and a machine-readable method/computation manifest;
2. tests for row counts, selections, transformations and representative statistics;
3. a zero-external-reference SVG editability audit;
4. Illustrator SVG-import, AI-reopen and editable-PDF-reopen audits with stable
   object counts, actual fonts/sizes and zero unexplained warnings;
5. a PDF structural audit and high-resolution render;
6. a hash-bound evidence manifest connecting all of the above;
7. human scientific and 200%-400% visual review.

SIMPLI Figure 4 under `examples/complex/prototype/simpli_figure4/` is the executable
example: b-h are source-data vectors, a/j remain microscopy-source decisions, and i
fails closed because one plotted group's observations are absent from the publisher
workbook.

# Scientific visual language

Use this reference when deciding the diagram's visual system.

## 1. Information hierarchy

Use no more than four levels:

1. figure or major-stage title;
2. module title;
3. symbol, equation, or dimension;
4. explanatory note.

Make stage titles dominant through size and weight, not excessive saturation. Keep explanatory text secondary.

## 2. Layout

- Use a strict grid and consistent outer margins.
- Align repeated rows to common baselines.
- Give parallel branches identical widths, heights, and gaps.
- Reserve whitespace around formulas and dense junctions.
- Keep captions outside the main diagram.
- Prefer horizontal/vertical connectors; use bends only to prevent collisions.

## 3. Visual grammar

### Flat overview figures

Use white or cool-gray backgrounds, thin strokes, restrained rounded containers, and simple vector icons. Separate major stages with one accent color each.

### Isometric architecture figures

Use shallow cuboids consistently:

- front face: branch color;
- top face: 15–22% lighter;
- side face: 12–18% darker;
- depth: about 12–16% of front-face width;
- one shared perspective and light direction;
- subtle or no shadow.

Use cuboids for data/tensors/modules, not for operators. Render `×`, `+`, concatenation, and arrows as independent 2D objects.

## 4. Color

Prefer a restrained, color-blind-conscious palette. Example:

| Role | Hex |
|---|---|
| Navy / encoder | `#294E7A` |
| Mean / teal | `#3A9D9A` |
| Variance / green | `#6BAF5E` |
| Skewness / amber | `#E9A62F` |
| Kurtosis / violet | `#8064A2` |
| Positive | `#3B8F62` |
| Neutral | `#E6A23C` |
| Negative | `#D95F59` |
| Body text | `#263238` |
| Divider | `#D7DEE8` |

Use the same branch color from extraction through projection and fusion. Do not use red/green alone to encode a distinction; pair color with labels or shapes.

## 5. Typography

- Use one sans-serif family for headings and prose.
- Use Cambria Math or another math face for symbols and equations.
- Preserve true subscripts, superscripts, Greek letters, and primes.
- Avoid tiny explanatory text; shorten wording before shrinking type.
- Keep all text horizontal unless a vertical axis label is essential.

## 6. Connectors

- Use consistent stroke weight and arrowhead size.
- Attach connectors to shape connection points.
- Avoid crossings and running lines behind text.
- Use color only when it encodes branch identity.
- Keep arrow directions unambiguous and consistent with reading order.

## 7. Definition-driven statistical plots

### Mean `μ`

Draw a symmetric curve with a vertical center line and center marker. The cue is location, not curve shape alone.

### Variance `σ²`

Draw a broad symmetric curve with a horizontal double-headed spread arrow. The cue is width/dispersion.

### Skewness `γ`

Draw a clearly asymmetric distribution with a displaced peak and long one-sided tail. The cue must remain obvious at thumbnail size.

### Kurtosis `κ`

Draw a symmetric tall narrow peak with visibly heavier two-sided tails. Add a faint normal/reference curve if needed. Do not make it resemble skewness.

## 8. Formula decomposition

For a projection such as `Wᵢ × mᵢ + bᵢ`, use:

`[3D Wᵢ block]  ×  [3D mᵢ block]  +  [3D bᵢ block]  →  [3D output block]`

Place dimensions beneath the relevant block. Keep operators outside blocks and align every item to the row baseline.

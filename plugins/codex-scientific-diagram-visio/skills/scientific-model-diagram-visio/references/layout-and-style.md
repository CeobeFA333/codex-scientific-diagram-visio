# Layout and style standards

## Grid and spacing

- Use a strict page grid with consistent outer margins and stage gutters.
- Keep repeated branches perfectly horizontal, equal in height, and evenly spaced.
- Align operands, operators, blocks, and dimension labels to shared row anchors.
- Reserve whitespace around equations, fusion junctions, legends, and captions.
- Widen dense stages instead of compressing all stages equally.
- Keep the caption outside the main architecture band.

## Stage containers

- Use thin rounded outlines on white or near-white fill.
- Keep stage titles centered and clear of the first row.
- Use stage title color only as a hierarchy cue; avoid saturated full-panel fills.
- Recommended title size on a 16 × 9 inch page: 17–19 pt, Arial/Aptos Bold.

## 3D cuboid master

- Front face: semantic/branch color.
- Top face: 15–22% lighter.
- Right face: 12–18% darker.
- Depth: 12–16% of front-face width.
- Perspective and light direction: identical across the page.
- Outline: 0.9–1.2 pt.
- Shadow: none or extremely light neutral gray; high transparency and small offset.
- Group front/top/right faces but keep them individually editable.

Use cuboids for data vectors, tensors, weights, biases, and modules. Do not put `×`, `+`, concatenation, or summation operators inside cuboids.

## Typography

Recommended minimums for a 16 × 9 inch publication figure:

| Role | Font | Size |
|---|---|---|
| Stage title | Arial/Aptos Bold | 17–19 pt |
| Module label | Arial/Aptos | 10–12 pt |
| Mathematical symbol | Cambria Math | 16–22 pt |
| Dimension | Arial/Aptos | 9–10 pt |
| Legend prose | Arial/Aptos | 9–11 pt |
| Caption | Cambria | 14–16 pt |

Never reduce required text below 9 pt. Prefer shorter wording, deliberate wrapping, or a wider container. Keep all text horizontal and use dark text such as `#15202B`.

## Connectors

- Main color: `#17212B` or branch color when lineage matters.
- Width: 1.5–1.8 pt for main signal flow.
- Arrowhead: consistent filled triangle.
- Glue both ends to connection points.
- Prefer zero-bend horizontal lines; otherwise use orthogonal bends.
- Keep lines out of text bounding boxes and away from cuboid faces.
- Use consistent entry/exit positions across four parallel rows.

## Example branch palette

| Branch | Front | Dark side |
|---|---|---|
| Mean / μ | `#8ACDD1` | `#4B9AA3` |
| Variance / σ² | `#A3CF7A` | `#6FA74D` |
| Skewness / γ | `#F5B44F` | `#D9861B` |
| Kurtosis / κ | `#BBA5D9` | `#8061AD` |
| Encoder/classifier | `#7EA5DC` | `#315C9D` |

Use labels and symbols in addition to color; color alone must not carry meaning.

## Definition-driven moment plots

- Mean: symmetric bell curve, center line, center marker.
- Variance: broad low symmetric curve and horizontal double-headed spread arrow.
- Skewness: displaced peak with a conspicuous one-sided long tail.
- Kurtosis: symmetric sharp peak and heavy tails, optionally with a faint dashed normal reference.

The four plots must remain distinguishable at thumbnail size.

## Collision policy

A figure fails when any of these occurs:

- text touches or crosses a container border;
- a connector intersects a label, operator, plot, or module;
- arrowheads overlap cuboid faces or other arrowheads;
- dimensions are visually associated with the wrong block;
- adjacent shadows merge into a false shape;
- a title or caption is clipped at export;
- repeated rows drift from common baselines.

Fix geometry first, then typography, then styling. Do not hide collisions with white rectangles.

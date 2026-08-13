# Image-generation design prompt

```text
Use case: scientific-educational
Asset type: publication-ready Transformer encoder architecture reference for later Microsoft Visio reconstruction

Primary request:
Create a clean wide 16:9 academic architecture figure for the original Transformer encoder stack. Use a white background, six left-to-right stage containers, straight horizontal main flow, orthogonal residual arrows above the modules, and shallow isometric cuboids. All text must be readable at ordinary preview size.

Scientific invariants:
- Token IDs [B × L]
- Token Embedding [B × L × 512]
- Positional Encoding [L × 512]
- element-wise addition as a separate plus operator
- Encoder Input X [B × L × 512]
- Multi-Head Self-Attention, 8 heads, d_model = 512
- Add & LayerNorm, output [B × L × 512]
- Feed-Forward Network: Linear 512→2048, ReLU, Linear 2048→512
- second Add & LayerNorm, output [B × L × 512]
- encoder layer repeated N = 6
- final Encoder Output [B × L × 512]
- two distinct residual/skip connections; no classifier or decoder

Visual system:
- navy/blue input and output blocks
- teal attention blocks
- amber feed-forward blocks
- violet Add & LayerNorm blocks
- dark charcoal connectors, 1.6 pt equivalent, filled triangle arrowheads
- consistent upper-right cuboid perspective with extremely subtle shadows
- Arial/Aptos-like headings and labels; Cambria Math-like symbols

Composition:
Stage 1 Input Tokens; Stage 2 Embedding + Position; Stage 3 Multi-Head Self-Attention; Stage 4 Add & Norm; Stage 5 Feed-Forward Network; Stage 6 Add & Norm / Encoder Output. Put an elegant dashed container around the complete encoder layer and mark ×6 clearly. Draw eight small attention-head blocks in a neat row or compact grid. Keep residual paths in reserved upper lanes.

Constraints:
No overlapping shapes or text. No connector crosses labels or blocks. Keep the main pipeline perfectly horizontal. Do not invent dimensions, decoder stages, cross-attention, classifier, probabilities, or output classes. No watermark. This is a design reference only; preserve technical accuracy over decoration.
```

# Synthetic model contract example

This example is intentionally generic and contains no private research content.

```text
Figure target: executed implementation
Input: token embeddings [B, L, 768]
Stage 1: reduce across L -> four statistics [B, 768] each
Stage 2: LayerNorm + row-vector projection 768 × 128 -> four features [B, 128]
Fusion rule: concatenate four projected features
Fused representation: [B, 512]
Classifier: 512 -> 128 -> 2
Output: Positive, Negative
Vector convention: row
Exact symbols: μ, σ², γ, κ
```

Dimensional audit:

```text
m_i [B,768] × W_i [768,128] + b_i [128] -> h_i [B,128]
concat(h_1,h_2,h_3,h_4) -> H [B,512]
H [B,512] × W_c [512,128] -> z [B,128]
z [B,128] × W_o [128,2] -> logits [B,2]
```

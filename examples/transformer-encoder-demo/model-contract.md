# Transformer encoder demo model contract

This public demo uses the encoder architecture from *Attention Is All You Need* and the parameter names of PyTorch's reference `TransformerEncoderLayer`.

## Evidence

- Vaswani et al., *Attention Is All You Need*: https://arxiv.org/abs/1706.03762
- PyTorch `TransformerEncoderLayer`: https://docs.pytorch.org/docs/stable/generated/torch.nn.TransformerEncoderLayer.html

## Frozen architecture

```text
Figure target: original Transformer encoder stack / PyTorch reference layer
Vector convention: batch-first row-vector notation for display
Token IDs: [B, L]
Token embeddings: [B, L, 512]
Positional encoding: [L, 512]
Combined encoder input: [B, L, 512]
Encoder layers: N = 6
Self-attention: Multi-Head Self-Attention, h = 8, d_model = 512
Attention output: [B, L, 512]
Residual 1: encoder input + attention output
Normalization 1: LayerNorm(512)
Feed-forward: Linear 512 -> 2048 -> ReLU -> Linear 2048 -> 512
Feed-forward output: [B, L, 512]
Residual 2: normalized attention state + feed-forward output
Normalization 2: LayerNorm(512)
Encoder output: [B, L, 512]
```

## Dimensional audit

```text
X [B,L,512] -> MHA(Q=X,K=X,V=X; 8 heads) -> A [B,L,512]
LayerNorm(X + A) -> H [B,L,512]
H [B,L,512] x W1 [512,2048] -> F1 [B,L,2048]
ReLU(F1) x W2 [2048,512] -> F2 [B,L,512]
LayerNorm(H + F2) -> Y [B,L,512]
Repeat encoder layer N = 6 -> Encoder output [B,L,512]
```

## Drawing invariants

- Use native editable Visio shapes; never use the generated reference as the final figure.
- Keep the main signal path horizontal.
- Draw both residual paths as separate orthogonal connectors above the main path.
- Do not route connectors through text or modules.
- Render the 8 attention heads as eight small parallel editable blocks.
- Keep `+`, `ReLU`, and `×6` as independent objects.
- Show all dimensions at preview-readable size.

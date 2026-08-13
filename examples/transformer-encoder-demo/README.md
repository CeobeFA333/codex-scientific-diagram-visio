# Transformer Encoder: paper/code to editable Visio

This reproducible example demonstrates the complete workflow on the original Transformer encoder: verify the architecture, generate a visual reference, reconstruct it with native Microsoft Visio objects, reopen the VSDX, and prove that a grouped block and a glued connector remain independently editable.

![Workflow demo](assets/workflow-demo.gif)

[Download the editable VSDX](assets/transformer-encoder-demo.vsdx) · [Open the PDF](assets/transformer-encoder-demo.pdf) · [View the final PNG](assets/transformer-encoder-demo.png)

[See the model and API-equivalent usage example](COST-EXAMPLE.md). A typical run using `gpt-5.6-terra`, one medium landscape `gpt-image-2` reference, and local Visio automation is approximately **$0.32** under the documented assumptions; local Visio drawing itself does not consume OpenAI tokens.

## Verified model contract

- Token IDs: `[B × L]`
- Token embedding: `[B × L × 512]`
- Positional encoding: `[L × 512]`
- Multi-head self-attention: 8 heads, `d_model = 512`
- Position-wise FFN: `512 → 2048 → 512`, ReLU
- Two residual + LayerNorm operations per encoder layer
- Encoder depth: `N = 6`
- Encoder output: `[B × L × 512]`

The contract follows [Attention Is All You Need](https://arxiv.org/abs/1706.03762) and is cross-checked against the official [PyTorch TransformerEncoderLayer documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.TransformerEncoderLayer.html).

## Reproduce on Windows

Requirements: Microsoft Visio and PowerShell 7.

```powershell
./scripts/build_transformer_visio_demo.ps1 -OutputDirectory ./build
```

The command visibly opens Visio, constructs the page from native shapes, saves and reopens the VSDX, captures staged screenshots, and exports VSDX/PDF/PNG.

To rebuild the GIF with Pillow:

```powershell
python ./scripts/make_workflow_gif.py `
  --build-dir ./build `
  --reference ./assets/transformer-reference.png `
  --output ./assets/workflow-demo.gif
```

The generated reference PNG is never inserted into the Visio document. Static package inspection reports one 16:9 page, 105 shapes, 16 groups, 24 connection records, and zero embedded media objects.

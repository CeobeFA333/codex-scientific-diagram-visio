# Model and usage example

This is an illustrative API-equivalent estimate for generating the Transformer Encoder Visio example. It is not a promise about ChatGPT or Codex subscription message limits, because subscription usage units are not exposed as a fixed token-to-credit conversion.

## Recommended model split

| Work | Model/tool | Example usage | Estimated API cost |
|---|---|---:|---:|
| Read the architecture, freeze dimensions, write and revise the Visio automation script, and perform QA | `gpt-5.6-terra` | 60K input + 13K output tokens | about **$0.276** |
| Generate one landscape style reference | `gpt-image-2`, medium, 1536 × 1024 | 1 image | about **$0.041**, plus small prompt-input cost |
| Construct, save, reopen, and export the VSDX | Local Microsoft Visio COM automation | about 105 shapes and 24 connection records | **$0 OpenAI API cost** |
| Total illustrative workflow | Terra + one medium reference + local Visio | one completed figure | about **$0.32** |

Calculation for the text/agent portion at standard short-context pricing:

```text
60,000 / 1,000,000 × $2.00  = $0.120 input
13,000 / 1,000,000 × $12.00 = $0.156 output
Agent subtotal                    $0.276
One GPT Image 2 medium landscape  $0.041
Illustrative total                $0.317 ≈ $0.32
```

## Model-choice comparison for the same token assumption

| Agent model | Intended use | 60K input + 13K output |
|---|---|---:|
| `gpt-5.6-sol` | Highest-quality reasoning for ambiguous papers or difficult reconstruction | about **$0.69** |
| `gpt-5.6-terra` | Recommended balance for this workflow | about **$0.276** |
| `gpt-5.6-luna` | Low-cost drafts when the model contract and layout spec are already clean | about **$0.0276** |

Add about `$0.041` for each additional medium 1536 × 1024 GPT Image 2 reference iteration. Web search, hosted containers, and other API tools are separate if used. Microsoft Visio licensing and local computer time are not OpenAI charges.

Prices were checked against the official OpenAI API documentation on 2026-08-13 and can change. Always verify the current [model pricing](https://developers.openai.com/api/docs/pricing) and [image-generation cost table](https://developers.openai.com/api/docs/guides/image-generation#calculating-costs).

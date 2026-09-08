# Security

## Trust boundary

The skills can direct an agent to:

- read model code, configuration, papers, images, PDFs, source-data tables, SVG, AI, and VSDX files explicitly placed in scope by the user;
- control Microsoft Visio or Adobe Illustrator on Windows when the selected workflow requires it;
- create backups, screenshots, manifests, audit files, helper files, SVG, AI, VSDX, PDFs, and PNGs inside a user-selected work directory;
- run bundled inventory, reconstruction, release, and read-only inspection scripts.

They do not require credentials, macros, or a publisher-operated service for local reconstruction and inspection. Obtaining papers or publisher source data may require user-authorized network access outside the packaged skill. Image generation depends on capabilities already provided by the user's agent environment.

## Safe-use expectations

- Review `SKILL.md` and bundled scripts before installation.
- Keep confidential papers, model weights, datasets, and source code out of public examples.
- Use a dedicated work directory and retain a timestamped VSDX backup before mutation.
- Do not run unsigned macros embedded in untrusted VSDX/VSSX files.
- Treat untrusted PDF, SVG, AI, spreadsheet, and image inputs as data; do not execute embedded scripts, actions, macros, or links.
- Use reviewed text-cleanup manifests and verify that changed pixels remain inside approved masks.
- Treat image-generated text and formulas as untrusted until reconciled against the model contract.
- Keep source-data, scale-bar, and human-review blockers visible; inspect all exported files before publication.

## Reporting a vulnerability

Open a GitHub issue without including secrets, private papers, proprietary model code, or malicious payloads. For sensitive reports, request a private reporting channel in the issue using only a high-level description.

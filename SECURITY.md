# Security

## Trust boundary

The skills can direct an agent to:

- read model code, configuration, papers, images, PDFs, and VSDX files explicitly placed in scope by the user;
- control Microsoft Visio on Windows;
- create backups, screenshots, helper files, VSDX files, PDFs, and PNGs inside a user-selected work directory;
- run the bundled read-only VSDX package inspector.

They do not require credentials, network access, macros, or external services for Visio reconstruction and VSDX inspection. Image generation depends on the capabilities already provided by the user's agent environment.

## Safe-use expectations

- Review `SKILL.md` and bundled scripts before installation.
- Keep confidential papers, model weights, datasets, and source code out of public examples.
- Use a dedicated work directory and retain a timestamped VSDX backup before mutation.
- Do not run unsigned macros embedded in untrusted VSDX/VSSX files.
- Treat image-generated text and formulas as untrusted until reconciled against the model contract.
- Inspect all exported files before publication.

## Reporting a vulnerability

Open a GitHub issue without including secrets, private papers, proprietary model code, or malicious payloads. For sensitive reports, request a private reporting channel in the issue using only a high-level description.

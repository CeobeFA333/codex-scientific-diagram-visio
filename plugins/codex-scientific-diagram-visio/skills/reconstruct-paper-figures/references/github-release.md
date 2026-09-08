# GitHub release boundary

Use this reference when preparing the skill or its containing workspace for a
public GitHub repository.

## Publishable unit

The default publishable unit is the source-only `reconstruct-paper-figures`
skill. Build it with `scripts/build_skill_release.py`; the archive contains the
skill entrypoint, UI metadata, deterministic scripts, references, version,
MIT license, and release profile. It excludes Python bytecode and every file
outside the skill directory.

Do not equate a successful code release with publication approval for any
scientific figure. Figure-level manifests and gates retain their own blockers.

## Excluded by default

Do not place user manuscripts, publisher PDFs, extracted figures, source-data
workbooks, Zenodo archives, generated AI/PDF evidence, or temporary workspaces
in a public repository merely because they exist beside the skill. Review the
license and redistribution terms of each example independently before adding a
small, necessary fixture.

## Public upload status

This repository and the standalone source-only skill archive are licensed
under MIT. The release audit may report `github_upload_ready=true` when no
other blockers are declared. Third-party scientific examples remain subject
to their own licenses and attribution requirements.

## Verification

Run the builder twice to different temporary filenames and compare SHA-256 when
deterministic-package verification is needed. Existing destinations are refused
unless `--force` is explicit. Inspect the sibling audit JSON before uploading.

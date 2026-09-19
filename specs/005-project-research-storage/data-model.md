# Local files

- research-layout.json: owner zbs-researcher, version 2.
- processed/dossier.json: existing schema 1, exact brief and source-relative artifacts; legacy dossier.json remains readable.
- artifacts.json: schema version, owner, files {path, role, bytes, sha256}. Exclude itself, hidden lock/temp files and symlinks. Roles raw, processed, final, metadata, legacy.
- research/index.json: schema version, owner, runs {path, goal, as_of, status, playbook, agent_context, artifacts, note}. Paths relative to research/. Invalid/missing finals have no result links.
- research/INDEX.md: generated owner marker, reading instructions, research links; escape source-derived Markdown text.

Prepare → draft. Valid export → partial/complete. Invalid/missing/mismatched pair → incomplete. Re-finalize repairs pair/inventory; index command rebuilds listing. No legacy migration.

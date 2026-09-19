# Design decisions

- Keep root metadata and final pair unchanged; only new working dossiers move to processed/. Preserve HTML sibling links and old runs.
- research-layout.json version 2 identifies structured runs; absence means flat legacy, never inferred migration.
- Owned research/INDEX.md and index.json use relative paths; ownership conflicts fail closed.
- raw/ means retained acquisition, possibly connector-normalized capture records, not guaranteed untouched HTTP bytes. Agent paraphrases and synthesis belong in processed/.
- Inventory size/SHA-256 establish file traceability, not truth; never modify source captures during export.
- Index distinguishes draft, complete, partial and incomplete; verify dossier and final digests before linking results.
- Atomic replacement and exclusive local lock files, no service/global catalog/dependency. No external research necessary.

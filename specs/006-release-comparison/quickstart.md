# Qualification

Run focused test_release_docs.py, full unittest suite, then scripts/selftest.sh from skills/deep-research. Verify offline relative links and excerpt hashes. Run npm pack --dry-run from installer with scripts disabled; do not publish. Review comparison against retained original sections and inspect privacy, date and winner limitations.

## Results

- 2026-09-05: focused tests failed before metadata/case creation; all four now pass.
- Full suite: 718 tests passed. Self-test: 10/10, version agreement 0.7.0 and 23 registered connectors. No paid calls; free connector smoke remains part of the existing self-test.
- npm pack --dry-run --ignore-scripts: version 0.7.0, exactly README.md, bin/cli.js and package.json, 4,725 bytes packed. No package published or archive emitted. Installer --dry-run executed no installation commands.
- Same-question q02 extracts retain the complete ZBS synthesis and Parallel narrative/references, with identical historical headers and explicit asymmetric extraction boundaries. Source and curated hashes recorded; private run IDs, absolute paths and raw quotation appendices are excluded from the public comparison.
- Relative documentation links and content hashes verified offline. git diff --check passes.
- Pre-implementation analysis: FR-001–006 mapped to T002–T007; 100% coverage, zero critical findings. Requirements checklist 5/5; no hooks configured.
- Final scoped adversarial review repaired stale README claims: 19 versus 23 connectors, automatic audio fallback, only-query data transfer, transcript exclusivity versus search, default legacy prepared-run/brief output, and missing heading separation. An inherited personal machine path in feature 005 qualification was generalized. The comparison explicitly retains both sides' shortcomings and unfinished owner judgments.
- No runtime source connector changed in this task; no new live research, publication, commit, push, merge or blind judgment performed. Existing local installed research behavior is unchanged; version metadata applies to the prepared repository distribution.
- Before publication, reconcile the existing divergent branch with main, include intended untracked runtime files and update published-state labels only after verification. Fresh 0.7.0 comparisons remain not run.

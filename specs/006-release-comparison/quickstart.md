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

## Authorized release qualification — 2026-09-19

- Owner explicitly authorized GitHub and npm publication. The release branch is based on origin/main (561f6ed), merging the preserved development candidate (4766463). Overlapping 0.6.0 changes were reconciled; its changelog remains intact. The integrated runtime matches the qualified candidate.
- Focused release documentation tests: 4/4. Full unittest suite: 718/718. The 10-step self-test passed, including metadata agreement, secret/portability checks, free connector smoke and Claude manifest validation. No paid research calls.
- npm package dry-run: exactly README.md, bin/cli.js, package.json; 4,705 bytes packed, 13,263 unpacked. Installer dry-run executed no installation commands.
- Final scoped adversarial review checked the integrated diff, source/reference inclusion, project-only storage and symlink/overwrite guards, output escaping and provenance limits, preserved 0.6.0 history, comparison hashes/date/no-winner caveats, and distribution labels. No release-blocking issue found. Staged files contain no private research directory, local settings, logs or detected credential patterns. Fixed four Markdown trailing-whitespace findings before qualification.
- GitHub authentication is available. npm reports ENEEDAUTH; browser login was offered without opening or controlling the owner's desktop. npm 0.7.0 is not yet published. Public README distinguishes the existing npm 0.5.0 shim from the GitHub plugin.
- A new matched benchmark remains deferred; this release does not establish superiority over manual research or another product.

## Distribution receipts — 2026-09-19

- PR #18 merged at 05:03:02 UTC; main commit a2c81efa77e76616512281b1b66ad9d9fc5e087d has the same qualified tree as release commit 0083ee3.
- Annotated remote tag v0.7.0 resolves to that main commit. Public GitHub release (not a draft) published at 05:03:29 UTC: https://github.com/zbs-gg/zbs-researcher/releases/tag/v0.7.0.
- GitHub contents API independently returned plugin version 0.7.0. npm registry still returned latest 0.5.0. npm publication is blocked on owner authentication, not on package qualification. No npm upload succeeded or is claimed.

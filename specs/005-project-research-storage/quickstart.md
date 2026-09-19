# Qualification

Prepare a temporary project with an offline fixture brief. Save captured source text in raw/, notes and dossier in processed/, then finalize. Read research/INDEX.md → agent-context.json → evidence artifact. Verify source hashes, partial status and relative links. Repeat in a second project to verify isolation.

Run focused tests, full unittest suite from skills/deep-research, then scripts/selftest.sh. Inspect installed-copy differences before refreshing only task-owned files. No live model/provider call is needed to prove file organization; this is not research-quality or published-release qualification.

## Results

- 2026-09-05: initial 10 storage tests failed before implementation (missing layout/index and absent placement checks), then passed.
- Final full unittest suite: 714 passed. Self-test: 10/10, including free connector checks; no paid provider/model call for this feature.
- Installed user-local `.agents/skills/deep-research` updated only for the six task-owned changed/new files after checking differences; recursive comparison reports parity, excluding Python caches.
- All 20 storage tests pass from the installed copy, including actual subprocess CLI prepare → finalize → index and a second independent project. This is deterministic installed execution, not another live model-led research evaluation.
- Skill quick validation passes using isolated uv/PyYAML (no project/global dependency added). git diff --check passes.
- Rebuilt the current repository's local index offline: one recognized direct goal-driven run, honestly partial. The nested Codex qualification fixture remains outside the direct-run listing; no old run was moved or modified.
- Pre-implementation consistency analysis: FR-001–008 covered by T002–T007; zero blocking contradictions/unmapped requirements. Requirements checklist 5/5.
- Final adversarial scoped review found two concrete issues and they were repaired: an index failure after committed output could hide the successful run and encourage duplicate allocation (now returns paths plus index_error); a legacy dossier could cite itself as source (now refused). Active/interrupted session writers are also withheld from reuse. Regression tests cover all three.
- Public/operator docs and skill routing updated. No release, version bump, commit, publication, auth/config change or legacy migration performed.

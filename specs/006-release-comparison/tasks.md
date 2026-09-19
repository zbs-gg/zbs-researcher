# Tasks: 0.7.0 and comparison

## Setup

- [x] T001 Inspect live metadata, release instructions and historical q02 inputs; document decisions in research.md.

## US1 — Candidate clarity

- [x] T002 [US1] Add offline release consistency tests in skills/deep-research/tests/test_release_docs.py before metadata changes.
- [x] T003 [US1] Bump .claude-plugin/plugin.json, marketplace.json, installer/package.json and scripts/selftest.sh to 0.7.0; update CHANGELOG.md, README.md, installer/README.md, installer/RELEASE.md and CLAUDE.md without publishing.

## US2 — Actual side-by-side comparison

- [x] T004 [US2] Add comparison integrity/link/privacy tests in skills/deep-research/tests/test_release_docs.py before creating the case.
- [x] T005 [US2] Prepare docs/comparison/{README.md,case.json,researcher.md,parallel.md} from inspected historical answer sections; link from README.md and docs/README.md, distinguish manual workflow from matched measurement.

## Qualification

- [x] T006 Run focused/full tests, 10-step self-test and installer package dry-run; record results in quickstart.md.
- [x] T007 Perform one final scoped diff/evidence review and mark preparation qualified, with publication and fresh benchmark deferred.

Dependencies: T001 → T002 → T003; T004 → T005; both stories → T006 → T007. No parallel agents. Both stories form the requested release-documentation slice; no new runtime.

## Authorized publication — 2026-09-19

- [ ] T008 Integrate the prepared release with origin/main; refresh distribution labels and rerun release qualification with a final scoped adversarial diff review.
- [ ] T009 Land via PR, tag/release 0.7.0 on GitHub and verify the public plugin metadata.
- [ ] T010 Publish npm shim 0.7.0 after authentication, inspect its exact package contents and verify the registry version. Record a blocker if owner login is unavailable.

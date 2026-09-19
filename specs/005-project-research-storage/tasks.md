# Tasks: Project-local research workspace

Input: spec.md, plan.md, research.md, data-model.md, contracts/cli.md.

## Setup

- [x] T001 Record scoped specification/design and inspect existing session, output paths, tests and ignore rules.

## US1 — Organized research (P1)

- [x] T002 [US1] Add failing layout, inventory, source preservation and legacy tests in skills/deep-research/tests/test_research_store.py.
- [x] T003 [US1] Implement safe layout/inventory in skills/deep-research/scripts/research_store.py and integrate prepare/finalize in research_session.py; reject research-root symlinks in output_paths.py.

## US2 — Project-agent reuse (P1)

- [x] T004 [US2] Add failing project isolation, ownership conflict, broken export and relative-link tests in skills/deep-research/tests/test_research_store.py.
- [x] T005 [US2] Implement owned local index and offline rebuild command in skills/deep-research/scripts/research_store.py and research_session.py.

## Integration and qualification

- [x] T006 [US1] [US2] Update skills/deep-research/SKILL.md and references/goal-driven.md plus README.md, CONFIGURATION.md, CLAUDE.md and CHANGELOG.md.
- [x] T007 [US1] [US2] Run focused/full unittest and 10-step self-test, check skill validity, verify installed-copy parity and record results in quickstart.md.
- [x] T008 [US1] [US2] Perform one final adversarial scoped diff review; resolve concrete defects, mark specification qualified but unreleased.

Dependencies: T001 → T002 → T003; T004 before T005; both stories before T006–T008. No parallel agents needed. MVP is both folder separation and usable project entry; no dashboard, database or migration.

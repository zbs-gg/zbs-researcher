# Tasks: Parallel Baseline and Claim Freshness

**Input**: Design documents from
`specs/001-parallel-baseline-freshness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/eval-cli.md`, `quickstart.md`

**Tests**: Required by the feature specification and project constitution. All
provider behavior must be validated with mocks; no paid or live calls.

**Organization**: Tasks are grouped by independently testable user story.

## Phase 1: Setup

**Purpose**: Establish current provider facts and the project governance used
by every story.

- [x] T001 Verify current official Parallel Task API processors, latency, and per-run pricing and record the decision in `specs/001-parallel-baseline-freshness/research.md`
- [x] T002 Establish Spec Kit governance and the selected feature pointer in `.specify/memory/constitution.md` and `.specify/feature.json`

---

## Phase 2: Foundational

**Purpose**: Preserve the existing evaluation and no-spend contracts before
changing any user story.

- [x] T003 Document the existing evaluation CLI, score, failure, and persistence boundary in `specs/001-parallel-baseline-freshness/contracts/eval-cli.md`
- [x] T004 Make test fixtures isolate host credentials, network, time, and sleep in `skills/deep-research/tests/test_eval_harness.py`

**Checkpoint**: Every provider path can be tested deterministically without a
real key or bill.

---

## Phase 3: User Story 1 - Trust the report's important claims (Priority: P1) 🎯 MVP

**Goal**: Broad questions are decomposed; every load-bearing claim is dated,
tiered, and demoted when stale or unsupported.

**Independent Test**: Run the self-test against `SKILL.md` and inspect a fixture
synthesis containing T1-T4 and old/current evidence.

### Tests for User Story 1

- [x] T005 [US1] Add ordered contract checks for decomposition, fact dating, proof tiers, the 12-month rule, and T4 rebuttal-only use in `skills/deep-research/scripts/selftest.sh`

### Implementation for User Story 1

- [x] T006 [US1] Add question decomposition and mandatory date-and-grade steps to `skills/deep-research/SKILL.md`
- [x] T007 [P] [US1] Explain the claim date, proof tier, stale section, and open-question output contract in `README.md`

**Checkpoint**: User Story 1 works without any baseline provider.

---

## Phase 4: User Story 2 - Compare with Parallel by explicit choice (Priority: P2)

**Goal**: The operator can intentionally run a paid Parallel baseline while the
default remains free and every failure stays honest.

**Independent Test**: Run the focused eval tests with a configured fake key;
the default makes no Parallel request and explicit selections cover success,
missing key, start failure, timeout, invalid output, and empty output.

### Tests for User Story 2

- [x] T008 [US2] Add no-implicit-call, missing-key, failure, timeout, empty-result, price-disclosure, and baseline-label tests in `skills/deep-research/tests/test_eval_harness.py`

### Implementation for User Story 2

- [x] T009 [US2] Implement Parallel key resolution, price disclosure, asynchronous start/poll, and unavailable states in `skills/deep-research/scripts/eval_harness.py`
- [x] T010 [US2] Add explicit baseline and processor CLI selection plus durable opponent labeling in `skills/deep-research/scripts/eval_harness.py`
- [x] T011 [P] [US2] Document endpoint, transmitted question, key handling, processor price, polling, and opt-in default in `CONFIGURATION.md`

**Checkpoint**: User Story 2 is independently useful on a stored researcher run
and cannot spend without `--baseline parallel`.

---

## Phase 5: User Story 3 - Read an honest comparison result (Priority: P3)

**Goal**: Equivalent evidence is scored equally and unavailable opponents are
never presented as zero-score losses.

**Independent Test**: Run fixtures with singular/plural excerpts, duplicates,
native social posts, corporate subdomains, unknown dates, and unavailable
baselines; inspect the score table and JSONL row.

### Tests for User Story 3

- [x] T012 [US3] Add structured citation, plural excerpt, duplicate URL, YouTube, corporate-subdomain, and opponent-label regressions in `skills/deep-research/tests/test_eval_harness.py`

### Implementation for User Story 3

- [x] T013 [US3] Normalize structured citation evidence and exclude corporate platform pages from native social scoring in `skills/deep-research/scripts/eval_harness.py`
- [x] T014 [US3] Preserve unknown freshness and explicit unavailable baseline states in tables and `eval-log.jsonl` in `skills/deep-research/scripts/eval_harness.py`
- [x] T015 [P] [US3] Update the public eval behavior and security boundary in `README.md` and the operational repo map in `CLAUDE.md`

**Checkpoint**: All three stories are independently testable and their combined
evaluation result is auditable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Keep repository guidance, history, and verification aligned with
the shipped behavior.

- [x] T016 [P] Add concise Codex scope, review, and completion guardrails in `AGENTS.md`
- [x] T017 [P] Record the unreleased user-visible behavior and non-goals in `CHANGELOG.md`
- [x] T018 Run focused eval tests, the full unittest discovery command, and `skills/deep-research/scripts/selftest.sh` using `specs/001-parallel-baseline-freshness/quickstart.md`
- [x] T019 Run Spec Kit cross-artifact analysis, `git diff --check`, and a final constitution/privacy/cost review across the complete branch diff

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup** starts immediately.
- **Foundational** depends on Setup and blocks provider implementation.
- **User Story 1** depends on Foundational and is the MVP.
- **User Story 2** depends on Foundational but not User Story 1.
- **User Story 3** depends on the evaluation path from User Story 2.
- **Polish** depends on all selected stories.

### User Story Dependencies

- **US1** has no baseline dependency and can ship as a playbook-only quality
  improvement.
- **US2** adds explicit baseline execution while preserving existing scores.
- **US3** hardens the comparison created by US2 and reuses its response parser.

### Parallel Opportunities

- T007 can proceed beside US2 because it changes only the public claim contract.
- T011 can proceed after the provider contract is stable while T010 finishes.
- T015, T016, and T017 touch separate documentation and can proceed after their
  source behavior is final.

## Implementation Strategy

1. Complete the playbook-only MVP (US1) and validate its marker contract.
2. Add the paid opponent behind explicit selection (US2), with tests before
   network behavior.
3. Correct evidence parsing and social classification (US3).
4. Align all public/project documentation, run the full verification gate once,
   then perform one final Spec Kit analysis and adversarial diff review.

## Notes

- Every task names the exact file it owns.
- A real Parallel run is optional operator acceptance, never automated
  validation.
- No task adds a monid connector, hidden runtime lookup, publication, version
  bump, or merge.

## Phase 7: Convergence

- [x] T020 Persist an auditable Parallel artifact bundle with the raw response, readable answer, normalized counted-evidence receipts, run identity and state, timing, processor and price basis, relative paths, atomic `0600` writes, regression tests, and operator documentation in `skills/deep-research/scripts/eval_harness.py`, `skills/deep-research/tests/test_eval_harness.py`, `specs/001-parallel-baseline-freshness/contracts/eval-cli.md`, `specs/001-parallel-baseline-freshness/quickstart.md`, `README.md`, `CONFIGURATION.md`, and `CHANGELOG.md` per FR-011 and FR-012 (partial)

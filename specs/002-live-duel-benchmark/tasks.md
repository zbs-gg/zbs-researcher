# Tasks: Live Duel Benchmark

**Input**: Design documents from `specs/002-live-duel-benchmark/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/duel-cli.md`, `quickstart.md`

**Tests**: Required. Provider behavior is mocked and all runtime data uses
temporary directories; no live or paid calls are permitted.

**Organization**: Tasks are grouped by independently testable user story.

## Phase 1: Setup

**Purpose**: Freeze the official experiment and protect its runtime boundary.

- [x] T001 Commit the exact five-question suite, rubric, attempt rules, thresholds, budgets, and authoritative price sources in `benchmarks/duel-v1.json`
- [x] T002 Add ignored private runtime coverage for `research/` and preserve tracked benchmark definitions in `.gitignore`

---

## Phase 2: Foundational

**Purpose**: Create deterministic validation and private storage shared by all commands.

- [x] T003 Add frozen-suite, private atomic I/O, relative-path, digest, time-window, and secret/path-redaction tests in `skills/deep-research/tests/test_duel_benchmark.py`
- [x] T004 Implement suite loading/validation, bundle loading, atomic mode-0600 writes, mode-0700 directories, relative-path guards, digests, and command dispatch in `skills/deep-research/scripts/duel_benchmark.py`

**Checkpoint**: Invalid suites and unsafe bundle state fail before any provider work.

---

## Phase 3: User Story 1 - Freeze a fair benchmark before seeing results (Priority: P1) 🎯 MVP

**Goal**: Initialize a complete offline preflight from the immutable suite.

**Independent Test**: Initialize a temporary bundle and verify exact questions,
rubric, revision, versions, budgets, availability booleans, deadline, and zero
provider calls.

### Tests for User Story 1

- [x] T005 [US1] Add init, exact-question, provider-boolean, git/version, deadline, default-path, and zero-network tests in `skills/deep-research/tests/test_duel_benchmark.py`

### Implementation for User Story 1

- [x] T006 [US1] Implement the offline `init` command and preflight records in `skills/deep-research/scripts/duel_benchmark.py`
- [x] T007 [US1] Add paid-consent preflight tests proving `run-parallel` without `--confirm-paid` cannot invoke an executor in `skills/deep-research/tests/test_duel_benchmark.py`

**Checkpoint**: A non-paid official bundle can be initialized and inspected.

---

## Phase 4: User Story 2 - Preserve one reproducible duel per question (Priority: P2)

**Goal**: Freeze a valid Researcher run before one auditable Parallel attempt.

**Independent Test**: Snapshot a synthetic completed run, execute a mocked
Parallel result, inspect complete attempt receipts, then prove only a recorded
technical failure permits a preserved retry.

### Tests for User Story 2

- [x] T008 [US2] Add complete/incomplete/mismatched Researcher snapshot and objective-score tests in `skills/deep-research/tests/test_duel_benchmark.py`
- [x] T009 [US2] Add mocked Parallel success, consent, ordering, budget, 24-hour, technical-retry, poor-answer-no-retry, and attempt-preservation tests in `skills/deep-research/tests/test_duel_benchmark.py`

### Implementation for User Story 2

- [x] T010 [US2] Implement `snapshot-researcher` validation, private copying, immutable receipt, and objective scoring in `skills/deep-research/scripts/duel_benchmark.py`
- [x] T011 [US2] Implement `run-parallel` preflight, explicit spend gate, feature-001 executor integration, numbered attempts, budget/window enforcement, and technical retry rules in `skills/deep-research/scripts/duel_benchmark.py`

**Checkpoint**: Each question can hold one complete, independently auditable pair.

---

## Phase 5: User Story 3 - Judge answers blind and declare an honest winner (Priority: P3)

**Goal**: Produce provider-neutral review material and derive only a complete valid result.

**Independent Test**: Blind and judge five fixture pairs, then verify margin,
veto, three-win, 2-2-1 tie, cost/time separation, and partial-report refusal.

### Tests for User Story 3

- [x] T012 [US3] Add deterministic/reversible A/B mapping, label-neutralization, private mapping, and no-regeneration tests in `skills/deep-research/tests/test_duel_benchmark.py`
- [x] T013 [US3] Add audit/judgment schema, range, critical-note, missing-pair, margin, veto, overall-winner, 2-2-1 tie, and cost/time-separation tests in `skills/deep-research/tests/test_duel_benchmark.py`
- [x] T014 [US3] Add a mocked five-question end-to-end bundle test with no network or paid call in `skills/deep-research/tests/test_duel_benchmark.py`

### Implementation for User Story 3

- [x] T015 [US3] Implement `blind`, participant-label neutralization, injectable RNG, private mapping, and blank AI-audit/owner-judgment forms in `skills/deep-research/scripts/duel_benchmark.py`
- [x] T016 [US3] Implement audit/judgment validation plus fail-closed per-question and overall `report` generation in `skills/deep-research/scripts/duel_benchmark.py`

**Checkpoint**: A winner can be declared only from five complete blind judgments.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Align user guidance, history, full verification, and internal handoff.

- [x] T017 [P] Document the private benchmark workflow, separate paid gate, runtime layout, retry rule, and non-public status in `README.md` and `CONFIGURATION.md`
- [x] T018 [P] Record the unreleased benchmark controller and its non-goals in `CHANGELOG.md` and the script/runtime ownership in `CLAUDE.md`
- [x] T019 Add an ordered self-test contract for the frozen suite and no-paid benchmark preflight in `skills/deep-research/scripts/selftest.sh`
- [x] T020 Run focused tests, full unittest discovery, `skills/deep-research/scripts/selftest.sh`, privacy/relative-path scan, and `git diff --check` using `specs/002-live-duel-benchmark/quickstart.md`
- [x] T021 Run Spec Kit cross-artifact analysis, implement any approved corrections, then run `$speckit-converge` against the complete feature
- [x] T022 Initialize one ignored non-paid preflight bundle under `research/`, inspect it, and stop before Researcher collection or any `--confirm-paid` call

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup** starts immediately.
- **Foundational** depends on Setup and blocks every user story.
- **US1** depends on Foundational and creates the bundle required by US2.
- **US2** depends on US1 and creates pairs required by US3.
- **US3** depends on US2.
- **Polish** depends on all three stories.

### Parallel Opportunities

- T017 and T018 touch separate documentation after behavior stabilizes.
- Tests are written before their matching implementation, but fixture-only test
  preparation may proceed beside documentation.
- Official live execution is not a parallel implementation task and remains
  outside this task list until separate owner authorization.

## Implementation Strategy

1. Freeze and validate the experiment definition.
2. Deliver the offline `init` MVP and prove it cannot spend.
3. Add immutable Researcher snapshots and one-attempt Parallel execution.
4. Add blind review and fail-closed reporting.
5. Validate the whole mocked package, initialize only the real non-paid
   preflight, and hand the paid phase back to the owner.

## Notes

- Every task names its owned files and follows the strict Spec Kit checklist format.
- Runtime answers and Telegram materials never enter version control.
- No task authorizes merge, publication, official live runs, or monid integration.

## Phase 7: Convergence

- [x] T023 CRITICAL add a portable total wall-clock deadline for paid `--fire` calls and atomically retain an automatic error/cost-unknown receipt after timeout in `skills/deep-research/scripts/deep-research.py`, `skills/deep-research/scripts/fire_audit.py`, and `skills/deep-research/tests/test_fire.py` per Constitution IV (partial)
- [x] T024 Reconcile every paid Researcher `manifest.calls[]` entry with an actual, estimated, or explicitly unavailable cost receipt before snapshot acceptance, and test that unaccounted spend cannot bypass the USD 10 cap in `skills/deep-research/scripts/duel_benchmark.py` and `skills/deep-research/tests/test_duel_benchmark.py` per FR-011 and FR-012 (partial)
- [x] T025 Replace audit completion booleans with a validated claim-level ledger that records each load-bearing claim, citation-fit verdict, fact date/freshness, support status, and evidence note while preserving recommendation/omission/contradiction and critical-error review in `skills/deep-research/scripts/duel_benchmark.py` and `skills/deep-research/tests/test_duel_benchmark.py` per FR-015 (partial)
- [x] T026 Ensure every benchmark runtime directory, including the implicit `questions/` parent, is mode `0700` on POSIX and extend the end-to-end privacy scan in `skills/deep-research/scripts/duel_benchmark.py` and `skills/deep-research/tests/test_duel_benchmark.py` per plan: private storage (partial)

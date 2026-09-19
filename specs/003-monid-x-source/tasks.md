# Tasks: Monid X Source

**Input**: Design documents from `specs/003-monid-x-source/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required by FR-014 and the project constitution. All provider calls
use deterministic mocks; no live or paid call is allowed.

**Organization**: Tasks are grouped by user story so each outcome can be tested
independently.

## Phase 1: Setup

**Purpose**: Pin the provider contract and create the offline test surface.

- [x] T001 Confirm the shipped Monid route adapters and response fixtures against `specs/003-monid-x-source/research.md` and `specs/003-monid-x-source/contracts/x-source-cli.md`
- [x] T002 Create the offline Monid discover, inspect, synchronous run, asynchronous run, nested timeline, provider error, and timeout tests in `skills/deep-research/tests/test_monid_x.py`

---

## Phase 2: Foundational

**Purpose**: Establish credential detection and transport primitives required by
the direct X story.

- [x] T003 Add failing Monid configured/absent and secret-redaction cases to `skills/deep-research/tests/test_detect_state.py`
- [x] T004 Implement Monid key resolution in `skills/deep-research/scripts/deep-research.py` and provider-state reporting in `skills/deep-research/scripts/detect_state.py`
- [x] T005 Implement the stdlib discover, inspect, compatible-route selection, paid-boundary announcement, run, bounded polling, billing normalization, and post normalization client in `skills/deep-research/scripts/monid_x.py`

**Checkpoint**: Monid transport and state are testable without registering a
public connector.

---

## Phase 3: User Story 1 - Pull real X posts without xAI API credit (Priority: P1) 🎯 MVP

**Goal**: One explicit `--fire x` returns auditable public X posts through
Monid while preserving route, freshness, and honest cost evidence.

**Independent Test**: Fire `x` with mocked Monid success and failure fixtures;
verify Markdown, envelope, provenance, call receipt, and zero unselected calls.

### Tests for User Story 1

- [x] T006 [US1] Add failing `x` connector rendering, nested response, missing-field, freshness, and explicit-selection tests to `skills/deep-research/tests/test_monid_x.py`
- [x] T007 [US1] Add failing Monid provider and quoted-versus-actual cost receipt tests to `skills/deep-research/tests/test_fire.py`
- [x] T008 [US1] Add failing direct-X reachability and fresh-post coverage tests to `skills/deep-research/tests/test_provenance.py`

### Implementation for User Story 1

- [x] T009 [US1] Register and render the default-off `x` connector, usage metadata, output name, and call provider in `skills/deep-research/scripts/deep-research.py`
- [x] T010 [US1] Add direct-X reachability, display name, and freshness classification in `skills/deep-research/scripts/provenance.py`
- [x] T011 [US1] Run each focused module with `python3 -m unittest discover -s tests -p 'test_<name>.py'` from `skills/deep-research` and make the P1 contract pass without network use

**Checkpoint**: Explicit Monid X retrieval is independently complete.

---

## Phase 4: User Story 2 - Keep paid alternatives explicit (Priority: P2)

**Goal**: A failed direct xAI call never triggers another payee and explains the
separate Monid and subscription-OAuth choices accurately.

**Independent Test**: Simulate xAI HTTP 403 with Monid and OpenRouter configured;
assert neither receives a request and the error artifact names the explicit X
route without claiming the SuperGrok plan funds the API key.

### Tests for User Story 2

- [x] T012 [US2] Add the xAI spending-limit no-fallback and actionable-error regression test to `skills/deep-research/tests/test_openrouter_routing.py`

### Implementation for User Story 2

- [x] T013 [US2] Preserve xAI HTTP failure evidence and add no-fallback Monid guidance in `skills/deep-research/scripts/deep-research.py`
- [x] T014 [US2] Document standard API-key, OpenRouter, SuperGrok OAuth, and Monid route boundaries in `CONFIGURATION.md` and `skills/deep-research/SKILL.md`

**Checkpoint**: Paid routing remains explicit and subscription wording is
evidence-bounded.

---

## Phase 5: User Story 3 - Remove low-value Bluesky work from defaults (Priority: P3)

**Goal**: Default single and entity-fan-out research stop calling Bluesky while
explicit Bluesky selection remains intact.

**Independent Test**: Inspect default connector selection and default fan-out
cells, then explicitly select Bluesky with a mocked response.

### Tests for User Story 3

- [x] T015 [US3] Add failing default-off and explicit-Bluesky connector selection cases to `skills/deep-research/tests/test_fire.py`
- [x] T016 [US3] Add the revised default free-channel assertion while preserving explicit Bluesky cell tests in `skills/deep-research/tests/test_entity_fanout.py`

### Implementation for User Story 3

- [x] T017 [US3] Mark Bluesky default-off in `skills/deep-research/scripts/deep-research.py` and remove it from `FREE_ENTITY_CHANNELS` in `skills/deep-research/scripts/entity_fanout.py`

**Checkpoint**: Defaults spend no work on Bluesky; explicit access survives.

---

## Phase 6: Documentation and Verification

**Purpose**: Keep the product contract honest and qualify the complete patch.

- [x] T018 Update connector tables, key setup, examples, default behavior, output tree, and network/privacy disclosures in `README.md`, `CONFIGURATION.md`, `skills/deep-research/SKILL.md`, and `CHANGELOG.md`
- [x] T019 Run `python3 -m unittest discover -s tests` from `skills/deep-research` and resolve every regression without live or paid calls
- [x] T020 Run `bash scripts/selftest.sh` from `skills/deep-research` and require all ten checks to pass
- [x] T021 Review the complete diff against `.specify/memory/constitution.md`, `specs/003-monid-x-source/spec.md`, and `specs/003-monid-x-source/contracts/x-source-cli.md` for hidden spend, route drift, cost overclaim, secret leakage, and benchmark impact
- [x] T022 Mark completed tasks in `specs/003-monid-x-source/tasks.md` and record any unresolved live-only verification explicitly in the final handoff

## Verification evidence

- Focused Monid, fire, state, provenance, fan-out, and no-fallback tests passed.
- Full unit suite: 653 tests passed without live or paid calls.
- `scripts/selftest.sh`: all ten checks passed without paid API calls.
- One separately owner-approved live Monid smoke selected TikHub at a quoted
  USD 0.0015 per call and returned public X posts. Monid returned no actual
  billing block, so the only live cost evidence remains the quoted unit price.
- No live SuperGrok OAuth integration was added: current official support is
  documented for compatible agent clients, while Researcher's direct xAI path
  still uses the separately billed standard API key.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: starts immediately.
- **Foundational**: follows fixture design and blocks US1.
- **US1**: depends on the Monid client and state contract.
- **US2**: can start after key resolution exists; it does not depend on a
  successful Monid run.
- **US3**: independent of US1/US2 after the baseline tests are loaded.
- **Documentation and Verification**: follows all selected stories.

### User Story Dependencies

- **US1 (P1)**: foundational Monid client and state only.
- **US2 (P2)**: independent failure-routing increment; integrates only through
  the existing Grok channel.
- **US3 (P3)**: independent default-selection increment.

### Within Each User Story

- Write and observe failing tests before implementation.
- Transport and normalization before connector registration.
- Connector behavior before documentation claims.
- Focused tests before the complete suite and selftest.

## Parallel Opportunities

- US2's Grok failure test and US3's default-selection tests touch different
  behavior and can be designed while US1 transport is implemented.
- Documentation can be audited in parallel with the final focused tests once
  public names and behavior are stable.
- Final full-suite, selftest, and diff review remain sequential gates.

## Implementation Strategy

### MVP First

1. Complete setup and foundational tasks.
2. Complete US1 through T011.
3. Stop and verify one mocked direct-X fire end to end.
4. Add the no-fallback and Bluesky-default corrections.
5. Update documentation and run all qualification gates.

### Incremental Delivery

1. Monid client proves compatible route selection and honest billing evidence.
2. `x` connector restores current direct-social evidence.
3. Grok failure guidance prevents hidden provider switching.
4. Bluesky default-off removes repeated low-value work.
5. Full verification qualifies the combined patch without publishing it.

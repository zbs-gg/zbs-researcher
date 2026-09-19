# Feature Specification: Live Duel Benchmark

**Feature Branch**: `codex/live-duel-benchmark`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Run the first official, reproducible five-question Researcher vs Parallel benchmark with frozen inputs, private evidence bundles, blind judging, and no paid execution until a separate explicit approval."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Freeze a fair benchmark before seeing results (Priority: P1)

As the product owner, I want one immutable benchmark definition and a recorded
preflight, so neither participant can receive a friendlier question and no case
can be selected after its result is known.

**Why this priority**: A comparison cannot establish anything if questions,
rules, budgets, or provider availability can drift after answers arrive.

**Independent Test**: Initialize a bundle from the committed suite and verify
that all five exact questions, rubric, rules, budgets, repository revision,
tool versions, provider availability, and start time are captured without a
network or paid call.

**Acceptance Scenarios**:

1. **Given** the committed suite, **When** a benchmark is initialized, **Then**
   the runtime bundle contains the same five questions in the same order and a
   complete preflight snapshot.
2. **Given** missing provider credentials, **When** initialization runs,
   **Then** availability is recorded as false without exposing secrets or
   blocking inspection of the frozen suite.
3. **Given** an initialized bundle, **When** a paid Parallel run is requested
   without separate confirmation, **Then** no request is made and the intended
   processor and maximum spend are shown.

---

### User Story 2 - Preserve one reproducible duel per question (Priority: P2)

As a benchmark operator, I want each completed Researcher run and subsequent
Parallel response stored together with their evidence and timing, so a reviewer
can reproduce the score and distinguish a technical retry from answer shopping.

**Why this priority**: The historical duel could not be independently checked
because its raw package remained in a temporary directory.

**Independent Test**: With a fixture Researcher run and a mocked Parallel
response, produce one complete duel pair and verify the original inputs,
answers, raw results, manifests, citations, score receipts, run metadata, costs,
and attempt history without a real provider call.

**Acceptance Scenarios**:

1. **Given** a completed Researcher run containing a plan, manifest, raw
   results, and synthesis, **When** it is snapshotted, **Then** the bundle keeps
   an independently checkable copy and rejects incomplete or mismatched runs.
2. **Given** a frozen Researcher snapshot and separate paid confirmation,
   **When** Parallel completes, **Then** the exact same question is used and the
   full response, citations, score receipts, identity, timing, state, processor,
   and price basis are retained.
3. **Given** a successful answer, **When** a rerun is requested, **Then** it is
   refused; a retry is allowed only after a recorded technical failure and both
   attempts remain visible.
4. **Given** any runtime file, **When** it is inspected, **Then** it has private
   permissions and contains neither credentials nor personal absolute paths.

---

### User Story 3 - Judge answers blind and declare an honest winner (Priority: P3)

As a reviewer, I want provider-neutral A/B answers and a fixed scoring rule, so
writing style or brand familiarity cannot substitute for correctness and useful
evidence.

**Why this priority**: Objective source counts alone cannot establish whether
citations support the conclusions or whether an answer would improve a real
decision.

**Independent Test**: Blind five complete fixture pairs with deterministic
randomness, submit complete judgments, and generate a report that applies the
per-question margin, critical-error veto, and overall three-win rule while
keeping cost and duration outside the quality score.

**Acceptance Scenarios**:

1. **Given** a complete pair, **When** it is blinded, **Then** answers A and B
   reveal no provider identity and the private mapping can reverse the labels.
2. **Given** reviewer scores from 0 to 4 on all five dimensions, **When** the
   difference is at least three points, **Then** the higher answer wins unless
   it has a confirmed decision-changing critical error; a smaller difference
   is a tie.
3. **Given** all five judged questions, **When** one participant wins at least
   three, **Then** it is the overall winner; a 2-2 result with one tie is an
   overall tie.
4. **Given** any missing pair, mapping, audit, or judgment, **When** reporting
   is requested, **Then** no final winner is produced and the missing input is
   named.

### Edge Cases

- A Researcher run uses a different question or lacks its pre-answer source plan.
- A provider is available during preflight but fails after a paid task starts.
- Parallel returns content without citations, duplicate citations, or citations
  that do not support a load-bearing statement.
- A technical retry finishes after the 24-hour benchmark window.
- Blinded prose itself names the provider or contains a provider-specific
  heading that would reveal the mapping.
- A judge supplies an out-of-range score, omits a dimension, or marks a critical
  error without the required evidence note.
- Two answers tie on quality while their cost and completion time differ widely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The benchmark suite MUST contain exactly five English questions
  in a fixed order and MUST reject runtime modifications to them.
- **FR-002**: The five questions MUST be the exact texts listed in the Frozen
  Question Set below.
- **FR-003**: Initialization MUST freeze the suite version, rubric, repository
  revision, relevant tool versions, budgets, provider availability, processor,
  start time, and 24-hour completion deadline without making paid calls.
- **FR-004**: Runtime benchmark packages MUST remain outside version control;
  only the suite, rubric, implementation, tests, and synthetic fixtures MAY be
  committed.
- **FR-005**: Each question MUST have one Researcher attempt and one Parallel
  attempt; another attempt is permitted only for a recorded technical failure,
  MUST preserve the earlier trace, and MUST NOT treat a poor answer as failure.
- **FR-006**: Researcher MUST finish and freeze its source plan, raw results,
  manifest, and synthesis before the corresponding Parallel answer is requested.
- **FR-007**: Researcher MUST use its investigate workflow, source-specific
  decomposition, no more than four drill rounds, and only its runner and
  configured lens providers during collection.
- **FR-008**: Parallel MUST receive the exact frozen question and use the Ultra
  processor for each of the five official attempts.
- **FR-009**: Every paid request MUST require a separate explicit confirmation
  after preflight; suite approval or initialization MUST NOT authorize spend.
- **FR-010**: The benchmark MUST disclose the current published processor price
  before a paid call and retain the actual available charge, currency, amount,
  basis, and authoritative source after each attempt.
- **FR-011**: Parallel spend MUST be capped at five Ultra calls at the frozen
  listed price, and Researcher vendor spend MUST be capped at USD 10 for the
  official benchmark.
- **FR-012**: Each pair MUST retain both complete answers, raw provider/run
  materials, normalized citations, score receipts, identity, state, timing,
  attempts, and costs sufficient for independent audit.
- **FR-013**: Each complete pair MUST expose objective primary-source depth,
  freshness, and native social coverage separately from human quality scores.
- **FR-014**: Blinding MUST produce provider-neutral A/B answers and a private
  mapping; deterministic randomness MUST be injectable for repeatable tests.
- **FR-015**: The AI audit MUST check every load-bearing claim, citation fit,
  current versus stale facts, unsupported recommendations, omissions, and
  contradictions before owner scoring is accepted.
- **FR-016**: The owner MUST score A and B from 0 through 4 for practical
  usefulness, factual correctness, evidence-to-claim fit, freshness, and honest
  handling of uncertainty and contradictions.
- **FR-017**: A difference of at least three total quality points MUST decide a
  question; a smaller difference MUST yield a tie.
- **FR-018**: A confirmed critical error capable of changing the decision MUST
  prevent that answer from winning the question, regardless of total score.
- **FR-019**: An overall winner MUST win at least three of five questions; a
  2-2 result with one tie MUST produce an overall tie.
- **FR-020**: Cost and elapsed time MUST be reported separately and MUST NOT be
  added to the quality score.
- **FR-021**: Reporting MUST refuse to declare a result while any pair, blind
  mapping, required audit, or score is incomplete or invalid.
- **FR-022**: Runtime files MUST be written atomically with private permissions
  and MUST contain only relative internal paths, no credentials, and no personal
  absolute paths.
- **FR-023**: Automated tests MUST complete end to end with mocked providers and
  MUST make no live, external-search, or paid calls.
- **FR-024**: The first official result is internal; nothing is published,
  merged, or uploaded automatically.
- **FR-025**: monid MUST NOT become a dependency, connector, or hidden source.

### Frozen Question Set

1. “As an independent AI builder aiming to build an English-language reputation in 2026, should I invest seriously in X, and which current practices produce qualified relationships rather than vanity reach? What changed since 2023?”
2. “For a production coding or AI agent in 2026, when should a team choose Mem0, Letta, or a custom memory layer? What failure modes are practitioners actually seeing, and which remain unresolved?”
3. “What kinds of AI decision and architecture clarity are companies demonstrably paying for in 2026, how do buyers describe the pain in their own words, and which needs remain poorly served?”
4. “Using current primary documentation only, compare the pricing, latency, data handling, privacy, and operational limits of Parallel Task API, Perplexity Sonar/API, and OpenAI web-search/research APIs for an agent product.”
5. “What do primary 2025–2026 studies actually establish about long-term memory in LLM agents? Where do benchmarks disagree, and which important claims remain unproven?”

### Key Entities

- **Benchmark Suite**: The immutable questions, rubric, budgets, rules, and
  scoring thresholds defining the experiment.
- **Benchmark Bundle**: One private runtime package containing preflight state,
  five question records, attempts, blind materials, audits, judgments, and report.
- **Question Record**: One frozen question plus its Researcher snapshot,
  Parallel attempt history, objective metrics, A/B mapping, audit, and judgment.
- **Attempt**: One participant execution with state, timestamps, cost, raw
  materials, and a technical-failure classification.
- **Judgment**: Complete A/B dimension scores, critical-error findings, notes,
  and the derived per-question result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Initialization reproduces all five frozen questions byte-for-byte
  and records every preflight field in 100% of fixture runs without network use.
- **SC-002**: A complete mocked five-question benchmark produces an auditable
  package and final report from start to finish with zero paid calls.
- **SC-003**: In all covered cases, a paid call is impossible without the
  dedicated confirmation and impossible before its Researcher snapshot exists.
- **SC-004**: 100% of successful Parallel fixtures retain raw response, readable
  answer, citations, counted evidence, run ID, timing, state, processor, and
  price basis; failed attempts retain their complete failure trace.
- **SC-005**: Deterministic blinding produces the same A/B mapping for the same
  injected randomness and can produce either participant as A across fixtures.
- **SC-006**: 100% of incomplete pairs, audits, mappings, and judgments prevent
  a final report and identify the missing requirement.
- **SC-007**: Per-question and overall results match the fixed margin, veto, and
  three-win rules across win, tie, 2-2-1, and critical-error fixture cases.
- **SC-008**: All runtime artifact files are private and a scan finds zero
  credential values or personal absolute paths.
- **SC-009**: The complete unit suite and ten-step self-test pass without a
  provider, external-search, or paid call.

## Assumptions

- The audit-persistence work from feature 001 is the base of this feature and
  its branch remains unmerged while this draft is stacked on it.
- Researcher execution remains session-driven; the benchmark tool validates and
  snapshots a completed run rather than replacing the investigate playbook.
- Provider availability means only that a credential/configuration route is
  present during preflight, not that a future paid task is guaranteed to finish.
- Primary links may be opened after answers are frozen for audit, but no new
  evidence may be inserted into either answer.
- The five official live duels and owner judgments are acceptance work after a
  separate paid-run authorization, not part of code implementation.

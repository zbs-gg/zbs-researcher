# Feature Specification: Parallel Baseline and Claim Freshness

**Feature Branch**: `codex/spec-kit-parallel-baseline`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Turn the original researcher plan into a living
spec: compare against Parallel only when explicitly requested, grade evidence
honestly, and stop stale claims from carrying the report."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trust the report's important claims (Priority: P1)

As a researcher, I want every conclusion that could change my decision to show
how direct and how current its evidence is, so I can separate a current fact
from an old claim, a weak mention, or an inference.

**Why this priority**: Better retrieval has no value if the final report
overstates what its evidence proves. This is the minimum trustworthy product.

**Independent Test**: Give the workflow a mix of current primary evidence, old
primary evidence, secondary summaries, and search snippets. The resulting
synthesis can be checked without any paid comparison provider.

**Acceptance Scenarios**:

1. **Given** a decision-relevant claim with current first-party evidence,
   **When** the report is synthesized, **Then** the claim identifies the fact
   date and the strongest applicable proof tier.
2. **Given** a claim whose only supporting evidence is more than 12 months old,
   **When** no current source confirms it, **Then** the claim is removed from
   current findings and appears only as stale or historical evidence.
3. **Given** only a search snippet or similarly indirect trace, **When** the
   report is synthesized, **Then** that trace may challenge a stronger claim
   but cannot support a load-bearing conclusion.

---

### User Story 2 - Compare with Parallel by explicit choice (Priority: P2)

As the product owner, I want to run the same research question against Parallel
as an optional paid baseline, so I can test the quality thesis without turning
that vendor into the default product or surprising anyone with a bill.

**Why this priority**: The original product goal is to beat a web-index
researcher on evidence quality. A fair, repeatable duel makes that claim
testable, while the core researcher remains useful without it.

**Independent Test**: Score a stored researcher run once with no paid baseline
selected, once with Parallel selected but unavailable, and once with a recorded
Parallel response. No live paid call is required for the test.

**Acceptance Scenarios**:

1. **Given** no paid baseline was selected, **When** an evaluation runs,
   **Then** no Parallel request is made and the existing free baseline behavior
   remains unchanged.
2. **Given** Parallel was selected but its credential is absent, **When** the
   evaluation runs, **Then** the baseline is marked unavailable, the reason is
   clear, and the researcher side is still scored and recorded.
3. **Given** a valid recorded Parallel response, **When** both sides are scored,
   **Then** they are judged on the same evidence axes and equivalent citation
   shapes count equally.

---

### User Story 3 - Read an honest comparison result (Priority: P3)

As a reviewer, I want the evaluation record to explain what ran, what failed,
which evidence counted, and whether a source is truly native social evidence,
so a headline score cannot hide an unfair or incomplete comparison.

**Why this priority**: A numeric win is harmful if documentation pages are
misclassified as social evidence or a failed baseline silently becomes zero.

**Independent Test**: Evaluate fixtures containing native social links,
platform help pages, plural excerpt fields, a baseline error, and empty result
sets; then inspect the durable evaluation record.

**Acceptance Scenarios**:

1. **Given** a platform help or documentation page, **When** social coverage is
   scored, **Then** it does not count as native social evidence.
2. **Given** evidence represented by one excerpt or a list of excerpts,
   **When** primary-source depth is scored, **Then** all valid equivalent forms
   are counted without double counting.
3. **Given** a selected baseline that fails, **When** the evaluation finishes,
   **Then** the record distinguishes unavailable from a legitimate zero score
   and identifies the selected provider without exposing credentials.

### Edge Cases

- The question is broad enough to require decomposition before source-specific
  searches can be compared fairly.
- Evidence has a publication date but the underlying fact date is unknown.
- A current secondary source repeats an old first-party claim without new
  confirmation.
- One claim has both current weak evidence and stale strong evidence.
- A response contains malformed, duplicate, singular, and plural citation
  fields in the same payload.
- A URL is hosted on a social platform's documentation or support subdomain.
- The selected paid baseline times out or returns an invalid response after the
  researcher side has already been scored.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The default research and evaluation path MUST NOT select or call
  Parallel; the paid baseline MUST require an explicit per-run choice.
- **FR-002**: Selecting an unavailable paid baseline MUST produce an honest
  unavailable result without preventing the researcher run from being scored
  and recorded.
- **FR-003**: A broad human question MUST be decomposed into source-appropriate
  questions before evidence collection; one blanket query across all sources
  MUST NOT qualify as the deep comparison workflow.
- **FR-004**: Every load-bearing claim MUST identify a fact date when known and
  MUST carry exactly one strongest applicable proof tier.
- **FR-005**: Proof tiers MUST distinguish direct primary evidence, independent
  current confirmation, secondary reporting, and indirect traces such as search
  snippets.
- **FR-006**: Evidence older than 12 months that lacks current confirmation MUST
  be excluded from current findings and labeled stale or historical.
- **FR-007**: Indirect-trace evidence MUST NOT support a load-bearing claim; it
  MAY be used to rebut, narrow, or request better evidence for one.
- **FR-008**: Both comparison sides MUST be scored on primary-source depth,
  freshness, and native social coverage using equivalent evidence rules.
- **FR-009**: Native social coverage MUST count content-native social evidence
  and MUST exclude help, support, documentation, or marketing pages merely
  hosted on a social platform's domain.
- **FR-010**: Equivalent singular and plural excerpt representations MUST be
  parsed consistently, with malformed and duplicate entries handled safely.
- **FR-011**: Every evaluation record MUST identify the selected baseline, its
  availability, the reason for unavailability or failure, the counted evidence,
  and any reported or estimated cost.
- **FR-012**: Evaluation output MUST NOT contain credentials, credential
  fragments, or personal absolute paths.
- **FR-013**: Automated validation MUST make no live or paid provider calls.
- **FR-014**: monid MAY supply an explicit project-local or external evaluation
  input, but this feature MUST NOT add a hidden public runtime dependency,
  connector, or required service relationship to monid.
- **FR-015**: Existing free-baseline behavior and the default investigate
  workflow MUST remain available when the optional comparison is not used.

### Key Entities

- **Evaluation Run**: One comparison attempt for a question, including the
  selected baseline, availability state, scores, cost disclosure, and errors.
- **Evidence Item**: A source-backed excerpt with provenance, content location,
  publication time, and the date of the fact it is used to support when known.
- **Claim Assessment**: A load-bearing statement linked to its evidence, fact
  date, proof tier, freshness state, and disposition as current, stale, rebuttal,
  or unsupported.
- **Proof Tier**: An ordered evidence strength class from direct primary proof
  through indirect trace, with explicit rules about which claims it may support.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a fixture set covering all four proof tiers, 100% of
  load-bearing claims receive one tier and a freshness disposition, with no
  indirect trace used as supporting proof.
- **SC-002**: In all cases where the only support is more than 12 months old,
  100% of those claims are absent from current findings unless a current source
  independently confirms them.
- **SC-003**: Running the default evaluation with no paid baseline selected
  produces zero Parallel network attempts and preserves a usable researcher
  score and evaluation record.
- **SC-004**: Missing credentials, timeouts, invalid responses, and empty
  results each yield a truthful unavailable or empty state in 100% of covered
  cases, never a fabricated zero-score loss or success.
- **SC-005**: Singular and plural excerpt fixtures produce the same depth score
  for semantically identical evidence, while duplicates do not increase it.
- **SC-006**: All platform help, support, and documentation URLs in the social
  classification fixture set are excluded from native social coverage.
- **SC-007**: The complete automated suite and no-paid-call self-test pass with
  no credential values or personal absolute paths in committed artifacts.

## Assumptions

- The existing investigate workflow remains the user-facing default and owns
  broad-question decomposition.
- A 12-month freshness boundary is the default for load-bearing product and
  market claims; a future domain-specific policy may tighten it in a separate
  feature.
- The same three existing evaluation axes remain sufficient for this iteration;
  this feature improves fairness and evidence honesty rather than inventing a
  composite quality score.
- Stored or mocked paid-baseline responses are sufficient for automated
  validation; a real paid duel is an operator-run acceptance step.
- Recurring score dashboards, hosted evaluation services, publication, version
  bumps, and a monid connector are outside this feature.

# Phase 0 Research: Parallel Baseline and Claim Freshness

## Decision 1: Keep Parallel an explicit evaluation baseline

**Decision**: Add Parallel only behind a per-run baseline selection in the
existing evaluation harness. A configured key is not consent to spend it.

**Rationale**: This tests the original quality claim directly while preserving
the default free web-index comparison and the installable research product.
Provider absence or failure can be represented as unavailable without changing
the researcher score.

**Alternatives considered**:

- Make Parallel the default baseline: rejected because it creates surprise
  spend and makes ordinary evaluation depend on a paid vendor.
- Add Parallel as a research connector: rejected because this feature measures
  the product; it does not outsource the product's evidence collection.
- Build a separate benchmark service: rejected because a local CLI and JSONL
  record already cover the intended one-run comparison.

## Decision 2: Use the current asynchronous Task API contract

**Decision**: Start one Task Run, send the key only in the `x-api-key` header,
poll by run ID with a bounded deadline, and score the returned content and basis
citations. Expose only the `pro`, `pro-fast`, `ultra`, and `ultra-fast` deep
research processors in this iteration.

**Rationale**: Parallel's official Task API documentation identifies pro and
ultra as the deep-research choices and confirms asynchronous polling for
one-off scripts. Official pricing checked on 2026-08-14 is $0.10 per pro run and
$0.30 per ultra run, with fast variants at the same price.

**Alternatives considered**:

- Add the vendor SDK: rejected because direct HTTPS keeps the project stdlib
  only and the required contract is small.
- Use webhooks or streaming: rejected because a local one-off CLI has no hosted
  callback and does not need live progress events.
- Expose every processor: rejected because lower tiers are not a fair deep
  research opponent and higher multiplier tiers expand cost/scope materially.

**Primary references**:

- <https://docs.parallel.ai/task-api/guides/choose-a-processor>
- <https://docs.parallel.ai/getting-started/pricing>
- <https://docs.parallel.ai/task-api/examples/task-deep-research>

## Decision 3: Grade claims in the investigate playbook

**Decision**: Before synthesis, the session decomposes the human question and
assigns each load-bearing claim a fact date and one evidence tier: T1 primary,
T2 first-hand numbers, T3 informed opinion, or T4 unsupported. T4 can rebut but
cannot support. Claims older than 12 months without fresh T1/T2 confirmation
move to the stale/historical section.

**Rationale**: The session, not the stateless connector runner, understands what
the user is deciding and which facts carry the conclusion. Encoding the rule in
the playbook improves every source without pretending a keyword heuristic can
judge epistemic support.

**Alternatives considered**:

- Automatically tier claims in Python: rejected because the runner does not own
  synthesis semantics and a heuristic would create false confidence.
- Use page publication date as fact date: rejected because a current article
  can repeat a years-old claim.
- Drop all evidence older than 12 months: rejected because old evidence remains
  useful as explicitly historical context and for identifying what changed.

## Decision 4: Score evidence shapes fairly and conservatively

**Decision**: Count a distinct URL as depth only when it carries a usable
excerpt, accept equivalent singular and plural excerpt fields, deduplicate URLs,
and exclude corporate help/support/docs/blog subdomains from native social
coverage. Unknown freshness stays unknown.

**Rationale**: A real duel exposed two rigging risks: the live response used a
plural excerpts field, and `help.x.com` was mistaken for reading native X
conversation. Both errors can make a comparison look stronger than its data.

**Alternatives considered**:

- Count every citation as primary depth: rejected because a pointer without
  source voice is not evidence.
- Count any URL on a social domain as native social: rejected because platform
  documentation is ordinary indexed web content.
- Treat missing dates as fresh or zero age: rejected because absence of a date
  is uncertainty, not proof of freshness.

## Decision 5: Keep monid outside the public runtime

**Decision**: monid may prepare or select an explicit evaluation input outside
this feature. The shipped plugin gains no import, connector, endpoint, hidden
lookup, or required local path related to monid.

**Rationale**: This keeps one public product boundary and prevents a private or
experimental neighboring system from becoming an undocumented prerequisite.

**Alternatives considered**:

- Add a monid connector now: rejected because no user-facing contract or
  validated runtime need was established.
- Read monid state implicitly when present: rejected because identical commands
  would then behave differently across machines without disclosure.

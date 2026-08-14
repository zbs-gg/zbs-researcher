# Research Decisions: Live Duel Benchmark

## Decision 1: Freeze a committed suite; keep results private

**Decision**: Store the five exact questions, rubric, thresholds, budgets, and
rules in `benchmarks/duel-v1.json`. Copy that definition plus its SHA-256 digest
into each ignored runtime bundle.

**Rationale**: A committed definition prevents result-driven question changes,
while ignored runtime storage protects personal research and licensed/social
content from accidental publication.

**Alternatives considered**: An all-runtime suite is easy to mutate; committing
answers would expose private/provider material; a database adds no value for a
single internal five-case experiment.

## Decision 2: Reuse feature-001 Parallel receipts

**Decision**: Import `eval_harness.py` locally and use its detailed outcome and
private artifact writer for Parallel attempts.

**Rationale**: It already owns API transport, opt-in cost disclosure, bounded
polling, raw response capture, citation normalization, scoring, redaction, and
atomic permissions. A second client would create two definitions of the same
evidence and spend boundary.

**Alternatives considered**: Calling its subprocess CLI complicates mocking and
error handling; reimplementing the client risks scorer and receipt drift.

## Decision 3: Make paid confirmation local to each attempt

**Decision**: `run-parallel` without `--confirm-paid` is a no-network preflight.
The flag authorizes only the named question's next allowed attempt; it is not
stored as future consent.

**Rationale**: Suite approval and provider configuration do not authorize spend.
Per-attempt confirmation also exposes current listed cost immediately before
the existing paid executor runs.

**Alternatives considered**: A bundle-wide consent bit remains active after
context changes; an interactive prompt is brittle for agents and automation.

## Decision 4: Model attempts append-only and promote success explicitly

**Decision**: Store numbered attempt directories. A completed attempt becomes
the selected answer. A failed attempt may be followed only with
`--retry-technical`; successful or merely poor answers cannot be replaced.

**Rationale**: This distinguishes genuine infrastructure failures from answer
shopping and retains the exact failed trace for audit.

**Alternatives considered**: Overwriting one directory destroys history;
allowing arbitrary retries biases the benchmark.

## Decision 5: Snapshot, do not automate, Researcher

**Decision**: Validate and copy a completed investigate run containing
`research-plan.md`, `manifest.json`, `synthesis.md`, and at least one successful
raw result. The plan must contain the exact frozen question.

**Rationale**: Researcher is a session-authored iterative workflow. Replacing it
with a thin script would change the participant under test and bypass its
source-specific decomposition and drill judgment.

**Alternatives considered**: Driving a blanket runner query would be easier but
would not test Researcher investigate mode.

## Decision 6: Treat the mapping and reviewer forms as private state

**Decision**: Generate sanitized A/B Markdown, store the mapping separately
with private permissions, and create explicit AI-audit and owner-judgment JSON
forms. Tests inject a seeded RNG; official runs use system randomness.

**Rationale**: Provider labels influence reviewers, while deterministic tests
must prove both mapping stability and reversibility.

**Alternatives considered**: Hash parity is deterministic but predictable;
manual renaming is unauditable and error-prone.

## Decision 7: Fail closed on incomplete judgment

**Decision**: Require every score, audit status, critical-error explanation, and
pair before report generation. Derive results rather than accepting a manually
entered winner.

**Rationale**: A partial report can look authoritative and conceal missing
checks. The critical-error veto must be mechanical once the finding is marked
confirmed.

**Alternatives considered**: Draft reports with provisional winners invite
premature conclusions; treating missing fields as zero unfairly penalizes one
side.

## Decision 8: Current Parallel price snapshot is metadata, not permanent truth

**Decision**: Seed v1 with Ultra at USD 0.30 per successful run and USD 1.50 for
five successful official calls, verified 2026-08-14. Record the official pricing
and processor URLs and require a fresh preflight verification before live use.

**Rationale**: Parallel currently lists Ultra at USD 300 per 1,000 Task Runs
(USD 0.30 each), 5–25 minute standard latency, and billing only for completed
runs. Vendor facts can change; the bundle must preserve which snapshot governed
the experiment and separately capture actual available charge.

**Sources**:

- https://docs.parallel.ai/getting-started/pricing
- https://docs.parallel.ai/task-api/guides/choose-a-processor

**Alternatives considered**: Hard-coding price without a source is not auditable;
fetching live docs automatically would add network behavior to initialization
and would not prove a human reviewed the changed terms.

## Constitution re-check after design

All gates remain passed. No design adds an implicit provider, live test,
credential persistence, public answer artifact, personal absolute path, monid
lookup, or automated publication/merge.

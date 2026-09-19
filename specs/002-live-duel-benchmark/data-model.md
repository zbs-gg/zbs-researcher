# Data Model: Live Duel Benchmark

## Benchmark Suite

- `schema_version`: integer
- `suite_id`: stable string (`duel-v1`)
- `language`: `en`
- `questions`: exactly five ordered Question Definitions
- `rubric`: five named dimensions, each bounded 0–4
- `rules`: attempt, ordering, 24-hour, margin, veto, and overall-winner rules
- `budgets`: Parallel and Researcher caps with currency and price basis
- `sources`: authoritative pricing and processor documentation URLs

Validation: the suite is immutable after bundle initialization; each runtime
copy must match the stored digest.

## Benchmark Bundle

- `bundle_id`, `suite_id`, `suite_digest`
- `state`: `initialized`, `collecting`, `ready_for_review`, `complete`
- `created_at`, `deadline_at`
- `git_sha`, Python version, tool versions
- provider availability booleans (never values)
- frozen budgets and questions
- relative paths to five Question Records

State transitions:

```text
initialized -> collecting -> ready_for_review -> complete
```

No transition skips missing pair/audit/judgment validation.

## Question Record

- `question_id`, ordinal, exact text, source-plan state
- Researcher Snapshot or null
- ordered Parallel Attempt summaries
- selected Parallel attempt or null
- blind material/mapping state
- AI Audit state
- Owner Judgment state
- derived objective metrics and result

## Researcher Snapshot

- captured timestamp and source run digest
- relative paths for plan, manifest, synthesis, and copied raw materials
- objective scores
- validation receipt: exact-question match, complete manifest, successful source
- duration from source metadata
- one unique receipt per paid call with actual, estimated, or unavailable cost
- conservative USD reconciliation by call ID whenever the provider amount is unavailable

Once accepted, the snapshot is immutable.

## Parallel Attempt

- `attempt_number`
- `state`: `completed` or `technical_failure`
- technical failure reason/classification when applicable
- run ID, start/end, duration, processor, price/cost basis
- relative paths to raw response, answer, evidence, and outcome
- objective scores or null

A completed attempt is selected exactly once. A later attempt is legal only
after `technical_failure` and explicit retry authorization.

## Blind Pair

- `answer_a.md`, `answer_b.md`
- private mapping `A|B -> researcher|parallel`
- RNG receipt suitable for tests without revealing official entropy
- sanitization receipt for participant-name headings

## AI Audit

For A and B:

- `status`: `pending` or `complete`
- `claims`: non-empty ledger of every load-bearing claim
  - claim text and citations
  - `citation_fit`: `supports`, `partial`, `does_not_support`, or `not_applicable`
  - fact date and `freshness`: `current`, `stale`, `undated`, or `not_applicable`
  - `support_status`: `verified`, `bounded_inference`, `unsupported`, or `contradicted`
  - non-empty evidence note
- `unsupported_recommendations`: list
- `omissions`: list
- `contradictions`: list
- `critical_error`: `{confirmed, decision_changing, evidence_note}`

## Owner Judgment

For A and B, integer 0–4 scores for:

- `usefulness`
- `correctness`
- `evidence_fit`
- `freshness`
- `uncertainty_honesty`

Also includes notes, timestamp, and acknowledgment that the blind mapping was
not consulted.

## Derived Result

- per-answer quality totals (0–20)
- absolute difference
- veto state
- per-question result: `A`, `B`, or `tie`
- resolved participant result through private mapping
- overall win/tie counts and winner
- cost and duration summary outside quality totals

Derived fields are regenerated and never accepted as authoritative input.

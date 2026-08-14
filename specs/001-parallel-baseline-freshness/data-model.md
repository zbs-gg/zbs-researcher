# Data Model: Parallel Baseline and Claim Freshness

The feature persists no database schema. These logical records describe the
existing local artifacts and the session-authored report contract.

## Evaluation Run

One append-only row in `eval-log.jsonl`.

| Field | Meaning | Validation |
|---|---|---|
| `ts` | Evaluation timestamp | UTC ISO-8601 string |
| `question` | Human research question sent to both sides | Non-blank string |
| `baseline_kind` | Opponent selected for this run | `web-index` or `parallel` |
| `beast` | Researcher score set | Required even when baseline is unavailable |
| `baseline` | Opponent score set or honest unavailable string | Never silently coerced to zero |
| `processor` | Paid processor selected, when applicable | Allowed deep-research processor |
| `cost` | Disclosed per-run price or unknown label | Never guessed when unmapped |

### State transitions

```text
requested -> researcher_scored -> baseline_not_selected -> recorded
requested -> researcher_scored -> baseline_unavailable  -> recorded
requested -> researcher_scored -> baseline_running      -> baseline_scored -> recorded
requested -> researcher_scored -> baseline_running      -> baseline_failed -> recorded
```

The researcher score survives every baseline outcome.

## Score Set

| Field | Meaning | Validation |
|---|---|---|
| `depth` | Distinct source URLs with usable quoted evidence | Integer >= 0; URLs deduplicated |
| `freshness_hours` | Median known evidence age | Number >= 0 or null when unknown |
| `social_coverage` | Distinct native social/community platforms | Integer >= 0; corporate subdomains excluded |

## Evidence Item

| Field | Meaning | Validation |
|---|---|---|
| `url` | Live source location | Required to count toward depth |
| `excerpt` | One or more source excerpts | At least one usable excerpt to count |
| `source` | Connector/platform identity | Normalized for coverage only |
| `publication_date` | When the page or item appeared | Optional; not substituted for fact date |
| `fact_date` | When the supported fact became true | Required for load-bearing report claims when knowable |

## Claim Assessment

Session-authored record represented in `synthesis.md`.

| Field | Meaning | Validation |
|---|---|---|
| `claim` | Decision-relevant statement | Non-blank |
| `evidence` | One or more evidence items | At least one for a supported claim |
| `fact_date` | Date of the fact, not merely the page | Explicit unknown if unresolved |
| `tier` | Strongest applicable proof tier | Exactly one of T1, T2, T3, T4 |
| `freshness` | Current, stale, historical, or unresolved | Stale when >12 months without fresh confirmation |
| `disposition` | Support, rebuttal, context, open question, or dropped | T4 cannot have support disposition |

## Proof Tier

- **T1 — primary**: platform documentation, official announcement, open code,
  or a dated statement by the actor who performed the action.
- **T2 — first-hand numbers**: identifiable actor reporting their own measured
  result with figures and a date.
- **T3 — informed opinion**: identifiable practitioner's interpretation without
  first-hand measurements.
- **T4 — unsupported**: unattributed, undated, snippet-only, or otherwise
  ungrounded trace. It can narrow or rebut a claim but never support one.

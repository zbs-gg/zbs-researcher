# Contract: Evaluation CLI

## Invocation

```text
eval_harness.py QUESTION --beast-dir DIR
  [--out FILE_OR_DIR]
  [--baseline web-index|parallel]
  [--processor pro|pro-fast|ultra|ultra-fast]
  [--artifact-dir PRIVATE_DIR]
```

## Selection rules

- `--baseline` defaults to `web-index`.
- The presence of `PARALLEL_API_KEY` or `parallel-key.txt` MUST NOT change the
  default.
- A Parallel request is permitted only when the invocation contains
  `--baseline parallel`.
- `--processor` affects only the selected Parallel baseline.
- `--artifact-dir` is valid only with `--baseline parallel`; omitting it keeps
  the pre-existing lightweight evaluation behavior unchanged.

## Provider contract

- Endpoint family: `https://api.parallel.ai/v1/tasks/runs`.
- Credential transport: `x-api-key` request header only.
- Request input: the same non-blank question evaluated on the researcher side.
- Execution: asynchronous start followed by bounded status polling.
- Cost disclosure: provider, processor, and known list price are printed before
  the start request. Unknown processors/prices are labeled unknown.

## Score contract

Both sides expose:

```json
{
  "depth": 0,
  "freshness_hours": null,
  "social_coverage": 0
}
```

- `depth` counts distinct URLs carrying usable excerpts.
- `freshness_hours` is the median age of known items and remains null when the
  provider does not supply dates.
- `social_coverage` counts distinct native platforms, excluding corporate help,
  support, documentation, marketing, and status subdomains.

## Failure contract

Missing credentials, start failure, timeout, invalid response, and empty output
return an `unavailable - ...` baseline value. They MUST NOT:

- erase or prevent the researcher score;
- become a numeric zero presented as a loss;
- expose a key, key fragment, credential-bearing URL, or personal absolute path;
- crash evaluation record creation.

## Persistence contract

One JSON object is appended to `eval-log.jsonl` in the explicit output location
or the researcher run directory. The row names `baseline_kind` so tables and
later comparisons cannot mislabel the opponent.

When `--artifact-dir` is selected, the row also contains only relative artifact
names and the directory becomes a private audit bundle:

- `parallel-raw.json` — complete provider result after secret/path redaction;
- `parallel-answer.md` — readable answer plus the citations supplied for it;
- `parallel-evidence.json` — normalized citations, excerpts, deduplication and
  explicit depth/social score receipts;
- `parallel-outcome.json` — run ID, state, UTC start/end, measured duration,
  processor, published price and source, scores, and relative artifact names.

Each artifact is written through an atomic replacement with mode `0600`; the
bundle directory is mode `0700` on POSIX. `parallel-outcome.json` is written
last and is the completion marker. No credential or personal absolute path may
appear in an artifact or the ledger row.

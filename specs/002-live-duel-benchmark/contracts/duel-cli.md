# Contract: Duel Benchmark CLI

## Shared rules

```text
duel_benchmark.py COMMAND [options]
```

- `--suite` defaults to `benchmarks/duel-v1.json`.
- All bundle-internal paths stored in JSON are relative POSIX paths.
- Files are atomically replaced with mode `0600`; created runtime directories
  are mode `0700` on POSIX.
- A bundle suite digest mismatch aborts every mutating command.
- Exit `0` means the requested state was durably created; validation or consent
  failures are non-zero and make no partial state transition.

## `init`

```text
duel_benchmark.py init [--suite FILE] [--bundle DIR]
  [--confirm-price-checked]
```

Creates `research/duel-v1-<UTC timestamp>/` by default and writes:

- `suite.json`: frozen committed suite plus digest;
- `bundle.json`: identity, git SHA, versions, state, created/deadline times;
- `preflight.json`: provider availability booleans, budgets, processor, listed
  price and authoritative URLs, plus `paid_authorized: false`.

No provider or paid call is permitted. `--confirm-price-checked` records that
the operator has just re-opened the two authoritative pages; it still does not
authorize a Task API call. A later paid attempt requires this price receipt and
its own `--confirm-paid` flag.

## `snapshot-researcher`

```text
duel_benchmark.py snapshot-researcher --bundle DIR --question q01 --run-dir DIR
  [--technical-failure-reason TEXT]
```

Requires the exact frozen question, `research-plan.md`, `manifest.json`,
`synthesis.md`, and at least one successful raw result. Copies the complete run
under `questions/q01/researcher/`, computes objective metrics, and freezes a
snapshot receipt. A successful existing snapshot cannot be replaced.

An incomplete attempt may be copied first with
`--technical-failure-reason`; this preserves its raw trace and permits a later
completed snapshot. A run with a synthesis and successful source cannot be
reclassified this way merely because its answer is poor. Reported paid-source
cost entries require provider, USD amount, and basis, and the cumulative five-
question Researcher cost may not exceed USD 10.

## `run-parallel`

```text
duel_benchmark.py run-parallel --bundle DIR --question q01
  [--confirm-paid] [--retry-technical]
```

Without `--confirm-paid`, prints question, processor, published price, remaining
budget, and readiness, then exits without network. Confirmed execution requires
a frozen Researcher snapshot and an open 24-hour window. `--retry-technical`
is accepted only when the previous attempt is a recorded technical failure.
Every attempt has a numbered private directory and reuses the full feature-001
Parallel outcome/artifact contract.

## `blind`

```text
duel_benchmark.py blind --bundle DIR --question q01
```

Requires complete Researcher and Parallel answers. Produces `answer-a.md`,
`answer-b.md`, a private `mapping.json`, and blank `ai-audit.json` and
`owner-judgment.json` forms. Participant headings are neutralized. Existing
blind material cannot be regenerated. Tests may inject RNG through the Python
function; the public CLI does not expose an official-run seed.

## `report`

```text
duel_benchmark.py report --bundle DIR
```

Validates all five pairs, mappings, completed AI audits, and complete owner
scores. It refuses any missing/invalid input. For each question it computes:

- five-dimension A/B totals;
- winner only when the margin is at least three;
- a veto preventing an answer with a confirmed decision-changing critical
  error from winning;
- participant identity through the private mapping.

The overall report requires at least three question wins. A 2-2-1 result is a
tie. Objective metrics, duration, and cost are presented in separate sections
and never alter quality totals. Output: private `report.json` and `report.md`.

## Error and retry contract

- A poor, incomplete, or weak answer is a completed answer, not a technical
  failure, and cannot be rerun.
- A failed paid attempt retains its outcome and authorizes at most the next
  explicitly confirmed `--retry-technical` attempt.
- The old and retry traces are never overwritten.
- No command publishes, commits, uploads, merges, or invokes monid.

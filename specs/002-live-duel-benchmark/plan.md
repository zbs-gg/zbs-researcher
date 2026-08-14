# Implementation Plan: Live Duel Benchmark

**Branch**: `codex/live-duel-benchmark` | **Date**: 2026-08-14 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/002-live-duel-benchmark/spec.md`

## Summary

Build a private, restartable benchmark controller around the existing
Researcher run format and feature-001 Parallel audit bundle. Commit one frozen
five-question suite and a stdlib CLI that initializes the experiment,
validates/copies completed Researcher runs, gates and records Parallel Ultra
attempts, creates blind A/B review material, and refuses to report a winner
until every audit and judgment is complete. Runtime answers stay under the
ignored `research/` tree; implementation, contract, fixtures, and tests are the
only committed artifacts.

## Technical Context

**Language/Version**: Python 3.9+

**Primary Dependencies**: Python standard library only; imports the existing
`eval_harness.py` locally for Parallel execution, scoring, price disclosure, and
private artifact persistence

**Storage**: Versioned JSON suite in `benchmarks/`; private atomic JSON/Markdown
runtime bundle in ignored `research/duel-v1-<UTC timestamp>/`

**Testing**: Python `unittest` with temporary directories, injected RNG/time,
mocked provider functions, full unittest discovery, and `scripts/selftest.sh`

**Target Platform**: Claude Code/Codex plugin on macOS, Linux, and Windows-safe
Python paths

**Project Type**: Existing CLI/plugin; one additional local operator CLI

**Performance Goals**: All non-provider commands complete locally in under two
seconds for five typical run bundles; provider time remains separately measured
and unbounded by report generation

**Constraints**: No paid/live calls in tests or initialization; explicit
`--confirm-paid` required per Parallel attempt; one successful attempt per
participant/question; technical retries preserve all attempts; only relative
paths in records; atomic mode-0600 files and mode-0700 runtime directories on
POSIX; no non-stdlib package, service, publication, merge, or monid dependency

**Scale/Scope**: Exactly five questions, two participants, up to one successful
attempt plus preserved technical failures per side, one owner and one AI audit,
all official attempts within a frozen 24-hour window

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

- **Evidence Before Claims — PASS**: complete raw answers, citations, normalized
  score receipts, claim audit, stale/current distinctions, and unresolved
  findings stay inspectable; report generation fails closed on missing evidence.
- **Quality Is the Product — PASS**: five fixed questions test practical,
  web-first, and scientific research; cost and latency remain separate from the
  five quality dimensions.
- **Explicit Spend — PASS**: `init`, snapshot, blind, and report are offline;
  `run-parallel` remains a preflight unless `--confirm-paid` is supplied, and
  tests inject a fake executor.
- **Portable and Graceful Execution — PASS**: stdlib only, no shell/process
  dependency, portable relative paths, and explicit technical-failure records.
- **Plan, Test, Review — PASS**: living spec/design/tasks, focused contract and
  end-to-end tests, full suite/selftest, analyze, converge, and diff review.
- **Runtime and privacy constraints — PASS**: runtime is explicit, ignored,
  private, sanitized, and never uploaded; the public tree contains synthetic
  fixtures only.

## Project Structure

### Documentation (this feature)

```text
specs/002-live-duel-benchmark/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── duel-cli.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
benchmarks/
└── duel-v1.json                     # frozen questions, rubric, rules, budgets

skills/deep-research/
├── scripts/
│   ├── duel_benchmark.py            # init/snapshot/run/blind/report controller
│   ├── eval_harness.py              # existing Parallel executor + receipts
│   └── selftest.sh                  # no-paid-call repository gate
└── tests/
    ├── fixtures/duel/               # synthetic complete/incomplete run inputs
    └── test_duel_benchmark.py        # unit + mocked package end-to-end tests

research/                             # gitignored private runtime only
└── duel-v1-<timestamp>/

README.md
CONFIGURATION.md
CHANGELOG.md
CLAUDE.md
```

**Structure Decision**: Keep orchestration beside the existing research and
evaluation scripts. The controller owns experiment state but delegates paid
execution and evidence normalization to `eval_harness.py`; it validates and
copies Researcher outputs rather than creating a second research runner.

## Implementation Phases

### Phase 0 - Frozen experiment design

Commit the exact suite and document decisions on bundle privacy, paid consent,
attempt state, question immutability, blinding, judgment validation, and winner
derivation. No runtime answer or provider call occurs in this phase.

### Phase 1 - Bundle lifecycle

Implement private atomic storage, suite hashing, preflight capture, Researcher
snapshot validation, question/time-window gates, and attempt history. Make
every stored path relative to the bundle and every state transition explicit.

### Phase 2 - Parallel and blinding

Reuse the feature-001 detailed Parallel outcome through an injected executor.
Without `--confirm-paid`, print the exact planned attempt and stop. After a
frozen Researcher snapshot, confirmed execution writes a numbered attempt and
promotes only a completed attempt. Blinding strips known participant headings,
uses injectable randomness, and keeps the mapping private.

### Phase 3 - Audit, judgment, and report

Generate blank audit/judgment forms, validate all dimensions and critical-error
notes, compute per-question results and the three-win overall result, and keep
objective metrics, duration, and cost outside the quality total. Refuse partial
or stale bundles rather than inferring missing values.

### Phase 4 - Verification and internal preflight

Run focused and mocked five-question end-to-end tests, the full suite, selftest,
Spec Kit analysis/convergence, privacy scan, and diff review. Initialize one
ignored non-paid runtime bundle as the handoff; do not execute official runs.

## Complexity Tracking

No constitution violation or exceptional architecture is required.

# Implementation Plan: Parallel Baseline and Claim Freshness

**Branch**: `codex/spec-kit-parallel-baseline` | **Date**: 2026-08-14 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/001-parallel-baseline-freshness/spec.md`

## Summary

Make the original quality thesis measurable without changing the default
product: extend the existing evaluation harness with an explicitly selected
Parallel Task API baseline, score stored evidence fairly on the same three
axes, and strengthen the investigate playbook so broad questions are decomposed
and every load-bearing claim is dated, tiered, and demoted when stale. Reuse the
current CLI, local JSONL ledger, secrets resolver, and session-authored
synthesis; add no service, dependency, connector, or hidden monid relationship.

## Technical Context

**Language/Version**: Python 3.9+ and POSIX-compatible shell for the existing
self-test

**Primary Dependencies**: Python standard library only; Parallel is an
optional HTTPS provider invoked directly through the existing HTTP helpers

**Storage**: Existing project-local Markdown/JSON run artifacts and append-only
`eval-log.jsonl`; no database or new global state

**Testing**: Python `unittest` with mocked network/time plus
`skills/deep-research/scripts/selftest.sh`

**Target Platform**: Claude Code plugin on macOS, Linux, and Windows-safe Python
runtime paths

**Project Type**: CLI/plugin with a session-authored research workflow

**Performance Goals**: Default evaluation begins without paid-provider work;
selected Parallel runs use bounded polling and report progress/cost before the
first paid call

**Constraints**: No paid calls in tests; Parallel never implicit; credentials
never logged; per-baseline failure degrades without losing the researcher
score; no new non-stdlib dependency; preserve existing self-test marker order

**Scale/Scope**: One question and one stored researcher run per evaluation;
dozens to hundreds of evidence links; one optional asynchronous baseline run

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

- **Evidence Before Claims — PASS**: the playbook requires fact dates, explicit
  proof tiers, stale demotion, open questions, and auditable links. The scorer
  counts quoted evidence rather than bare pointers.
- **Quality Is the Product — PASS**: investigate remains the default and
  Parallel is a measurement option, not a runtime dependency or positioning
  shortcut.
- **Explicit Spend — PASS**: only `--baseline parallel` authorizes a call; cost
  is shown first; all tests mock network, sleep, and time.
- **Portable and Graceful Execution — PASS**: the implementation stays stdlib,
  introduces no prohibited process primitives, and returns explicit unavailable
  states without exposing keys.
- **Plan, Test, Review — PASS**: this feature owns a spec, design artifacts,
  executable tasks, focused regression tests, full-suite validation, and final
  diff review.
- **Runtime and privacy constraints — PASS**: evaluation data remains beside
  the selected run or explicit output path. monid is only a permitted external
  input boundary and is not referenced by public runtime code.

## Project Structure

### Documentation (this feature)

```text
specs/001-parallel-baseline-freshness/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── eval-cli.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
skills/deep-research/
├── SKILL.md                         # decomposition and claim-grading playbook
├── scripts/
│   ├── eval_harness.py              # baseline selection, polling, parsing, scoring
│   └── selftest.sh                  # repository contract and no-paid-call smoke
└── tests/
    └── test_eval_harness.py         # deterministic eval behavior and regressions

README.md                            # public behavior and default-cost promise
CONFIGURATION.md                     # provider, credential, endpoint, cost, opt-in
CHANGELOG.md                         # unreleased user-visible changes
CLAUDE.md                            # repository operating contract
AGENTS.md                            # concise Codex/operator guardrails
```

**Structure Decision**: Extend the existing single-project CLI/plugin in place.
The optional provider belongs in the evaluation harness, while claim grading
belongs in the session playbook because the session reads and synthesizes the
evidence. Public documentation describes the boundary; no new package or
service is justified.

## Complexity Tracking

No constitution violations or exceptional complexity are required.

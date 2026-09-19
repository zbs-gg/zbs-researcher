# Implementation Plan: Monid X Source

**Branch**: `codex/monid-x-source` | **Date**: 2026-08-16 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-monid-x-source/spec.md`

## Summary

Add a default-off `x` connector that uses Monid's discover → inspect → run
contract to fetch current public X posts without consuming xAI API credit. Keep
the existing `grok` lens separate and fail it with explicit guidance rather
than automatically spending through Monid or OpenRouter. Remove Bluesky from
default single and entity-fan-out selection while preserving it as an explicit
best-effort connector. Record Monid route and price evidence honestly,
including the distinction between quoted and actual cost.

## Technical Context

**Language/Version**: Python 3.9+

**Primary Dependencies**: Python standard library only; Monid HTTPS API as an
optional pay-per-use integration

**Storage**: Existing Markdown channel artifacts plus append-only JSON call and
provenance receipts in each research run directory

**Testing**: Python `unittest` with injected HTTP responses, time, and sleeps;
full unittest discovery and `scripts/selftest.sh`

**Target Platform**: Claude Code/Codex plugin on macOS, Linux, and Windows-safe
Python paths

**Project Type**: Existing CLI/plugin with one optional direct-social connector

**Performance Goals**: Free discovery and inspection complete before the paid
request; synchronous and asynchronous results finish inside a bounded five
minute connector deadline; rendering remains linear in returned posts

**Constraints**: No live or paid calls in tests; no automatic paid fallback;
fail closed on unknown Monid routes; never print credentials; preserve one
failed-channel/healthy-siblings behavior; default Bluesky selection must be off

**Scale/Scope**: One query per explicit fire, up to the connector's requested
item limit, two initially validated Monid routes, no pagination in v1

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

- **Evidence Before Claims — PASS**: output retains post fields and canonical
  links; manifests keep the selected route, run ID, count, freshness, quoted
  price, and actual billing only when returned.
- **Quality Is the Product — PASS**: current X evidence is restored as a direct
  source; Bluesky remains available but no longer consumes default attention.
- **Explicit Spend — PASS**: Monid is default-off and key-gated; only an
  explicit `x` selection reaches its paid run, with provider and price announced
  after free preflight; failed Grok never triggers another provider.
- **Portable and Graceful Execution — PASS**: stdlib HTTPS and bounded polling,
  no `mcpc` or private-repository dependency, isolated error artifacts, and
  secrets resolved through the existing portable key contract.
- **Plan, Test, Review — PASS**: feature artifacts precede implementation;
  focused success/failure tests, full suite, selftest, analysis, and adversarial
  diff review are required.
- **Runtime and privacy constraints — PASS**: only public query text goes to
  Monid; the API credential remains in environment/secrets storage; all output
  remains in the launching project's allocated run.

## Project Structure

### Documentation (this feature)

```text
specs/003-monid-x-source/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── x-source-cli.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
skills/deep-research/
├── scripts/
│   ├── deep-research.py       # connector registry, X renderer, receipts
│   ├── monid_x.py             # stdlib discover/inspect/run/poll client
│   ├── detect_state.py        # Monid configured/absent state only
│   ├── entity_fanout.py       # revised default free-channel set
│   ├── provenance.py          # direct-X reachability and freshness
│   └── selftest.sh
└── tests/
    ├── test_monid_x.py        # route, response, cost, and failure fixtures
    ├── test_fire.py           # call receipt and no-fallback behavior
    ├── test_detect_state.py   # credential-presence contract
    ├── test_provenance.py     # direct-X coverage classification
    └── test_entity_fanout.py  # revised default selection

README.md
CONFIGURATION.md
CHANGELOG.md
skills/deep-research/SKILL.md
```

**Structure Decision**: Isolate provider-specific transport and normalization
in `monid_x.py`, then keep the public CLI contract in the existing runner. This
lets tests inject every HTTP transition without growing the already-large
runner or requiring Monid's CLI/MCP client.

## Implementation Phases

### Phase 0 - Provider contract

Pin the current official discover, inspect, run, polling, pricing, and xAI OAuth
facts. Define a small allowlist of compatible Monid routes and a fail-closed
selection rule rather than executing an unknown high-ranked catalog result.

### Phase 1 - Direct X source

Implement Monid key detection, free route preflight, bounded sync/async run,
nested post normalization, Markdown rendering, freshness capture, usage/cost
metadata, connector registration, and provenance.

### Phase 2 - Honest routing and defaults

Add actionable xAI spending-limit guidance with no fallback call. Disable
Bluesky in default connector and entity-fan-out selection while preserving
explicit selection. Update state output and all operator/public documentation.

### Phase 3 - Verification

Run focused Monid, fire, state, provenance, and fan-out tests; then the complete
unittest suite and ten-step selftest. Perform Spec Kit analysis and an
adversarial diff review focused on spend, route drift, cost wording, secrets,
and unchanged benchmark behavior.

## Complexity Tracking

No constitution violation or exceptional architecture is required.

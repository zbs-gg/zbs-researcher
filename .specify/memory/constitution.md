<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Added principles: Evidence Before Claims; Quality Is the Product; Explicit Spend;
  Portable and Graceful Execution; Plan, Test, Review
- Added sections: Runtime and Privacy Constraints; Delivery Workflow
- Removed sections: none
- Follow-up TODOs: none
-->
# ZBS Researcher Constitution

## Core Principles

### I. Evidence Before Claims
Every load-bearing research claim MUST be traceable to auditable source evidence.
Primary sources, verbatim excerpts, authorship, live links, evidence dates, and
known coverage gaps MUST be preserved where the source supports them. The system
MUST distinguish verified evidence, bounded inference, and unavailable or stale
evidence; it MUST NOT fabricate provenance, freshness, reach, or baseline results.

### II. Quality Is the Product
The product MUST optimize for research quality: source-specific questions,
native social and community depth, contradiction hunting, and problems-first
synthesis. Price and zero-key access are useful properties, not the core claim.
The default user path MUST remain the deepest supported investigate workflow;
short scans or paid comparison baselines require an explicit user choice.

### III. Explicit Spend
Anthropic and OpenAI API calls MUST remain disabled by default. Every connector
or evaluation path that can spend money MUST be opt-in, name the provider before
the call, degrade honestly when credentials are absent, and avoid surprise
fallbacks to another paid provider. Automated tests MUST make no paid or live
vendor calls and MUST use deterministic fixtures or mocks.

### IV. Portable and Graceful Execution
The core runner MUST use the Python standard library unless an optional feature
has a documented lazy dependency. Supported paths MUST remain Windows-safe and
MUST NOT introduce Unix-only process primitives prohibited by the repository
contract. One failed channel MUST produce an explicit error artifact while
unrelated channels continue. Secrets MUST come from the configured secrets
directory or environment and MUST never appear in output, logs, fixtures, or
version-controlled files.

### V. Plan, Test, Review
Every non-trivial change MUST begin with a written, reviewable specification and
implementation plan, include tests for its public behavior and failure paths,
and receive an adversarial diff review before landing. Verification MUST include
the complete project unittest suite and the no-paid-call self-test. Repeating a
review or archive scan without new code, a new failure, or a newly identified
risk is prohibited because it adds process without improving the product.

## Runtime and Privacy Constraints

- Research output MUST stay in the launching project's allocated run directory
  unless the user explicitly selects another destination.
- Credentials and personal machine paths MUST NOT be written into specs, tests,
  generated reports, public documentation, or evaluation logs.
- Network behavior MUST be documented per component: destination, transmitted
  data, credential, cost class, and default activation state.
- Optional external memory, profiling, or evaluation systems MUST remain
  explicit integrations. Their absence MUST NOT block local research.
- A public runtime feature MUST NOT acquire a hidden dependency on a private
  repository, personal archive, or unpublished service.

## Delivery Workflow

1. Start from the current `origin/main` and preserve unrelated worktrees and
   local artifacts.
2. Express user value and testable acceptance criteria in `spec.md`; keep
   implementation choices in `plan.md` and executable work in `tasks.md`.
3. Implement the smallest complete user story, then run focused tests followed
   by the full unittest suite and `bash scripts/selftest.sh`.
4. Review the final diff against this constitution, public documentation,
   privacy boundaries, cost behavior, and the product's quality claim.
5. Publishing, version bumps, merging, and other outward actions require the
   owner's explicit approval and current evidence that the candidate is ready.

## Governance

This constitution is the highest project-level authority for Spec Kit artifacts.
`CLAUDE.md` remains the operational reference and may add compatible detail, but
specifications, plans, tasks, reviews, and pull requests MUST satisfy every MUST
rule above. Amendments require an explicit rationale, an updated Sync Impact
Report, and a semantic version bump: MAJOR for incompatible governance changes,
MINOR for new or materially expanded principles, and PATCH for clarification.
Every non-trivial pull request MUST record its constitution check and validation
evidence; unresolved violations block landing.

**Version**: 1.0.0 | **Ratified**: 2026-08-14 | **Last Amended**: 2026-08-14

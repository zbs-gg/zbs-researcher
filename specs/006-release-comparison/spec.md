# Feature Specification: Version and evidence-backed comparison

**Created**: 2026-09-05

**Status**: Publication authorized; fresh matched benchmark deferred
**Input**: Update the version and README, showing research with ZBS beside other methods.

## Publication authorization — 2026-09-19

The owner subsequently explicitly authorized publication to GitHub and npm.
This supersedes the preparation-only prohibition for this release, not for
paid research or a new benchmark. Integrate with current main through a PR,
qualify the integrated tree, publish the plugin before its npm shim, and
record independent verification or an authentication blocker per channel.
Public docs must reflect the observed distribution state, not remain labelled
unpublished after a verified release. The original preparation acceptance
record below remains historical.

## User Scenarios & Testing

### User Story 1 — Understand the candidate and install the right thing (P1)

An interested user sees what the next version does, where their research lives,
and which installation route is available. They can distinguish a prepared
candidate from a published package.

**Independent test**: Inspect version-bearing files and README; all agree on
the candidate, preserve prior release history, and do not imply publication.

**Acceptance**: Given an older npm installer and a newer main branch, the next
version does not reuse either number. Both Codex local use and Claude installation
remain documented without implying the npm shim installs a Codex skill.

### User Story 2 — Inspect differences in actual research (P1)

A reader compares answers to an identical question, follows links to preserved
answer text, and sees the date, method and weaknesses of both sides.

**Independent test**: Follow comparison links offline and check included answer
sections and hashes; synthetic or unmatched comparisons are never scored as wins.

**Acceptance**: A historical ZBS/Parallel pair is clearly historical and is not
presented as a fresh test of the new version. Manual workflow comparison describes
work ownership, not untested restrictions of competing products.

### Edge Cases

No fresh competitor result: disclose the gap. Private source material: prepare
only bounded inspected excerpts, never publish private logs or credentials.
Unfinished blind evaluation: no winner or derived win-rate. Costs: no new paid calls.

## Requirements

- **FR-001**: All candidate version identifiers MUST agree and exceed existing known versions; preserve 0.6.0 history.
- **FR-002**: README MUST explain purpose, project storage, final deliverables, Codex/Claude routes and unpublished status.
- **FR-003**: Comparison MUST show the same question and actual dated answers side by side with inspectable supporting text.
- **FR-004**: Both sides' strengths, weaknesses and evidence limits MUST remain visible; no invented measurements or current-version victory.
- **FR-005**: Manual-method comparison MUST distinguish described workflow from experimentally established product capabilities.
- **FR-006**: Preparation MUST not publish, spend, mutate original benchmark records, expose private paths or resolve pending blind judgments.

## Key Entities

Candidate version; dated comparison case; preserved answer extract; limitations;
origin and content digest identifying the inspected historical inputs.

## Success Criteria

- Version consistency and comparison link/integrity checks pass offline.
- Reader can open both answers from one comparison table without private files.
- Full tests and 10-step self-test pass, plus one scoped adversarial review.
- No remote publication or paid-provider invocation occurs.

## Assumptions

Owner authorized a version bump and local documentation changes, not publication.
Reuse the existing completed historical pair; fresh matched benchmarking is
explicitly deferred. This is release preparation, not new runtime functionality.

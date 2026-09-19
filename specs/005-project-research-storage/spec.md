# Feature Specification: Project-local research workspace

**Created**: 2026-09-05

**Status**: Locally qualified; unreleased
**Input**: Research belongs inside the project where the researcher was invoked. Separate received materials from processed analysis, automatically deliver a report, and let future agents reuse the data and conclusions.

## User Scenarios & Testing

### User Story 1 — Organized research without manual filing (Priority: P1)

As a project owner, I want each research run to create its own source and analysis folders and produce the established human/agent deliverables.

**Independent Test**: Prepare and finalize an offline fixture; source bytes remain unchanged, analysis lives separately, both final documents are linked.

**Acceptance Scenarios**:
1. Given an existing project, when preparation runs, then one uniquely named run contains separate raw and processed directories and explicit returned paths.
2. Given collected materials and a valid dossier, when finalized, then playbook.html and agent-context.json share a digest and an inventory identifies their supporting files.
3. Given an old flat run, when finalized, then it remains readable without automatic migration.

### User Story 2 — A future agent can find and reuse this project's research (Priority: P1)

As a project agent, I want one local entry point listing research goals, dates, status and result paths so I can reuse relevant findings with their caveats.

**Independent Test**: Create two independent projects and multiple runs; each index lists only its own runs. Follow its relative links to claims and source artifacts.

**Acceptance Scenarios**:
1. Preparation lists the run as draft; successful export lists its actual complete/partial status.
2. Missing or inconsistent export files are not advertised as a validated result.
3. Existing unrelated files, symlink targets and other projects are not overwritten or scanned.

### Edge Cases

- Interrupted export or index update: explicit incomplete state and an offline rebuild path.
- Same goal twice: numbered siblings, no overwrite.
- Existing user-owned index file: refuse replacement and explain conflict.
- Legacy runs: no inferred raw/processed classification, no moving their source files.
- Raw source content is untrusted; stored output does not establish semantic truth or freshness.

## Requirements

### Functional Requirements

- **FR-001**: New goal-driven runs MUST create raw/ and processed/; the shared working dossier MUST reside in processed/dossier.json.
- **FR-002**: Received source material MUST be distinct from agent-authored analysis. Normalized connector records must retain their provenance; their directory MUST NOT imply original wire bytes or direct verification.
- **FR-003**: Finalization MUST preserve source bytes and produce exactly the existing two final documents plus internal artifact bookkeeping.
- **FR-004**: Preparation and finalization MUST refresh a project-local research index with relative paths, goals, dates and truthful status.
- **FR-005**: Future agents MUST have a documented local entry point and read conclusions with source links, coverage gaps and dates before reuse.
- **FR-006**: Indexing MUST remain within the selected project's research directory, reject escaping symlinks and preserve user-owned conflicting files.
- **FR-007**: Old flat goal-driven runs MUST remain readable/finalizable without automatic migration; unrelated legacy quick scans MUST not masquerade as validated runs.
- **FR-008**: Organization/indexing MUST be offline, stdlib-only and Windows-safe. No paid API calls, global catalog, server, database or root AGENTS.md edits.

### Key Entities

- Run: brief, source captures, processed dossier, final pair, inventory.
- Project index: owned generated listing of only that project's recognized goal-driven runs.
- Artifact: relative path, storage role, size and content digest; not a truth assertion.

## Success Criteria

- **SC-001**: Offline preparation and finalization require no manual directory creation or catalog editing.
- **SC-002**: All indexed final links and evidence paths resolve within the selected run/project; raw byte hashes remain unchanged after export.
- **SC-003**: Two-project isolation, legacy compatibility, conflict protection and broken-export status are covered by deterministic tests.
- **SC-004**: Full unittest suite and 10-step self-test pass; installed local Codex copy matches the qualified candidate. Publication remains separate.

## Assumptions and Scope

The host agent performs collection and synthesis using the installed skill. This is not a standalone unattended service. raw/ holds received source captures (including connector-normalized capture records); processed/ holds agent notes, analysis and dossier. Captures are not automatically evidence of direct access. No cross-project memory or automatic migration of prior runs is requested.

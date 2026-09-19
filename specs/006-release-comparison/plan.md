# Implementation Plan: 0.7.0 and side-by-side evidence

**Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

## Summary

Prepare version 0.7.0 without publication; update README with an actual historical same-question comparison and a separate manual-workflow comparison. Preserve dated evidence and failure limits.

## Technical Context

Markdown/JSON only, existing Python unittest/selftest. No new dependency, renderer or runtime feature. Read local archived q02 answers; retain inspected answer sections plus references, excluding massive raw quote appendices. Copy no credentials/private machine paths. Hash original and curated inputs for traceability.

## Constitution Check

Pre/post design PASS: no invented results or winner, no paid calls/publication, preserve dirty worktree and private originals, tests first. Work remains on owner's existing checkout; no branch/merge operation.

## Files

- .claude-plugin/plugin.json and marketplace.json; installer/package.json.
- README.md, CHANGELOG.md, installer/README.md, installer/RELEASE.md, CLAUDE.md, docs/README.md.
- docs/comparison/README.md, case.json, researcher.md, parallel.md.
- skills/deep-research/scripts/selftest.sh; tests/test_release_docs.py.
- This feature's spec/design/tasks and qualification record.

## Sequence

Offline tests → version metadata/history → curated historical extracts and side-by-side docs → full tests/selftest and installer package dry-run → one final diff/evidence review. No new live comparison; current-version benchmark stays explicitly deferred.

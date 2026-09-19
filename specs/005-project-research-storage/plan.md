# Implementation Plan: Project-local research workspace

**Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing offline session helper, not the research engine. Create separate raw/processed paths and a layout marker; preserve the final pair at the run root. Generate an inventory and project-only index automatically. Keep flat legacy runs compatible.

## Technical Context

- Python 3.9+ and standard library; local JSON/Markdown files, no database.
- CLI/skill for Codex and Claude; existing agent performs collection and synthesis.
- Tests: unittest temporary projects and fixtures, no network. Full suite and self-test after integration.
- Scope: only selected project's research directory. Scan direct recognized run children, never other projects.
- Performance: bounded by local run count and finalized run file bytes; stream hashes.

## Constitution Check

Pre-design and post-design PASS: one outcome, Spec Kit, tests first, stdlib/Windows-safe, offline/no paid spend, source limitations preserved, no publication. Preserve unrelated work. No exceptions.

## Project Structure

- scripts/research_store.py: layout, safe paths, inventory, local index.
- scripts/research_session.py: integrate prepare/finalize/index; validate placement.
- scripts/output_paths.py: reject symlinked research roots.
- tests/test_research_store.py: storage and reuse tests.
- SKILL.md, references/goal-driven.md: placement and future-agent lookup.
- README, CONFIGURATION, CLAUDE, CHANGELOG: behavior and limits.
All scripts/tests/skill paths above are inside skills/deep-research/.

## Sequence

Tests → layout/inventory/index → session integration → skill/docs → checks → installed-copy refresh → one final adversarial diff review.

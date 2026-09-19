# Implementation Plan: Goal-driven research

**Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

## Summary

Keep the host agent as investigator. Add a deterministic session CLI for intake,
readiness, evidence validation and the final pair, plus targeted retrieval in
existing connectors. No new orchestrator, database or model service.

## Technical Context

Python 3 standard library, optional yt-dlp/media backends. Local JSON/Markdown,
self-contained HTML/CSS/JS. Unittest fixtures, isolated browser checks and a live
mixed-source test. Windows-safe. Automated tests never make paid vendor calls.

## Constitution Check

Evidence, freshness, failure states and citation references validated before export.
Paid discovery is separate from archive readers. Raw CLI stays compatible.
Live budget USD 1: conservative reservations, actual usage receipts, no paid retry.
Working-copy exception: feature 003 is implemented but uncommitted and main has
diverged. Preserve this user-supplied checkout. Main integration is a release
prerequisite; no release or installation claim is made for the candidate.

## Project Structure

- scripts/research_session.py: brief, readiness, dossier validator; prepare/status/finalize/example.
- scripts/playbook.py: escaped bilingual HTML, action sequence, evidence and print.
- scripts/connectors/reddit_research.py: Perplexity discovery plus targeted free
  Arctic Shift post-ID/comment reads and explicitly selected ScrapeCreators reader.
- scripts/connectors/youtube.py: bounded comments, bilingual captions, evidence JSON.
- scripts/deep-research.py: source registry, bounded Grok settings, dates and usage.
- skills/deep-research/SKILL.md + references/goal-driven.md: default user journey.
- tests/test_research_session.py, test_playbook.py, test_reddit_research.py and
  expanded YouTube/fire tests; README/CONFIGURATION/CHANGELOG/CLAUDE updates.

## Phases

1. Source research and contracts; validate task coverage.
2. Tests then session pair and source readers in independent files.
3. Integrate runner, skill and docs; realistic fresh-agent skill evaluation.
4. Live mixed-language investigation <= USD 1, real final pair and three-size visual QA.
5. Full unittest/selftest, one adversarial diff review, fix discovered defects.

## Complexity Tracking

Host composes queries and synthesizes; deterministic code enforces output contracts.
No second AI service and no universal crawler. Optional paid readers stay explicit.

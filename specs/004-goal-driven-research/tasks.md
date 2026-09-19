# Tasks: Goal-driven bilingual research

## Foundation

- [x] T001 Specify the three user stories and evidence contracts in `spec.md`, `plan.md`, `research.md`, `data-model.md`, and `contracts/session-cli.md`.
- [x] T002 Analyze requirements, task coverage, safety boundaries, and existing checkout compatibility before implementation (all FR001–FR010 and SC001–SC005 mapped below).

## US1 — Goal and readiness (P1)

- [x] T003 [US1] Write failing brief, readiness, path, and budget tests in `skills/deep-research/tests/test_research_session.py` (FR001, FR002, FR009).
- [x] T004 [US1] Implement prepare/status/example commands and bounded spending ledger in `skills/deep-research/scripts/research_session.py` (FR001, FR002, FR009; SC001).
- [x] T005 [US1] Route skill entry through goal intake and source connection guidance in `skills/deep-research/SKILL.md` and `references/goal-driven.md` (FR001, FR002; SC001).

## US2 — Read social evidence in both languages (P1)

- [x] T006 [P] [US2] Write fixtures and implement targeted Reddit posts/comments and Perplexity discovery in `scripts/connectors/reddit_research.py` and `tests/test_reddit_research.py` under `skills/deep-research` (FR003, FR006).
- [x] T007 [P] [US2] Extend `skills/deep-research/scripts/connectors/youtube.py` and `tests/test_youtube.py` for bounded comments, bilingual captions, and honest transcript/comment status (FR004, FR006).
- [x] T008 [US2] Integrate new sources, source metadata, current-date prompts, and actual-cost accounting in `skills/deep-research/scripts/deep-research.py` with focused tests (FR003, FR004, FR009, FR010).
- [x] T009 [US2] Specify seed-first, RU/EN, lead expansion, contradiction search, evidence dating and untrusted-source rules in `skills/deep-research/references/goal-driven.md` (FR004, FR005, FR006; SC002).

## US3 — Two usable artifacts (P1)

- [x] T010 [US3] Write failing dossier/reference/coverage/HTML safety tests in `skills/deep-research/tests/test_research_session.py` and `test_playbook.py` (FR007, FR008).
- [x] T011 [US3] Implement dossier validation and paired HTML/JSON export in `skills/deep-research/scripts/research_session.py` and `playbook.py` (FR007, FR008; SC003).
- [x] T012 [US3] Produce and inspect a real bounded research pair on desktop/tablet/mobile under `research/goal-driven-*` (SC003, SC004, SC005).

## Qualification and handoff

- [x] T013 Update `README.md`, `CONFIGURATION.md`, `CLAUDE.md`, `CHANGELOG.md` and feature quickstart for candidate behavior and limits (FR010).
- [x] T014 Evaluate skill intake on fresh independent prompts without paid source calls; fix observed routing gaps (SC001, SC002).
- [x] T015 Run focused tests, full unittest suite from `skills/deep-research`, and `bash scripts/selftest.sh`; perform one final adversarial diff review and resolve findings (FR010).
- [x] T016 Reconcile live test spending under the newly authorized $1, record actual versus estimated cost and unresolved source limitations, complete tasks only with evidence (FR009; SC004).

## Dependencies and parallel execution

T001–T002 precede implementation. US1 and the isolated source files in T006–T007 can proceed in parallel. Source worker owns only those connectors/tests; parent owns session, renderer, runner integration and docs. T010 precedes T011. T005/T009 integrate after the concrete CLI exists. T012 follows integration; T013–T016 close the same product outcome. No merge, publication, global plugin installation, or unrelated feature is included.

## Pre-implementation analysis

All ten functional requirements and five success criteria have explicit tasks. No unresolved requirement contradiction. The skill-host remains the reasoning loop; the CLI validates and preserves its evidence rather than claiming unattended model orchestration. Direct content and model summaries remain distinguishable. Two final documents do not prohibit internal evidence files. $1 is an explicit test ceiling, not permission for unknown recurring spend. Existing dirty changes are preserved; release alignment is separate.

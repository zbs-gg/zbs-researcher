# Qualification

From skills/deep-research, run focused session/playbook/Reddit/YouTube tests, then
full `python3 -m unittest discover -s tests` and `bash scripts/selftest.sh`.

Use `research_session.py example`, fill brief, prepare, retrieve selected sources,
fill dossier and finalize. Inspect playbook at desktop/tablet/mobile in headless
browser; exercise navigation, expandable source excerpts and print CSS. Validate agent references.

Live example: owner topic and supplied seeds if received; RU/EN discovery, targeted
Reddit post/comments, YouTube text/comments and native X under total USD 1.
Unavailable sources yield explicitly partial outputs. No superiority claim.

## Qualification result — 2026-09-05

Implemented in the existing dirty checkout without reverting the owner's
Monid/duel changes. `694` unittests passed; `bash scripts/selftest.sh` passed
10/10, including plugin validation and zero-key/legacy paths. No paid provider
calls in deterministic tests. `git diff --check` passed.

Live run (local, ignored evidence):
`research/deep-research-reddit-и-x-для-моделей-первый-эксперимент-2026-09-05/`.
Final `playbook.html` and `agent-context.json` share a validated dossier digest.
This is a deliberately partial research example, not a market-wide answer or
proof that Researcher beats a manual workflow.

- Read three Reddit posts (two EN, one RU), 37 archive comments, two full
  YouTube auto-transcripts (EN/RU) and 12 video comments. Comments are bounded;
  YouTube comment dates are marked approximate. Video screen content was not
  independently inspected.
- Two native xAI requests returned X search/tool traces. Their quotes remain
  model-reported; direct reading of the selected Russian X permalink failed.
  Four Sonar/OpenRouter calls supplied Reddit/web discovery. Three original web
  pages were opened for rules and a Russian promotional claim check.
- Exact provider-reported total: **USD 0.1352633** of the newly approved USD 1.
  Six explicit calls, no retries or paid fallbacks, all costs settled in
  `spending.json`. Prior unrelated Grok smoke is outside this new allowance.
  ScrapeCreators Reddit route was fixture-tested, not billed/live-qualified.
- Live discovery exposed a caption bug: failed Russian translation prevented
  downloading the available English original. One bounded original-track
  recovery now succeeds without repeating comments or enabling paid audio.
- Isolated fresh BB thread `thr_4f72e4ktgm` evaluated three intake prompts.
  It found competing legacy instructions; those moved into an optional
  reference. A follow-up regression confirmed the competing intake was gone.
  This is instruction/routing evaluation, not a blind answer-quality benchmark.
- Headless Chromium inspected at 1440×1000, 768×1024 and 390×844. Screenshots
  physically viewed; no horizontal overflow, no broken anchors; source details
  opened and agent JSON link worked. axe-core 4.12.1: zero violations. No user
  desktop control, hosting or publication. Isolated browser was closed.
- Final adversarial review found three bugs: parent post incorrectly satisfying
  a comment seed, short YouTube URL mismatch, and final output paths accepted as
  raw evidence. All fixed with focused regression tests. Bounds are also
  rejected outside direct Grok fire rather than silently ignored.

Operator/public docs were updated in the same work. No merge, version bump,
npm/marketplace publication or installed-plugin change. To use this candidate,
load the repository-local `skills/deep-research/SKILL.md`; the host agent owns
research reasoning and dossier synthesis, not a background service.

## Isolated installation follow-up — 2026-09-05

The owner requested preparation for installation and public demonstration.
This follow-up qualifies delivery; it does not authorize a version bump or
publication, and does not reclassify the earlier research as a blind E2E.

- Claude Code 2.1.260 installed the candidate from a local marketplace into
  a fresh temporary `CLAUDE_CONFIG_DIR`. The installed plugin was enabled,
  version 0.5.0, and its skill files matched the snapshot by checksum.
  The owner's normal installed plugin and settings were not changed.
- All 694 deterministic tests passed from the installed copy. The first
  reduced snapshot omitted the benchmark fixture and produced
  29 errors; a fresh installation of the complete snapshot resolved them.
- An additional installed-copy check disabled socket connections, used an
  empty secrets directory and a zero-dollar brief, observed `needs_connection`
  for Reddit/X, rejected a positive reservation, and exported a matching-digest
  HTML/JSON pair. Its content is explicitly synthetic, not research evidence.
- The installed self-test passed its unit suite but stopped in step 2 because
  the benchmark requires a repository Git SHA. An installed plugin cache has
  no Git history. Do not describe this installed run as self-test 10/10.
  The repository self-test subsequently passed all 10 steps, including all
  694 tests; `git diff --check` passed. No runtime code changed in this follow-up.
- The npm dry-run pack contained exactly README.md, bin/cli.js and package.json
  (4504 compressed bytes); the installer command dry-run executed nothing.
- Live `origin/main` still resolves to `561f6ed09867d1bfd6d790e60560c0c5f089c2a4`
  and carries version 0.6.0. The candidate remains 0.5.0 with divergent local
  work. Resolve the release base and approve a new version before publication;
  do not overwrite main with the older candidate metadata. An explicit plugin
  update also reported 0.5.0 already current despite changed local source files,
  so an unchanged version is not evidence of refreshed installed contents.
- Authentication in the fresh profile is absent (`loggedIn: false`). No
  credentials were copied, no model request was made, and no additional paid
  source calls ran. Full authenticated goal-to-artifacts E2E remains pending.

Next: authenticate the isolated profile, run a real zero-paid-source research
through the installed skill, inspect its transcript and paired artifacts, then
prepare the release version/base and a public example for explicit approval.
README and installer documentation were checked; their unreleased-candidate
boundary remains accurate, so no public availability claim was changed.

## Codex installation — 2026-09-05

The owner explicitly selected Codex and authorized use of the existing account.
Installed an independent copy of the current whole skill in the user skill
directory `~/.agents/skills/deep-research`, with no prior destination overwritten.
The published GitHub installer was not used because it would retrieve the old
release. Installed script/reference checksums matched the working skill.

Codex CLI 0.150.1 reports ChatGPT authentication. The first isolated invocation
ignored user configuration and consequently missed the configured keyring;
it failed with unauthenticated HTTP 401 before research began. Preserving
`cli_auth_credentials_store="keyring"` in the next invocation restored the
existing sign-in without copying credentials or asking for another login.
User configuration files were not edited; no API-key billing fallback was used.

The fresh session discovered and read the installed skill and its goal-driven
reference, wrote its own brief and prepared one run in a clean temporary project.
Its task requires RU/EN Reddit, YouTube and web evidence, starts with one supplied
video, and prohibits paid source calls, private memory and old research reports.
Evidence is retained locally under `research/codex-installed-e2e-20260905/`.
The host consumes the existing account allowance, distinct from the external
source budget of USD 0. Full-run completion is recorded below only after export.

README, CONFIGURATION and CLAUDE now document the local Codex route and its
authentication/usage boundaries. Repository self-test passed 10/10, including
694 deterministic tests, after those documentation changes.

### Completed Codex run

The authenticated session completed without a restart or parent-authored dossier.
It read the full supplied English YouTube transcript and available comments,
used host web search/read for Reddit and primary web pages, authored its own
dossier, and successfully called the installed `finalize`. The long synthesis
pause did not turn out to be a process failure. The entire run took about eleven
minutes. CLI usage reported 1,544,436 input tokens (1,421,056 cached) and 31,177
output tokens; these are host usage counters, not a dollar invoice.

The untouched exported pair and raw evidence were copied into the durable local
`research/codex-installed-e2e-20260905/result/` folder. It contains ten evidence
records, five claims and one experimental action, with overall `partial` status.
Both files have the same dossier digest; all referenced raw paths exist.
The spending ledger has a USD 0 ceiling and an empty call list. The transcript
shows one free `youtube-social` call and native host web calls, with no paid
research connector or old-report/private-memory access.

This is a successful bounded goal-to-artifacts execution, not full bilingual
platform qualification: the Russian Reddit source is adjacent artist evidence;
Russian YouTube/web evidence is absent; comments are incomplete; X was outside
this test. Source excerpts in the final pair include synthesized summaries, so
the existence of an evidence record is not a claim of preserved verbatim text.
The parent checked selected original pages, not every date or interpretation.

The child could not obtain Chromium screenshots and honestly reported that gap.
The parent then inspected the unchanged HTML in a separate headless browser at
1440×1000, 390×844 and 768×1024, physically viewed the screenshots, checked no
horizontal overflow or broken internal anchors, and opened a source disclosure.
axe-core 4.12.1 reported zero violations. The browser was closed afterward; no
desktop control, hosting or publication occurred.

Final scoped review found no installation/authentication blocker. It retained
the partial-coverage and local-candidate labels; no runtime/skill source change,
version bump, merge or publication was needed for this Codex installation.

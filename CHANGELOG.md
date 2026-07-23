# Changelog

## 0.4.0 — 2026-07-23

Two new deep-research modes alongside the default broad-scan `single` mode — the
edge is QUALITY: native, full-breadth social/community depth, not price.

- **`--mode entity-fanout`** — real deep research instead of one blanket query
  per channel: enumerate the top-N entities for a topic (GitHub top-by-stars +
  HN mentions, per-source degrade; an LLM lens enriches / is required for
  non-repo topics), then fan out **per entity** across the channels into an
  entity×channel dossier matrix. Hybrid tiering: free channels on all N
  entities, paid LLM lenses on the top-K only (`--paid-all` lifts + raises the
  budget). Bounded `ThreadPoolExecutor` concurrency, per-host reddit/bluesky
  backoff, per-cell `ERROR.md` degrade, and an honest cost/time manifest with a
  `degraded` flag — never "$0 / 40s". `--dry-run` previews the entity list +
  call budget for free.
- **`--mode investigate`** — the flagship: a session-driven, question-driven
  agentic loop. Compose short, target-scoped queries per source (never a
  blanket sentence), `--fire <source>` one at a time, read + drill adaptively,
  then synthesize a problems-first landscape report with a real quote + author
  handle + clickable live link behind every load-bearing claim. Reads the
  platforms from inside (live X via Grok, Telegram client-session, the full
  Reddit archive) where a web-index researcher sees only the indexed scraps.
- **Coverage-receipts** (`--coverage RUN_DIR`) mark, from real provenance,
  what a web-index researcher would miss (Telegram with no web footprint,
  fresh pre-index X, deep Reddit archive) — truthful, never inferred.
- **Compound feedback loop**: `--feedback` saves your notes + composed queries
  to a local ledger the next run reads (honest — a save, not learning), with an
  opt-in Cartographer relay (`DEEP_RESEARCH_CARTOGRAPHER_URL`, https-only,
  failure-tolerant) for cross-run profile compounding.
- **Eval harness** (`eval_harness.py`) — head-to-head on your own data: Beast
  vs a free web-index `site:` baseline, scored on primary-source depth,
  freshness, and social-coverage.
- Positioning is quality: "free / cheaper" is a property, not the pitch.

## 0.3.0 — 2026-07-21

ZBS Researcher: persona, CLI polish, npx installer, showcase.

- **ZBS Researcher persona** (brand-only — plugin id stays
  `deep-research`): the wizard introduces itself by name and asks at most two
  persona questions (gender of address + tone preset), both skippable, only
  after the $0 Tier-0 proof. Choice persists in `onboarding.json` as a
  `persona` object; voicing rules pin that tone changes intonation and
  sign-off only — never findings, rankings, or honesty notes.
- **`term_ui` banner + live progress board** in the runner CLI: ASCII banner
  and an animated per-connector board (spinner, status, elapsed) — rendered
  ONLY in a real TTY. Non-TTY / `NO_COLOR` / `CI` / `TERM=dumb` output stays
  byte-compatible with the previous plain per-channel lines.
- **npx installer** `zbs-researcher`: one command
  (`npx -y zbs-researcher@latest`) detects the `claude` CLI, adds the
  marketplace, installs the plugin, and prints next steps. Prepared here;
  npm publication is a separate manual action.
- **Marketplace renamed** `deep-research-skill` → `zbs-researcher` (plugin id
  unchanged). Migration: installs registered under the old marketplace name
  should re-add it as `zbs-gg/zbs-researcher`.
- **Showcase docs**: README showcase top, `docs/demo-script.md` (demo-video
  shot list), `docs/site-brief.md` (hand-off brief for an external site
  effort).

## 0.2.0 — 2026-07-15

Unreleased package update for project-local research ownership.

- Skill runs now reserve one unique
  `<project>/research/deep-research-{slug}-{date}[-NN]/` directory and write
  `research-plan.md` before starting connectors.
- Raw reports, `manifest.json`, session-authored `synthesis.md`, and optional
  `brief.html` are colocated with the plan instead of using detached global
  defaults.
- Direct CLI runs allocate project-local raw-evidence bundles by default;
  `--project-root` narrows monorepo ownership and explicit `--output-dir`
  destinations remain supported.
- Probe and render-only operations remain read-only with respect to run
  allocation, and deterministic path/documentation/version checks now run in
  the no-paid-API selftest.
- Ambiguous or malformed legacy CLI shapes now fail before allocation:
  positional topic plus `--topic`, `--only` plus `--skip`, unknown connector
  names, malformed `--q`, blank explicit paths, `--html-out` without render,
  and `--allocate-run` combined with raw-run options. Use one topic form, one
  connector selector, non-blank paths, and a separate allocation call.
- Skill commands resolve the runner from the host-discovered `SKILL.md`
  directory, so Codex does not depend on Claude's `CLAUDE_PLUGIN_ROOT`.
- Skill allocation now stamps `_topic.txt`; the subsequent connector call uses
  `--prepared-run` to require that exact topic, a non-empty plan, and no prior
  raw artifacts, then atomically claims the directory against concurrent or
  stale reuse. Reusing plain `--output-dir` remains an explicit low-level
  compatibility behavior.
- Skill commands also pass the captured directory through `--launch-cwd`, so
  ownership does not change if an agent's process cwd drifts between tool calls.

## 0.1.0 — 2026-07-08

Initial plugin packaging of the deep-research skill.

- **10 connectors**: gemini, grok, perplexity, openai *(opt-in)* + hackernews,
  hiring, polymarket, github, reddit, bluesky.
- **Plan-first STEP 0** — a research plan (topic resolution, channel choice,
  per-channel queries, expected contradictions) precedes every run.
- **No Anthropic/OpenAI API spend by default** — retrieval on Gemini/Grok/
  Perplexity + free direct connectors; synthesis in the Claude Code session;
  `openai` channel is opt-in.
- **Hiring-signal connector** — counts "Who is hiring?" postings mentioning a
  topic (job-market hotness) with sample companies.
- **Polymarket** via `/public-search` (real text search, not top-100 by volume).
- **Self-contained HTML brief** renderer (`--render-html`), no external deps.
- Per-run `manifest.json`; each channel degrades to `ERROR.md` on failure
  without killing siblings.
- `${CLAUDE_PLUGIN_ROOT}` paths and `DEEP_RESEARCH_SECRETS_DIR` override for
  portability; env-var keys supported as a fallback to secret files.

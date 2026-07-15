# Changelog

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

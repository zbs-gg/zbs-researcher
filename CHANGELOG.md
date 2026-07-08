# Changelog

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

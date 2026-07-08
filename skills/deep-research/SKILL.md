---
name: deep-research
description: Parallel multi-channel deep research — LLM lenses (Gemini/Grok/Perplexity; OpenAI opt-in) + direct connectors (HN, Hiring-signal, Polymarket, GitHub, Reddit, Bluesky) + Claude synthesis. ALWAYS produce a research plan first, then run. By default it does NOT bill Anthropic/OpenAI APIs. Use for any topic that needs multi-source diligence — tech investigation, comparative analysis, scientific landscape, real user voices vs marketing, hiring-market hotness, contradictions between sources. NOT for one-off fact-checks.
---

# Deep Research — plan first, then multi-channel pull + synthesis

Use when normal web search isn't enough — you need to *triangulate*
across very different source types (reasoning-model lenses **and** raw
platform signal) and surface contradictions, not just retrieve the
top-ranked summary.

## STEP 0 — RESEARCH PLAN (mandatory, before any run)

**Never fire the script cold.** Every invocation starts with a short
research plan shown to Nik, then the run. This is the rule Nik set on
2026-07-08: *"когда вызываешь ресёрч — сначала план ресёрча, потом запуск."*

1. **Check what's live** — run the connector probe so the plan is built on
   reality, not assumptions:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/deep-research/scripts/deep-research.py" --list-connectors
   ```
2. **Resolve the topic** (this is where the quality comes from — borrowed
   from last30days' pre-research idea). Don't search raw keywords; first
   name the concrete entities:
   - people → exact @handles (X/GitHub/Bluesky)
   - communities → exact subreddits (r/…), HN, specific orgs
   - repos → `owner/name`
   - is this a **forecastable event**? → Polymarket is worth including
   - is this a **skills/tech-trend** question? → the **hiring** channel shows
     whether the job market is heating up on it (resolve the query to 1–2
     sharp terms, e.g. `RAG`, `context engineering`, not a long phrase)
3. **Pick channels + aim each one.** Decide which of the 9 connectors run
   and *why each* — which channel covers which facet. Write a per-channel
   query where the default topic string isn't the sharpest aim.
4. **Name the contradictions you expect to test** — the value of the run is
   in the disagreements, so say up front what tension you're probing.

Show this as a compact plan (topic resolution · channels + rationale ·
per-channel queries · expected contradictions). Then run. For anything
non-trivial also drop a copy under `~/elle/plans/` per the plan-first rule.

## Budget rule — no Anthropic / OpenAI API by default

Nik's rule (2026-07-08): **don't burn Anthropic or OpenAI API keys.** So:

- The script's **default run bills neither**. Web/social retrieval is covered
  by **Gemini (Google)**, **Grok (xAI)**, **Perplexity** — separate, cheap
  keys Nik opted into — plus the free direct connectors.
- The **openai** channel is **OFF by default** (opt-in via `--only openai`);
  it bills the OpenAI API per token. Only enable it on Nik's explicit OK.
- **Synthesis** happens in *this Claude Code session* (flat-rate), not via the
  Anthropic API — the script never calls `api.anthropic.com`.
- If you genuinely want a GPT lens without per-token spend, run it **through
  Codex** (flat subscription) interactively — not from this script.

## Architecture — 10 connectors

**LLM channels** (need an API key; each is a reasoning model with its own
live web access):

| Channel | Source | Why this model | Default |
|---|---|---|---|
| **gemini** (2.5 Pro) | YouTube + web (googleSearch grounding) | Reads videos by URL; strong on talks, lectures, tutorials | on |
| **grok** (4.20-reasoning) | X / Twitter (`x_search`) | Only model with realtime X — fresh threads, complaints, edge cases | on |
| **perplexity** (Sonar) | web + news, citation-first | Web/social lens; forces per-claim attribution | on |
| **openai** (gpt-5.4 non-Pro) | Reddit + HN + GitHub + blogs (`web_search`) | GPT lens; **bills OpenAI API** | **opt-in** |

**Direct channels** (zero-config, free; STRUCTURAL signal an LLM won't hand
you — raw numbers, odds, velocity):

| Channel | Source | Gives you |
|---|---|---|
| **hackernews** | HN Algolia | stories ranked by points/comments |
| **hiring** | HN "Who is hiring?" | job-market hotness — how many postings mention the topic + which companies (RAG/agents/context-eng spikes) |
| **polymarket** | Gamma `/public-search` | real-money odds on the topic (implied %) |
| **github** | repo + issue search (`gh`) | stars, push recency, top issues/PRs |
| **reddit** | search.json | top posts by upvotes *(best-effort — Reddit throttles unauth JSON; degrades to ERROR.md)* |
| **bluesky** | app.bsky searchPosts | top posts *(best-effort)* |

**Claude (this session)** — synthesis: reads the report files, writes
`synthesis.md` (overlaps, contradictions, one-screen recommendation), then
optionally renders a shareable `brief.html`.

## When to use

- **Tech investigation** — why a library/approach fails on real edge cases.
- **Comparative analysis** through user voice, not press releases.
- **Scientific landscape** — community reception of a method, not just paper 1.
- **Decision diligence** — before sinking time into a stack: failure-mode distribution.
- **Contradiction surfacing** — one polished narrative dominates and you suspect it's incomplete.
- **Forecastable events** — releases, elections, launches → Polymarket odds add a money-weighted signal.

## When NOT to use

- Simple fact-check — `WebSearch` is faster and cheaper.
- Pure academic lit review — Scholar/arXiv/Semantic Scholar are better primaries.
- Internal codes / private APIs — not in public sources.

## How to run

```bash
# discover live connectors (the plan step)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/deep-research/scripts/deep-research.py" --list-connectors

# default = every available connector, in parallel
python3 "${CLAUDE_PLUGIN_ROOT}/skills/deep-research/scripts/deep-research.py" "TOPIC" \
    --output-dir ~/research/deep-research-{slug}-{date}

# scope the channels
… "TOPIC" --output-dir DIR --only gemini,perplexity,hackernews,polymarket
… "TOPIC" --output-dir DIR --skip reddit,bluesky

# hiring-market hotness for a skill/tech (free): how many postings mention it + who
… "context engineering" --output-dir DIR --only hiring
# GPT lens (OPT-IN — bills OpenAI API, only on Nik's OK)
… "TOPIC" --output-dir DIR --only openai

# aim each channel (repeatable --q name:query; legacy --gemini-q/--grok-q/--openai-q still work)
… --topic "long-context memory failure modes" --output-dir DIR \
    --q gemini:"YouTube talks 2026 on long-context retrieval failures" \
    --q grok:"X threads long context degradation real reports" \
    --q openai:"Reddit/HN/GitHub issues long-context memory bugs LangChain LlamaIndex"

# after writing synthesis.md, render a shareable HTML brief
… --render-html DIR/synthesis.md --html-out DIR/brief.html
```

`--max-items N` controls items per direct channel (default 10).

## Output layout

```
research/deep-research-{slug}-{date}/
├── _topic.txt            — what was asked
├── manifest.json         — what ran / was skipped / errored, timings
├── gemini-youtube.md     — Gemini findings
├── grok-x.md             — Grok findings (X)
├── openai-social.md      — OpenAI findings (only if opt-in)
├── perplexity-web.md     — Perplexity findings (web/news, cited)
├── hackernews.md         — HN stories by points
├── hiring.md             — HN Who-is-hiring postings mentioning the topic
├── polymarket.md         — market odds (or honest "no markets")
├── github.md             — top repos + recent issues
├── reddit.md             — top posts (or ERROR.md)
├── bluesky.md            — top posts (or ERROR.md)
├── synthesis.md          — Claude: overlaps, contradictions, recommendation
└── brief.html            — optional shareable dark-mode HTML (self-contained)
```

## Tech detail

- Channels run in parallel via threading; ~3–7 min wall-clock (LLM channels dominate; direct channels finish in <2s).
- Keys read from `~/.openclaw/secrets/{gemini-key,grok-api-key,openai-api-key,perplexity-key}.txt` (or env `GEMINI_API_KEY`, `GROK_API_KEY`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`). The openai-key read is name-tolerant (`openai-api-key.txt` / `openai-key.txt` / `openai.txt`).
- OpenAI channel (**opt-in only**) uses gpt-5.4 (non-Pro) via `api.openai.com/v1/responses`. It bills the OpenAI API, so it is not in the default set — enable with `--only openai` on Nik's OK. Pro models are never used; that spend is reserved for `emergency-pro`.
- Perplexity uses `sonar` (env `PERPLEXITY_RESEARCH_MODEL` to override).
- If a channel fails (quota, network, key, throttle) it writes `<name>.ERROR.md` and records the error in `manifest.json`; other channels continue.
- Direct channels are free and need no key. `github` prefers authed `gh` (higher rate limit), falls back to unauthenticated API.
- HTML brief renders with a built-in mini markdown→HTML converter (no external deps); output is fully self-contained (inline CSS, system-font fallbacks behind Inter/JetBrains Mono) — safe to hand to Nik or share.

## Limits

- **Gemini** grounding sometimes returns plain web, not YouTube. For strictly YouTube, append `site:youtube.com`.
- **Grok** X search caps ~25 posts/query — reformulate for deeper passes.
- **OpenAI/Perplexity** sometimes miss small niche communities — enumerate exact subreddits/orgs/domains in the query.
- **Polymarket** only fires for forecastable topics; honest "no markets matched" otherwise (uses real `/public-search`, not top-100-by-volume).
- **Reddit / Bluesky** are best-effort — Reddit throttles unauthenticated JSON and may degrade to ERROR.md; that's expected, the LLM channels cover the same ground.
- Synthesis quality depends on the reports — if all agree, the value is noticing it; if they disagree, the value is naming *why*.

## Cost note

- Default run: Gemini + Grok + Perplexity (cheap, cents to ~$1 by depth) + free direct channels. **No Anthropic/OpenAI API spend.**
- openai channel is opt-in and bills OpenAI per token — off unless Nik says so.
- Pro reasoning is not needed for retrieval+synthesis; escalate to `emergency-pro` only on Nik's explicit OK. For a GPT opinion at flat cost, use Codex interactively.

## Adding more connectors

- TikTok / Instagram transcripts need a ScrapeCreators key → drop it in
  `~/.openclaw/secrets/scrapecreators-key.txt` (or `SCRAPECREATORS_KEY`) and
  add a `direct` connector in the registry.
- Brave Search → `~/.openclaw/secrets/brave-key.txt` (or `BRAVE_API_KEY`).
- Each new connector: add one `channel_*` function + a `Connector(...)` line
  in the registry + an entry in `OUTPUT_NAMES`. The runner, `--only/--skip`,
  `--list-connectors`, and manifest pick it up automatically.

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

**Never fire the connectors cold.** Every skill invocation creates one
self-contained bundle in the project from which the skill was launched. The
meaningful research plan must exist inside that bundle before connector work
starts. This is the rule Nik set on 2026-07-08: *"когда вызываешь ресёрч —
сначала план ресёрча, потом запуск."*

1. **Capture the launch directory before resolving plugin paths**, then probe
   the live connectors from that directory. Never `cd` into the plugin and
   accidentally make it the research owner. Resolve `SKILL_DIR` from the
   absolute directory containing the **loaded** `SKILL.md`; this path is
   supplied during skill discovery on Codex and other hosts. Do not assume
   `CLAUDE_PLUGIN_ROOT` exists, and never execute the placeholder below—replace
   it with the discovered absolute directory in every shell call:
   ```bash
   LAUNCH_CWD="$(pwd -P)"
   SKILL_DIR="<absolute directory containing the loaded SKILL.md>"
   SCRIPT="$SKILL_DIR/scripts/deep-research.py"
   test -f "$SCRIPT"
   printf 'launch_cwd=%s\n' "$LAUNCH_CWD"
   (cd "$LAUNCH_CWD" && python3 "$SCRIPT" --list-connectors \
       --launch-cwd "$LAUNCH_CWD")
   ```
   Record the printed absolute path. Shell variables may not survive between
   tool calls, so later calls must reassign `LAUNCH_CWD` to this captured
   literal; do not recalculate it after visiting another directory.
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
3. **Pick channels + aim each one.** Decide which of the 10 connectors run
   and *why each* — which channel covers which facet. Write a per-channel
   query where the default topic string isn't the sharpest aim.
4. **Name the contradictions you expect to test** — the value of the run is
   in the disagreements, so say up front what tension you're probing.
5. **Show the compact plan**, then reserve exactly one run directory through
   the runner. Use the resolved topic, not an unexpanded placeholder:
   ```bash
   LAUNCH_CWD="/absolute/path/printed-in-step-1"
   SKILL_DIR="/absolute/directory/containing/the/loaded/SKILL.md"
   SCRIPT="$SKILL_DIR/scripts/deep-research.py"
   TOPIC="RESOLVED TOPIC"
   RUN_DIR="$(cd "$LAUNCH_CWD" && python3 "$SCRIPT" "$TOPIC" \
       --allocate-run --launch-cwd "$LAUNCH_CWD")"
   printf 'run_dir=%s\n' "$RUN_DIR"
   ```
   The default owner is the launch directory's Git top-level, or the captured
   launch directory outside Git. If a monorepo's Git root is broader than the
   actual project, pass the intended owner explicitly during allocation:
   ```bash
   LAUNCH_CWD="/absolute/path/printed-in-step-1"
   SKILL_DIR="/absolute/directory/containing/the/loaded/SKILL.md"
   SCRIPT="$SKILL_DIR/scripts/deep-research.py"
   TOPIC="RESOLVED TOPIC"
   PROJECT_ROOT="/absolute/path/to/intended/project"
   RUN_DIR="$(cd "$LAUNCH_CWD" && python3 "$SCRIPT" "$TOPIC" \
       --allocate-run --launch-cwd "$LAUNCH_CWD" \
       --project-root "$PROJECT_ROOT")"
   printf 'run_dir=%s\n' "$RUN_DIR"
   ```
   Allocation writes only `_topic.txt`, which binds the reservation to the
   exact topic. It does not start connectors.
6. **Write `research-plan.md` inside the absolute run path printed in step 5
   before starting connectors.** Use the normal file-writing tool, not a
   placeholder shell echo. The plan must name the resolved topic/entities,
   research questions and scope, selected channels with rationale, exact
   per-channel queries, expected contradictions, and what evidence would
   answer the request. Record the captured launch directory and any explicit
   project-root choice.
7. **Run connectors into that exact directory.** Do not allocate a second run
   and do not derive a path independently:
   ```bash
   LAUNCH_CWD="/absolute/path/printed-in-step-1"
   SKILL_DIR="/absolute/directory/containing/the/loaded/SKILL.md"
   SCRIPT="$SKILL_DIR/scripts/deep-research.py"
   TOPIC="RESOLVED TOPIC"
   RUN_DIR="/absolute/path/printed-in-step-5"
   (cd "$LAUNCH_CWD" && python3 "$SCRIPT" "$TOPIC" \
       --launch-cwd "$LAUNCH_CWD" --output-dir "$RUN_DIR" --prepared-run)
   ```
   Add `--only`, `--skip`, and repeated `--q name:query` options from the
   written plan. Afterward, read the reports and write `synthesis.md` beside
   `research-plan.md`; if a brief is useful, render it there too:
   ```bash
   SKILL_DIR="/absolute/directory/containing/the/loaded/SKILL.md"
   SCRIPT="$SKILL_DIR/scripts/deep-research.py"
   RUN_DIR="/absolute/path/printed-in-step-5"
   python3 "$SCRIPT" --render-html "$RUN_DIR/synthesis.md" \
       --html-out "$RUN_DIR/brief.html"
   ```

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

The complete workflow is the skill orchestration in STEP 0: allocation,
`research-plan.md`, raw channel evidence, session-authored `synthesis.md`, and
optional `brief.html` all share one directory.

The Python command is also available as a **low-level raw-evidence runner**.
A direct topic run does not author `research-plan.md`, `synthesis.md`, or
`brief.html`; the calling agent or person owns those higher-level artifacts.
Plain `--output-dir` remains an intentionally permissive raw-run override.
Skill orchestration must add `--prepared-run`, which verifies the exact topic
reservation, a non-empty `research-plan.md`, and the absence of prior raw
artifacts, then atomically claims the run before writing. A crashed claim stays
fail-closed; deliberate recovery uses the low-level override after inspection.

```bash
SKILL_DIR="/absolute/directory/containing/the/loaded/SKILL.md"
SCRIPT="$SKILL_DIR/scripts/deep-research.py"

# discover live connectors without creating a run
python3 "$SCRIPT" --list-connectors

# direct default: raw evidence in a unique project-local research run
python3 "$SCRIPT" "TOPIC" --only gemini,perplexity,hackernews,polymarket

# narrow ownership below a broader Git root (for example, a monorepo package)
python3 "$SCRIPT" "TOPIC" --project-root /absolute/path/to/project --only hiring

# explicit raw-output override: bypasses project-root resolution and allocation
python3 "$SCRIPT" "TOPIC" --output-dir ./scratch/research-run --skip reddit,bluesky

# aim each channel (repeatable --q name:query)
python3 "$SCRIPT" --topic "long-context memory failure modes" \
    --q gemini:"YouTube talks 2026 on long-context retrieval failures" \
    --q grok:"X threads long context degradation real reports"

# render an existing synthesis beside its markdown input by default
python3 "$SCRIPT" --render-html ./research/existing-run/synthesis.md

# GPT lens (OPT-IN — bills OpenAI API, only on Nik's OK)
python3 "$SCRIPT" "TOPIC" --output-dir ./scratch/openai-run --only openai
```

`--max-items N` controls items per direct channel (default 10).

## Output layout

A **complete skill-authored bundle** is self-contained:

```
<project>/research/deep-research-{slug}-{date}[-NN]/
├── research-plan.md      — resolved scope, channel aims, contradictions
├── _topic.txt            — what was asked
├── .raw-run.claim        — hidden atomic single-writer marker
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
├── synthesis.md          — session: overlaps, contradictions, recommendation
└── brief.html            — optional shareable dark-mode HTML (self-contained)
```

A direct raw-runner invocation creates the unique project-local directory and
writes only `_topic.txt`, `manifest.json`, and the selected channel files. An
explicit `--output-dir` keeps intentional standalone output wherever the
caller requested it. Probe and render-only modes allocate no research run.

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

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
starts. The rule is: *"when you invoke research — the research plan first,
then the run."*

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
3. **Pick channels + aim each one.** Decide which of the 17 connectors run
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

Budget rule: **don't burn Anthropic or OpenAI API keys.** So:

- The script's **default run bills neither**. Web/social retrieval is covered
  by **Gemini (Google)**, **Grok (xAI)**, **Perplexity** — separate, cheap
  keys you opted into — plus the free direct connectors.
- The **openai** channel is **OFF by default** (opt-in via `--only openai`);
  it bills the OpenAI API per token. Only enable it on your explicit OK.
- **Synthesis** happens in *this Claude Code session* (flat-rate), not via the
  Anthropic API — the script never calls `api.anthropic.com`.
- If you genuinely want a GPT lens without per-token spend, run it **through
  Codex** (flat subscription) interactively — not from this script.

## Architecture — 17 connectors

**LLM channels** (need an API key; each is a reasoning model with its own
live web access):

| Channel | Source | Why this model | Default |
|---|---|---|---|
| **gemini** (2.5 Pro) | YouTube + web (googleSearch grounding) | Reads videos by URL; strong on talks, lectures, tutorials | on |
| **grok** (4.20-reasoning) | X / Twitter (`x_search`) | Only model with realtime X — fresh threads, complaints, edge cases | on |
| **perplexity** (Sonar) | web + news, citation-first | Web/social lens; forces per-claim attribution | on |
| **openai** (gpt-5.4 non-Pro) | Reddit + HN + GitHub + blogs (`web_search`) | GPT lens; **bills OpenAI API** | **opt-in** |

**Direct channels** (STRUCTURAL signal an LLM won't hand you — raw numbers,
odds, velocity; free and zero-config except the last three gated ones):

| Channel | Source | Gives you |
|---|---|---|
| **hackernews** | HN Algolia | stories ranked by points/comments |
| **hiring** | HN "Who is hiring?" | job-market hotness — how many postings mention the topic + which companies (RAG/agents/context-eng spikes) |
| **polymarket** | Gamma `/public-search` | real-money odds on the topic (implied %) |
| **github** | repo search (`gh`) | stars, push recency |
| **github-issues** | issue + comment search (`gh`) | top issues by reactions + real comment excerpts — product/competitor evidence; `owner/repo` query scopes to one repo |
| **reddit** | Arctic-Shift archive (free) | reaction-weighted posts — real score+comments, relevance-ranked *(search.json is dead; degrades to ERROR.md)* |
| **bluesky** | app.bsky searchPosts | top posts *(best-effort)* |
| **launch-radar** | Show HN + yc-oss + DevHunt (+Product Hunt with free read token) | what's shipping — momentum-ranked launches (votes × recency decay × comments) + category velocity (saturation signal); YC entries are recency-only (no vote fields) |
| **revenue-radar** | Flippa sold listings + Substack leaderboards (free) | what's selling — realized sale prices with profit multiples (Flippa→microsaas) + bestseller tiers verbatim, never invented revenue (Substack→infoproducts) |
| **meta-ads** | Meta Ad Library, EU scope (free token; auto-skipped without one) | who's PAYING to advertise the topic — active ads, advertisers, durations |
| **telegram** *(opt-in, off by default)* | Telegram client session (Telethon; separate research account only, ack-gated) | channel posts + discussion comments — views, reactions, real subscriber voice |
| **tiktok-ig** *(opt-in, off by default)* | pay-per-use vendor (ScrapeCreators or Apify) | TikTok/IG posts + comments — every run costs vendor credits, the report says so |
| **threads** *(key-gated)* | official Threads keyword_search (free token) or ScrapeCreators (pay-per-use) | Threads posts by keyword — official path keeps Meta's TOP order (no engagement counts; Standard Access = own posts only until App Review); vendor path adds like/reply counts, 1 credit/request |

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

## Two modes — broad-scan (default) vs entity fan-out

The runner has two modes, chosen with `--mode`:

- **`single`** (default) — one blanket query per channel (`"LLM agent memory"`
  → one Grok blob, one Gemini blob, one Reddit blob…). Fast, cheap, broad. This
  is the STEP 0 workflow above and is unchanged.
- **`entity-fanout`** — actual deep research. It (1) **enumerates the top-N
  entities** for the topic (GitHub top-repos-by-stars + HN mentions, free; an
  LLM lens enriches and is *required* for product/people-shaped topics that have
  no ranking repo), then (2) **fans out per entity** — every entity gets its own
  query in each channel, then (3) **aggregates an entity × channel dossier
  matrix**, and you (4) **synthesize the landscape** from the dossiers.

  **Hybrid tiering (the default):** the free channels (hackernews, github-issues,
  reddit, bluesky) run on **all N** entities; the paid LLM lenses (grok, gemini,
  perplexity) run on the **top-K** only. `--paid-all` lifts lenses to all N.

  ```bash
  # preview the entity list + exact call budget, no fan-out, no paid calls
  python3 "$SCRIPT" "TOPIC" --mode entity-fanout --entities-n 50 --dry-run

  # full run (free channels on all N; paid lenses on top-K, budget-capped)
  python3 "$SCRIPT" "TOPIC" --mode entity-fanout --entities-n 50 --top-k 10
  ```

  Flags: `--entities-n N` (default 50, cap 200), `--top-k K` (default 10),
  `--concurrency C` (default 6, cap 16), `--paid-budget B` (default K × available
  lenses), `--paid-all`, `--dry-run`.

  **Self-allocated plan-first (different from single mode).** entity-fanout owns
  its run: it self-allocates the run directory and writes `research-plan.md`
  (the enumerated entity list + the computed call budget) *before* firing any
  cell — it does **not** use the agent-driven `--allocate-run` / `--prepared-run`
  handshake that STEP 0 uses for single mode. Artifacts:
  `research-plan.md`, `entities/<entity-slug>/<channel>.md` (per cell; a failed
  cell degrades to `<channel>.ERROR.md`), `matrix.json`, `manifest.json`,
  `brief.html`. Then read the matrix and write `synthesis.md`.

  **Honest cost/time (not $0 / 40s).** Fan-out over 50 entities is minutes of
  wall time; the top-K paid lenses cost real vendor tokens. The manifest records
  real paid-call count, token usage (real vendor `usage` when available, else a
  labeled size-based estimate), and wall time — and flags the run `degraded` when
  a free channel was mostly rate-limited, so a hollow matrix is never sold as
  complete. Zero paid keys still yields a real matrix from GitHub + HN
  enumeration + free-channel fan-out (repo-shaped topics).

## Onboarding (first run) — the wizard IS the conversation

There is no separate setup screen. The wizard is this dialogue, run once,
and every upgrade must be earned by a real result shown first.

**STEP 0 — read detected state.** A SessionStart hook (wired in the plugin
root's `hooks/hooks.json`) injects JSON produced by `scripts/detect_state.py`:
`{providers: {gemini, grok, perplexity, openrouter, scrapecreators, groq,
threads}, telegram_session, profile, wizard_done, tier, persona}`. If no hook context is present
(Codex, Cursor, and other hosts without plugin hooks), run the detector
yourself and parse its JSON — detection must be host-portable, not just the
dialogue:
```bash
SKILL_DIR="/absolute/directory/containing/the/loaded/SKILL.md"
python3 "$SKILL_DIR/scripts/detect_state.py"
```
If `wizard_done` is true → **skip onboarding entirely** (no repeat pitch,
ever) and proceed with normal skill use.

**STEP 1 — first question with the welcome INSIDE it.** Never send a
standalone welcome message. Ask exactly one question whose text embeds the
persona pitch (default English):
- "Hi — I'm **ZBS Researcher**. I run deep multi-source research with
  live people's reactions: HN, Reddit, Threads, GitHub, Polymarket and a
  dozen more channels. $0 and zero keys to get started."

The options remain the only decision (still exactly ONE question). Use
AskUserQuestion (modal) where available; the prose fallback below otherwise:
- **Auto** — run the $0 proof right now.
- **Manual** — let the user choose sources first, then run.
- **Skip** — skip onboarding; write the STEP-4 marker with the current tier
  (persona defaults apply: `neutral` / `business`) and never pitch again.

**STEP 2 — Tier-0 proof BEFORE any key ask.** Run the free connectors only —
`--only hackernews,hiring,polymarket,github,github-issues,reddit,bluesky` — on a topic the
user gives (or offer one concrete demo topic). Use the normal STEP 0 flow
above: allocate the run, write `research-plan.md`, run, then show the brief.
**No paid-key prompt may appear before this real result exists.**

After showing the brief, add ONE line offering the live board: the
agent-mediated run above prints plain per-channel lines by design — the
animated progress board renders only in a real terminal. Say "want to watch
the run live with the animation — run this in your own terminal" and
hand over the copyable command (substitute the discovered absolute skill
path for `$SKILL_DIR` so it pastes verbatim):
```bash
python3 "$SKILL_DIR/scripts/deep-research.py" "<topic>" \
    --only hackernews,hiring,polymarket,github,github-issues,reddit,bluesky
```

**STEP 2.5 — persona tuning (max two questions, one ask).** Runs only AFTER
the Tier-0 brief exists — never before or instead of the $0 proof. Send ONE
AskUserQuestion carrying BOTH questions below (multi-question form); prose
fallback otherwise. If the user skips or doesn't care, apply defaults
silently — gender `neutral`, tone `business` — and move on. Persist the
answers in the STEP-4 marker's `persona` object.

1. **Researcher voice** — which pronoun the persona uses about
   itself (this affects nothing else):
   - "she" — "she found, she counted" → `"gender": "f"`
   - "he" — "he found, he counted" → `"gender": "m"`
   - "neutral" — "found, counted" → `"gender": "neutral"` (default)
2. **Tone** — one-line sample each:
   - "business" — calm and to the point: "7 channels in; three takeaways and a
     recommendation below." → `"tone": "business"` (default)
   - "zbs" — bold, with an edge: "7 channels, zero fluff — and there's real
     meat here. Three finds, let's go." → `"tone": "zbs"`
   - "neutral" — no coloring: "The 7-channel report is ready. Key findings
     below." → `"tone": "neutral"`
   - "custom" — free text via Other (e.g. "pirate slang") → stored
     verbatim as the `tone` value.

Prose fallback (hosts without a modal ask) — wait for the answers, defaults
in brackets:
```
I'll set the researcher voice (Enter — keep the default):
  Gender:  1. she   2. he   3. neutral               [3]
  Tone:    1. business   2. zbs   3. neutral   4. custom — say which   [1]
```

**STEP 3 — one visible decision per tier.** Offer upgrades one at a time,
always naming what is already unlocked free first. Never stack questions.

**How to connect a key (say this whenever a tier needs one).** There are two
ways, pick whichever is easier — the tool reads both:
1. **Env var** — `export <ENV_VAR>="<key>"` (add it to the shell profile to
   persist). Nothing is written to disk by the tool.
2. **Key file** — create `<secrets-dir>/<filename>.txt` containing just the key
   (`chmod 600` it). The secrets dir is `DEEP_RESEARCH_SECRETS_DIR` if set,
   else `~/.config/zbs-researcher/secrets` (respects `XDG_CONFIG_HOME`).

After the user adds a key, **prove it took**: run `python3
"$SKILL_DIR/scripts/deep-research.py" --diagnose` (shows which providers are
now configured, no network) and then one real segment through the new channel.
The full provider → env-var → key-file → where-to-get-it table lives in
`CONFIGURATION.md`; name the specific one for the tier the user is unlocking.

- **Tier 1 — own Gemini/Grok keys** (grounded LLM lenses; Gemini also reads
  YouTube). Gemini: `GEMINI_API_KEY` or `gemini-key.txt`, get it at
  aistudio.google.com/apikey. Grok: `GROK_API_KEY` or `grok-api-key.txt`, from
  console.x.ai. Perplexity (optional): `PERPLEXITY_API_KEY` or
  `perplexity-key.txt`, from perplexity.ai/settings/api. Each direct key
  unlocks its lens independently.
- **Tier 2 — one OpenRouter key** routes ALL LLM lenses through a single key
  when their direct keys are absent (direct keys always win): `OPENROUTER_API_KEY`
  or `openrouter-key.txt`, from openrouter.ai/keys.
- **Telegram** (opt-in, HARD WARNING gate): separate/secondary account only,
  never the personal one; state the ban risk and the risk to personal DMs
  plainly; require explicit acknowledgement of both before any session
  capture starts. The acknowledgement is machine-enforced: the connector
  refuses to run until the environment carries
  `DEEP_RESEARCH_TELEGRAM_ACK=separate-account` (exact value). The Telethon
  `*.session` file lives ONLY in the secrets dir (`DEEP_RESEARCH_SECRETS_DIR`
  or `~/.config/zbs-researcher/secrets`; chmod 0600 on POSIX) — never inside the project
  or research output tree. Telethon itself is an optional install
  (`pip install telethon`); the connector is off by default — run it with
  `--only telegram`.
- **TikTok/IG**: pay-per-use vendor (ScrapeCreators), off by default; give an
  honest per-run cost note before enabling. Vendor is selectable with
  `DEEP_RESEARCH_TIKTOK_VENDOR` (`scrapecreators` default; `apify` needs
  `APIFY_TOKEN`); run it with `--only tiktok-ig` — every run costs vendor
  credits and the report header says so. Video transcription uses the media
  backend: the default `client` profile needs `GROQ_API_KEY` + `GEMINI_API_KEY`
  (cloud, cents), while `DEEP_RESEARCH_PROFILE=self` runs local MLX Whisper at
  $0 (Mac-bound) — name the free local option, not just the paid keys.
- **Threads**: two honest routes, pick one. Token-gated official API — free,
  2,200 queries/day, but Standard Access searches only your own posts
  (Advanced Access via App Review, ~1–2 weeks, unlocks public search) and
  results carry no engagement counts. OR instant pay-per-use via
  ScrapeCreators (engagement counts included, 1 credit/request, ~10 posts).
  With only a ScrapeCreators key the connector routes to the vendor
  automatically; `DEEP_RESEARCH_THREADS_VENDOR=scrapecreators` forces it
  even when a token exists.
- **Meta Ad Library**: free but token-gated — needs the user's own token.

Each accepted tier ends with a verification step that proves it works: a real
one-connector segment run through the newly unlocked channel.

**STEP 4 — verify + doctor.** Run one more real segment, then show state with
no network call:
```bash
python3 "$SKILL_DIR/scripts/deep-research.py" --diagnose
```
Then write the onboarding marker `<secrets-dir>/onboarding.json` =
`{"wizard_done": true, "tier": "<highest unlocked>",
"persona": {"gender": "<f|m|neutral>", "tone": "<business|zbs|neutral|free
text>"}}`, where the secrets dir is `DEEP_RESEARCH_SECRETS_DIR` or
`~/.config/zbs-researcher/secrets`. Use the STEP-2.5 answers; if they were skipped or never
reached, write the defaults `{"gender": "neutral", "tone": "business"}`.
`detect_state` and `--diagnose` surface the persona; old markers without it
keep working (persona reads as unset, defaults apply).

**Demand signals — reachable from any tier.** If the user says they want the
paid/hosted version:
```bash
python3 "$SKILL_DIR/scripts/deep-research.py" --signal want-paid
# or: --signal host-for-me
```
This records the signal locally; it notifies the maintainer only when a notify target is
configured, and the confirmation copy must say honestly which of the two
happened. Never silently create accounts or mint anything.

**Prose fallback (hosts without a modal ask).** Same flow, numbered options:
```
Deep multi-source research, $0 to start, zero keys. Pick one:
  1. Auto — run the free proof now on a topic you name
  2. Manual — choose sources first
  3. Skip — no onboarding, never ask again
```
Wait for the number, then continue at the matching step above.

## Persona voice — voicing rules (apply on every run, not just onboarding)

The persona is **ZBS Researcher** (ZBS — "badass-grade") — a brand name that
lives in copy only; the skill id, paths, and commands stay `deep-research`.
Read `persona` from the detected state (STEP 0 hook JSON or `detect_state.py`)
and voice output accordingly:

- **Tone is a rendering layer, not a data layer.** It shapes wording,
  intonation, and sign-off of `synthesis.md`, briefs, and chat replies —
  NEVER findings, rankings, numbers, honesty notes, or warnings. The
  Telegram warning (STEP 3) stays stern in every tone, including free-text
  "custom".
- **Gender affects only the persona's own self-reference** ("she found" /
  "he found" / "found") — never the findings, never how the user is
  addressed.
- **Profanity floor:** no profanity in client-facing artifacts
  (`synthesis.md`, `brief.html`, reports) by default — this binds ALL tone
  values, presets AND free-text "custom" — unless the user explicitly lifts
  it. "zbs" is badass-energy, not badass-vocabulary.
- **Changing persona later:** the user just says so in chat — edit the
  `persona` object inside `<secrets-dir>/onboarding.json` directly. No
  wizard re-run; `wizard_done` stays untouched.
- No persona in the marker (legacy install or skipped STEP 2.5) → defaults:
  neutral voice, business tone.

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

# GPT lens (OPT-IN — bills OpenAI API, only on your OK)
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
├── github.md             — top repos (stars, push recency)
├── github-issues.md      — top issues by reactions + comment excerpts
├── reddit.md             — top posts (or ERROR.md)
├── bluesky.md            — top posts (or ERROR.md)
├── launch-radar.md       — what's shipping: momentum-ranked launches + category velocity
├── revenue-radar.md      — what's selling: Flippa sold prices + Substack bestseller tiers
├── telegram.md           — Telegram channel posts + comments (opt-in, ack-gated)
├── tiktok-ig.md          — TikTok/IG posts + comments (opt-in, pay-per-use)
├── threads.md            — Threads posts by keyword (official token or ScrapeCreators)
├── synthesis.md          — session: overlaps, contradictions, recommendation
└── brief.html            — optional shareable dark-mode HTML (self-contained)
```

A direct raw-runner invocation creates the unique project-local directory and
writes only `_topic.txt`, `manifest.json`, and the selected channel files. An
explicit `--output-dir` keeps intentional standalone output wherever the
caller requested it. Probe and render-only modes allocate no research run.

## Tech detail

- Channels run in parallel via threading; ~3–7 min wall-clock (LLM channels dominate; direct channels finish in <2s).
- Keys read from `~/.config/zbs-researcher/secrets/{gemini-key,grok-api-key,openai-api-key,perplexity-key}.txt` (or env `GEMINI_API_KEY`, `GROK_API_KEY`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`). The openai-key read is name-tolerant (`openai-api-key.txt` / `openai-key.txt` / `openai.txt`).
- OpenAI channel (**opt-in only**) uses gpt-5.4 (non-Pro) via `api.openai.com/v1/responses`. It bills the OpenAI API, so it is not in the default set — enable with `--only openai` on your explicit OK. Pro models are never used; that spend is reserved for `emergency-pro`.
- Perplexity uses `sonar` (env `PERPLEXITY_RESEARCH_MODEL` to override).
- If a channel fails (quota, network, key, throttle) it writes `<name>.ERROR.md` and records the error in `manifest.json`; other channels continue.
- Direct channels are free and need no key. `github` and `github-issues` prefer authed `gh` (higher rate limit), fall back to unauthenticated API.
- HTML brief renders with a built-in mini markdown→HTML converter (no external deps); output is fully self-contained (inline CSS, system-font fallbacks behind Inter/JetBrains Mono) — safe to hand off or share.

## Limits

- **Gemini** grounding sometimes returns plain web, not YouTube. For strictly YouTube, append `site:youtube.com`.
- **Grok** X search caps ~25 posts/query — reformulate for deeper passes.
- **OpenAI/Perplexity** sometimes miss small niche communities — enumerate exact subreddits/orgs/domains in the query.
- **Polymarket** only fires for forecastable topics; honest "no markets matched" otherwise (uses real `/public-search`, not top-100-by-volume).
- **Reddit / Bluesky** are best-effort — Reddit throttles unauthenticated JSON and may degrade to ERROR.md; that's expected, the LLM channels cover the same ground.
- Synthesis quality depends on the reports — if all agree, the value is noticing it; if they disagree, the value is naming *why*.

## Cost note

- Default run: Gemini + Grok + Perplexity (cheap, cents to ~$1 by depth) + free direct channels. **No Anthropic/OpenAI API spend.**
- openai channel is opt-in and bills OpenAI per token — off unless you enable it.
- Pro reasoning is not needed for retrieval+synthesis; escalate only when you explicitly opt in to paid Pro reasoning. For a GPT opinion at flat cost, use Codex interactively.

## Adding more connectors

- TikTok / Instagram transcripts need a ScrapeCreators key → drop it in
  `~/.config/zbs-researcher/secrets/scrapecreators-key.txt` (or `SCRAPECREATORS_KEY`) and
  add a `direct` connector in the registry.
- Brave Search → `~/.config/zbs-researcher/secrets/brave-key.txt` (or `BRAVE_API_KEY`).
- Each new connector: add one `channel_*` function + a `Connector(...)` line
  in the registry + an entry in `OUTPUT_NAMES`. The runner, `--only/--skip`,
  `--list-connectors`, and manifest pick it up automatically.

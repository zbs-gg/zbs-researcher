# Configuration

The plugin works with **zero configuration** for the free direct connectors.
The LLM channels each need one API key (or one OpenRouter key for all three
default lenses — Tier 2).

## Free out of the box (no keys)

`hackernews`, `hiring`, `polymarket`, `github`, `github-issues`, `reddit`,
`bluesky`, `launch-radar`, `revenue-radar` — these call public endpoints.
`github`/`github-issues` use your `gh` CLI auth if present (higher rate
limit), otherwise the unauthenticated API. `reddit` and `bluesky` are
best-effort (some networks throttle them; they degrade to an `ERROR.md`
without affecting other channels).

## LLM channels — provide a key to activate

| Channel | Env var | Provider | Default |
|---|---|---|---|
| gemini | `GEMINI_API_KEY` | Google AI Studio | on |
| grok | `GROK_API_KEY` | xAI | on |
| perplexity | `PERPLEXITY_API_KEY` | Perplexity | on |
| openai | `OPENAI_API_KEY` | OpenAI | **opt-in** (bills per token) |
| *(Tier 2)* | `OPENROUTER_API_KEY` | OpenRouter | routes gemini+grok+perplexity when their direct keys are absent; direct keys always win; never routes openai |

Set them as environment variables:

```bash
export GEMINI_API_KEY=AIza...
export GROK_API_KEY=xai-...
export PERPLEXITY_API_KEY=pplx-...
# ONE key for all three default lenses instead (Tier 2):
export OPENROUTER_API_KEY=sk-or-...
# openai is opt-in; only export if you intend to use --only openai
export OPENAI_API_KEY=sk-...
```

A channel with no key is simply skipped and recorded in `manifest.json`
under `connectors_skipped` — the run continues with whatever is available.

## Gated / opt-in connectors

| Connector | Env var(s) | Notes |
|---|---|---|
| meta-ads | `META_ADS_TOKEN` | free Meta Ad Library token; auto-skipped without it |
| launch-radar (PH slice) | `PRODUCTHUNT_TOKEN` | optional free read token; the other three sources need nothing |
| telegram | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `DEEP_RESEARCH_TELEGRAM_ACK=separate-account` | off by default; needs a Telethon `*.session` in the secrets dir; see the security section below |
| tiktok-ig | `SCRAPECREATORS_KEY` (or `DEEP_RESEARCH_TIKTOK_VENDOR=apify` + `APIFY_TOKEN`) | off by default; pay-per-use vendor — every run costs credits |
| threads | `THREADS_ACCESS_TOKEN` (official, free) or `SCRAPECREATORS_KEY` (vendor); `DEEP_RESEARCH_THREADS_VENDOR=scrapecreators` forces the vendor path | key-gated; official path is free (Standard Access = own posts only), vendor path is pay-per-use |
| youtube | none — but needs the `yt-dlp` tool installed | free and on by default; without `yt-dlp` the channel writes `youtube.ERROR.md` and its neighbours keep running |
| media backend (used by youtube + tiktok-ig) | audio: `GROQ_API_KEY` **or** `OPENROUTER_API_KEY` **or** local `mlx-whisper`; vision: `GEMINI_API_KEY` — or `DEEP_RESEARCH_PROFILE=self` for local MLX | see "Transcription routes" below |

## Transcription routes

Transcription is chosen **independently of the vision profile**, so one
OpenRouter key can cover audio while vision still runs wherever the profile
points.

| Route | What runs | Cost | Privacy |
|---|---|---|---|
| `local` | `mlx-whisper` (`whisper-large-v3-turbo`, ~6 GB peak) | $0 | audio never leaves the machine |
| `groq` | Groq Whisper `whisper-large-v3-turbo` | free tier ≈2,000 requests/day, then ≈$0.04 per hour of audio | audio goes to Groq |
| `openrouter` | OpenRouter `/audio/transcriptions` | per-model, billed by OpenRouter | audio goes to OpenRouter |

`local` is Apple-silicon only (`pip install mlx-whisper`). Resolution order:

1. `DEEP_RESEARCH_TRANSCRIBE_BACKEND=local|groq|openrouter` — forces one route.
2. `"transcribe"` in `<secrets-dir>/onboarding.json` — what the wizard asked
   once and stored.
3. Derived: `DEEP_RESEARCH_PROFILE=self` → local; otherwise Groq when its key
   is set, else OpenRouter when its key is set.
4. Nothing configured → the media channels degrade with a note naming all
   three options. No silent fallback to a provider you did not choose.

An explicitly chosen route is honored even when its credential is missing —
the error then says exactly what to fix, instead of quietly billing someone
else. `python3 scripts/deep-research.py --diagnose` prints the machine and the
route that will actually run.

Related env vars: `DEEP_RESEARCH_TRANSCRIBE_MODEL` (OpenRouter model id,
default `openai/whisper-large-v3`), `DEEP_RESEARCH_WHISPER_MODEL` (Groq model
id), `DEEP_RESEARCH_YOUTUBE_READ_TOP` (videos opened per run, default 5),
`DEEP_RESEARCH_YOUTUBE_TRANSCRIBE_TOP` (videos transcribed per run, default
3), `DEEP_RESEARCH_YOUTUBE_MAX_SECONDS` (skip longer videos, default 2700),
`DEEP_RESEARCH_YOUTUBE_SUB_LANGS` (caption languages to try, default
`en-orig,en`).

## Key files instead of env vars

Keys may also live as files in a secrets directory (one key per file). The
directory defaults to `~/.config/zbs-researcher/secrets` and is overridable:

```bash
export DEEP_RESEARCH_SECRETS_DIR=~/.config/deep-research/secrets
```

File names checked: `gemini-key.txt`, `grok-api-key.txt`, `openai-api-key.txt`
(or `openai-key.txt` / `openai.txt`), `perplexity-key.txt`,
`openrouter-key.txt` (LLM lenses **and** transcription), `groq-key.txt`,
`meta-ads-token.txt`,
`producthunt-token.txt`, `scrapecreators-key.txt`, `threads-access-token.txt`,
`telegram-api-id.txt`,
`telegram-api-hash.txt`. Each file may hold the bare key or a `KEY = value`
line — the first match wins. Env vars take over when no file is found.

## Model overrides (optional)

```bash
export OPENAI_RESEARCH_MODEL=gpt-5.4          # default
export PERPLEXITY_RESEARCH_MODEL=sonar        # default
export OPENAI_BASE_URL=https://api.openai.com/v1
```

## Entity fan-out mode (`--mode entity-fanout`)

Deep mode: enumerate the top-N entities for a topic, then query each entity
across every channel. Flags (single mode ignores them):

| Flag | Default | Effect |
|---|---|---|
| `--mode entity-fanout` | `single` | switch on the deep entity-fan-out mode |
| `--entities-n N` | 50 (cap 200) | how many entities to enumerate |
| `--top-k K` | 10 | top-K entities that get the paid LLM lenses (free channels always run on all N) |
| `--concurrency C` | 6 (cap 16) | max parallel (entity, channel) cells |
| `--paid-budget B` | K × available lenses | hard ceiling on paid lens calls; excess is trimmed keeping top-rank entities |
| `--paid-all` | off | run paid lenses on **all** N entities (raises the budget) |
| `--dry-run` | off | enumerate + write `research-plan.md` with the call budget, then stop (no fan-out, no paid calls) |

Free channels (hackernews, github-issues, reddit, bluesky) run with **zero
keys** on all N entities; the paid lenses (grok/gemini/perplexity, or one
OpenRouter key) enrich the top-K. Cost/time is reported honestly in
`manifest.json` (real token usage where the vendor returns it, else a labeled
estimate; a `degraded` flag when a channel was rate-limited). For
product/people-shaped topics with no ranking GitHub repo, a lens key is required
for good entity coverage — without one the run is flagged repo-shaped-only.

## Investigate mode

The flagship question-driven loop is session-driven — there is no
`--mode investigate`. The session composes short target-scoped queries and
drives three stateless runner primitives (full playbook: the skill's
INVESTIGATE MODE section):

| Call | What it does |
|---|---|
| `"<composed query>" --fire <source> --output-dir DIR` | fire ONE composed query on ONE named source; stdout is exactly one JSON envelope `{source, path, items, status, provenance}`; a failing channel degrades to an `.ERROR.md` twin with `status: "error"` while the exit code stays 0; repeated fires into the same directory accumulate one `manifest.json` |
| `--coverage RUN_DIR` | print the coverage-receipts markdown section ("Coverage — what a web-index researcher would miss") from `RUN_DIR/manifest.json`; markers render only from real provenance records — a manifest without provenance prints nothing, never a fabricated section |
| `--feedback "<note>" --topic "<topic>"` | append the human note to a local `investigate-feedback.jsonl` in the secrets dir (created 0600); the next run on the topic reads it back before composing |

Bounds the playbook enforces: **4 drill rounds max** by default — stop
earlier the moment a round surfaces no new leads — and the paid lenses
(grok / gemini / perplexity) are budget-conscious: the free channels carry
the breadth, paid fires are saved for the leads that matter. A `--fire` on
a keyless paid source refuses up front, naming the missing keys — no
surprise paid calls.

### Cartographer relay (opt-in)

```bash
export DEEP_RESEARCH_CARTOGRAPHER_URL=https://your-cartographer.example/feedback
```

Unset (the default), feedback is **saved locally to inform the next run**
and no network I/O happens — useful, not learning. Set it — it must be an
`https://` URL, anything else is refused — and each feedback row is also
POSTed to your own Cartographer install so a research profile can compound
across runs. The relay is failure-tolerant and honest: the local append
always happens first, a relay failure never loses the note, and the
confirmation copy claims a relay only after an actual HTTP 2xx. This repo
ships no endpoint, no token, no default.

### Eval harness (`scripts/eval_harness.py`)

```bash
python3 "$SKILL_DIR/scripts/eval_harness.py" "<question>" --beast-dir RUN_DIR
```

Scores an existing run against a free web-index baseline on three axes —
primary-source depth (distinct quoted threads), freshness (median item age
in hours), native social coverage — and appends one JSON row to
`eval-log.jsonl` beside the run. The baseline is a Brave Search `site:`
pass: `BRAVE_API_KEY` (or `brave-key.txt` in the secrets dir) is
**optional** — without it the baseline row honestly reads
`unavailable - no web-index key configured`, the run side still scores,
and no network call is made. A richer paid baseline (`PARALLEL_API_KEY`)
is an opt-in hook only, never required.

## Budget note

The default run bills **no Anthropic and no OpenAI** API. Retrieval is
Gemini + Grok + Perplexity + free connectors; synthesis runs in your Claude
Code session. The `openai` channel is the only one that spends OpenAI credits,
and it is off unless you pass `--only openai` (or add it via `--skip`-less
selection). Pro/reasoning-heavy models are never called by this plugin.

## Security & transparency — what it does, what it sends where

Everything network-touching is listed here. The general shape: connectors
send **your research query text** to the endpoints below and nothing else —
no telemetry, no analytics, no phoning home. Keys are read at call time from
the environment or the secrets dir; they are never logged, echoed, or written
into research output.

| Connector | Endpoint(s) | What leaves the machine | Key / credential | Default |
|---|---|---|---|---|
| gemini | `generativelanguage.googleapis.com`; Tier 2: `openrouter.ai` | query/prompt text | `GEMINI_API_KEY` / `gemini-key.txt`; Tier-2 fallback `OPENROUTER_API_KEY` | on (skipped without key) |
| grok | `api.x.ai`; Tier 2: `openrouter.ai` | query/prompt text | `GROK_API_KEY` / `grok-api-key.txt`; Tier-2 fallback `OPENROUTER_API_KEY` | on (skipped without key) |
| perplexity | `api.perplexity.ai`; Tier 2: `openrouter.ai` | query/prompt text | `PERPLEXITY_API_KEY` / `perplexity-key.txt`; Tier-2 fallback `OPENROUTER_API_KEY` | on (skipped without key) |
| openai | `api.openai.com` (or `OPENAI_BASE_URL`) | query/prompt text | `OPENAI_API_KEY`; **never** OpenRouter-routed | **off — opt-in, bills per token** |
| hackernews | `hn.algolia.com` | query text | none | on |
| hiring | `hn.algolia.com` | query text | none | on |
| polymarket | `gamma-api.polymarket.com` | query text | none | on |
| github | `api.github.com` (or your authed `gh` CLI) | query text | none (optional `gh` auth = higher rate limit) | on |
| github-issues | `api.github.com` (or `gh`) | query text | none (optional `gh` auth) | on |
| reddit | `arctic-shift.photon-reddit.com` | query text + candidate subreddit names | none | on |
| bluesky | `public.api.bsky.app` | query text | none | on |
| youtube | `youtube.com` / `googlevideo.com` via the local `yt-dlp` tool; audio then goes to whichever transcription route is configured (see above) | query text (as a YouTube search), then caption tracks and — only when captions are unusable — the audio of the top videos | none for search/captions; the transcription route needs its own credential | on, degrades to ERROR.md without `yt-dlp` |
| launch-radar | `hn.algolia.com`, `yc-oss.github.io`, `api.github.com`; with token also `api.producthunt.com` | query text (the yc-oss pull is a plain list download — no query sent) | none; optional `PRODUCTHUNT_TOKEN` | on |
| revenue-radar | `api.flippa.com`, `substack.com` | nothing topic-specific — category/list pulls, filtered locally | none | on |
| meta-ads | `graph.facebook.com` (Ad Library, EU scope) | query text + your token | `META_ADS_TOKEN` / `meta-ads-token.txt` | on, auto-skipped without token |
| telegram | Telegram MTProto via a Telethon client session | channel search terms + channel reads, authenticated as the research account | `TELEGRAM_API_ID` + `TELEGRAM_API_HASH` + `*.session` in the secrets dir; runtime ack `DEEP_RESEARCH_TELEGRAM_ACK=separate-account` | **off — double opt-in** |
| tiktok-ig | `api.scrapecreators.com` or `api.apify.com` | query text | `SCRAPECREATORS_KEY` or `APIFY_TOKEN` (vendor via `DEEP_RESEARCH_TIKTOK_VENDOR`) | **off — opt-in, pay-per-use** |
| threads | `graph.threads.net` (official) or `api.scrapecreators.com` (vendor) | query text + your token (official token is redacted from every error path, never rendered) | `THREADS_ACCESS_TOKEN` / `threads-access-token.txt`, or `SCRAPECREATORS_KEY` for the vendor path | key-gated; official free / vendor pay-per-use |

Non-connector components:

- **`detect_state.py`** (SessionStart hook, `--diagnose`): makes **no network
  calls**. It emits provider **booleans and names only** — never key values,
  never key prefixes. It also reports the **machine** (OS, architecture, RAM,
  CPU count, and on macOS the chip name from a local `sysctl` call) so the
  wizard can offer the free local transcription route only where it would
  actually run. That is local hardware information; nothing is transmitted.
- **`signals.py`** (`--signal want-paid | host-for-me`): appends one JSON line
  to a **local** `demand-signals.jsonl` in the secrets dir (created 0600).
  It POSTs the signal over HTTPS **only** when the operator has set
  `DEEP_RESEARCH_NOTIFY_URL` themselves — this repo ships **no endpoint, no
  token, no bot credential**, and non-HTTPS targets are refused. The
  confirmation copy honestly states whether a notification was sent.
- **`investigate_feedback.py`** (`--feedback`): appends the note to a
  **local** `investigate-feedback.jsonl` in the secrets dir (created 0600).
  It POSTs the feedback JSON over HTTPS **only** when the operator has set
  `DEEP_RESEARCH_CARTOGRAPHER_URL` themselves (same shape as the signals
  relay: no shipped endpoint, no token, non-HTTPS refused, local append
  first, relay claimed only after a real 2xx).
- **`eval_harness.py`**: its only network call is the web-index baseline —
  the question text goes to `api.search.brave.com` **only** when
  `BRAVE_API_KEY` / `brave-key.txt` is configured. Without a key the
  baseline row reads "unavailable", the run side still scores, and no
  network I/O happens.
- **Media backend** (`media_backend.py`, used by tiktok-ig): in the default
  `client` profile, audio bytes go to `api.groq.com` (Groq Whisper — Groq's
  own OpenAI-*compatible* route, not OpenAI) and image bytes to
  `generativelanguage.googleapis.com` (Gemini vision).
  `DEEP_RESEARCH_PROFILE=self` runs local MLX models instead — nothing
  leaves the machine.
- **Telegram session storage**: the Telethon `*.session` file lives **only**
  in the secrets dir (`DEEP_RESEARCH_SECRETS_DIR` or `~/.config/zbs-researcher/secrets`,
  chmod 0600 on POSIX) — never in the project or research output tree. The
  separate-account acknowledgement is machine-enforced: without the exact
  env value the connector refuses to run.

Least-privilege summary:

- **Zero keys by default.** Every Tier-0 connector works with no credential;
  a missing key means the channel is skipped and recorded in
  `manifest.json` — never a blocked run or a nag loop.
- **Each tier unlocks explicitly**, one visible decision at a time (see the
  onboarding wizard in the skill).
- **No Anthropic API calls, ever** — `api.anthropic.com` appears nowhere in
  the code. **No OpenAI API calls by default** — the openai channel is
  opt-in and direct-key only.
- **Enforced by the selftest** (`skills/deep-research/scripts/selftest.sh`):
  a secret-scan over tracked source, a POSIX-only-symbol portability grep,
  and a zero-key Tier-0 wizard dry-run.

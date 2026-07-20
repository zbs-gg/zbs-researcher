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
| media backend (used by tiktok-ig) | `GROQ_API_KEY` (audio), `GEMINI_API_KEY` (vision) — or `DEEP_RESEARCH_PROFILE=self` for local MLX | client profile is cloud-cheap; self profile is $0 local |

## Key files instead of env vars

Keys may also live as files in a secrets directory (one key per file). The
directory defaults to `~/elle/.secrets` and is overridable:

```bash
export DEEP_RESEARCH_SECRETS_DIR=~/.config/deep-research/secrets
```

File names checked: `gemini-key.txt`, `grok-api-key.txt`, `openai-api-key.txt`
(or `openai-key.txt` / `openai.txt`), `perplexity-key.txt`,
`openrouter-key.txt`, `groq-key.txt`, `meta-ads-token.txt`,
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
| launch-radar | `hn.algolia.com`, `yc-oss.github.io`, `api.github.com`; with token also `api.producthunt.com` | query text (the yc-oss pull is a plain list download — no query sent) | none; optional `PRODUCTHUNT_TOKEN` | on |
| revenue-radar | `api.flippa.com`, `substack.com` | nothing topic-specific — category/list pulls, filtered locally | none | on |
| meta-ads | `graph.facebook.com` (Ad Library, EU scope) | query text + your token | `META_ADS_TOKEN` / `meta-ads-token.txt` | on, auto-skipped without token |
| telegram | Telegram MTProto via a Telethon client session | channel search terms + channel reads, authenticated as the research account | `TELEGRAM_API_ID` + `TELEGRAM_API_HASH` + `*.session` in the secrets dir; runtime ack `DEEP_RESEARCH_TELEGRAM_ACK=separate-account` | **off — double opt-in** |
| tiktok-ig | `api.scrapecreators.com` or `api.apify.com` | query text | `SCRAPECREATORS_KEY` or `APIFY_TOKEN` (vendor via `DEEP_RESEARCH_TIKTOK_VENDOR`) | **off — opt-in, pay-per-use** |
| threads | `graph.threads.net` (official) or `api.scrapecreators.com` (vendor) | query text + your token (official token is redacted from every error path, never rendered) | `THREADS_ACCESS_TOKEN` / `threads-access-token.txt`, or `SCRAPECREATORS_KEY` for the vendor path | key-gated; official free / vendor pay-per-use |

Non-connector components:

- **`detect_state.py`** (SessionStart hook, `--diagnose`): makes **no network
  calls**. It emits provider **booleans and names only** — never key values,
  never key prefixes.
- **`signals.py`** (`--signal want-paid | host-for-me`): appends one JSON line
  to a **local** `demand-signals.jsonl` in the secrets dir (created 0600).
  It POSTs the signal over HTTPS **only** when the operator has set
  `DEEP_RESEARCH_NOTIFY_URL` themselves — this repo ships **no endpoint, no
  token, no bot credential**, and non-HTTPS targets are refused. The
  confirmation copy honestly states whether a notification was sent.
- **Media backend** (`media_backend.py`, used by tiktok-ig): in the default
  `client` profile, audio bytes go to `api.groq.com` (Groq Whisper — Groq's
  own OpenAI-*compatible* route, not OpenAI) and image bytes to
  `generativelanguage.googleapis.com` (Gemini vision).
  `DEEP_RESEARCH_PROFILE=self` runs local MLX models instead — nothing
  leaves the machine.
- **Telegram session storage**: the Telethon `*.session` file lives **only**
  in the secrets dir (`DEEP_RESEARCH_SECRETS_DIR` or `~/elle/.secrets`,
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

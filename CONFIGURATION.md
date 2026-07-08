# Configuration

The plugin works with **zero configuration** for the free direct connectors.
The LLM channels each need one API key.

## Free out of the box (no keys)

`hackernews`, `hiring`, `polymarket`, `github`, `reddit`, `bluesky` — these
call public endpoints. `github` uses your `gh` CLI auth if present (higher
rate limit), otherwise the unauthenticated API. `reddit` and `bluesky` are
best-effort (some networks throttle them; they degrade to an `ERROR.md`
without affecting other channels).

## LLM channels — provide a key to activate

| Channel | Env var | Provider | Default |
|---|---|---|---|
| gemini | `GEMINI_API_KEY` | Google AI Studio | on |
| grok | `GROK_API_KEY` | xAI | on |
| perplexity | `PERPLEXITY_API_KEY` | Perplexity | on |
| openai | `OPENAI_API_KEY` | OpenAI | **opt-in** (bills per token) |

Set them as environment variables:

```bash
export GEMINI_API_KEY=AIza...
export GROK_API_KEY=xai-...
export PERPLEXITY_API_KEY=pplx-...
# openai is opt-in; only export if you intend to use --only openai
export OPENAI_API_KEY=sk-...
```

A channel with no key is simply skipped and recorded in `manifest.json`
under `connectors_skipped` — the run continues with whatever is available.

## Key files instead of env vars

Keys may also live as files in a secrets directory (one key per file). The
directory defaults to `~/.openclaw/secrets` and is overridable:

```bash
export DEEP_RESEARCH_SECRETS_DIR=~/.config/deep-research/secrets
```

File names checked: `gemini-key.txt`, `grok-api-key.txt`, `openai-api-key.txt`
(or `openai-key.txt` / `openai.txt`), `perplexity-key.txt`. Each file may hold
the bare key or a `KEY = value` line — the first match wins. Env vars take
over when no file is found.

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

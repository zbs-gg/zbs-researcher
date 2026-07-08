# deep-research

A Claude Code plugin for **plan-first, multi-channel deep research**. It
triangulates a topic across reasoning-model lenses **and** raw platform
signal, then synthesizes the contradictions — not just the top-ranked
summary.

Unlike a single web search, it pulls in parallel from up to **10 connectors**
and, crucially, **produces a research plan before it runs** and **does not
bill Anthropic or OpenAI APIs by default**.

## Why this one

- **Plan first.** Every run starts by resolving the topic (exact @handles,
  subreddits, repos, whether it's a forecastable event or a hiring-market
  question) and showing a short plan — then executes. No cold keyword blasts.
- **No Anthropic/OpenAI spend by default.** Retrieval runs on Gemini (Google),
  Grok (xAI), and Perplexity plus free direct connectors. Synthesis happens in
  your Claude Code session. The OpenAI channel is opt-in.
- **Structural signal, not just prose.** Direct connectors return numbers an
  LLM won't: HN points, Polymarket odds, GitHub stars/velocity, and a
  **hiring-signal** (how many "Who is hiring?" postings mention your topic —
  a cheap read on whether a skill/trend is heating up).
- **Shareable HTML brief.** Renders a self-contained dark-mode `brief.html`.

## Connectors

| Channel | Type | Needs a key | What it gives |
|---|---|---|---|
| gemini | LLM | Gemini | YouTube + web (grounding) |
| grok | LLM | Grok/xAI | realtime X / Twitter |
| perplexity | LLM | Perplexity | web + news, citation-first |
| openai | LLM | OpenAI *(opt-in)* | Reddit/HN/GitHub/blogs — **bills OpenAI** |
| hackernews | direct | free | stories by points/comments |
| hiring | direct | free | job-market hotness for a topic |
| polymarket | direct | free | real-money odds (implied %) |
| github | direct | free | repo stars, velocity, issues |
| reddit | direct | free* | top posts by upvotes *(best-effort)* |
| bluesky | direct | free* | top posts *(best-effort)* |

Direct channels are zero-config. LLM channels activate when their key is
present. See [CONFIGURATION.md](CONFIGURATION.md).

## Install

```bash
# from a marketplace (once published)
/plugin marketplace add nkkmnk/deep-research-skill
/plugin install deep-research

# or test locally without installing
claude --plugin-dir /path/to/deep-research-skill
```

Then the skill is available as `/deep-research:deep-research` (Claude also
invokes it automatically when a task needs multi-source diligence).

## Quickstart

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/deep-research/scripts/deep-research.py"

# what's live right now (the plan step)
python3 "$SCRIPT" --list-connectors

# a full run (every available connector, in parallel)
python3 "$SCRIPT" "LLM long-context memory failure modes" \
    --output-dir ~/research/deep-research-longctx-2026-07-08

# free hiring-market read for a skill/tech
python3 "$SCRIPT" "context engineering" --output-dir ~/research/hire --only hiring

# render a shareable brief from your synthesis
python3 "$SCRIPT" --render-html ~/research/.../synthesis.md --html-out ~/research/.../brief.html
```

`--only a,b` / `--skip x,y` scope the channels; `--q name:query` aims a single
channel; `--max-items N` sets items per direct channel.

## Requirements

- Python 3.9+ (stdlib only — no pip install)
- Optional: `gh` (GitHub CLI) for a higher-rate GitHub connector
- API keys only for the LLM channels you want (see CONFIGURATION.md)

## License

MIT — see [LICENSE](LICENSE).

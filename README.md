# deep-research

A Claude Code plugin for **plan-first, multi-channel deep research**. It
triangulates a topic across reasoning-model lenses **and** raw platform
signal, then synthesizes the contradictions — not just the top-ranked
summary.

Unlike a single web search, it pulls in parallel from up to **16 connectors**
and, crucially, **produces a research plan before it runs** and **does not
bill Anthropic or OpenAI APIs by default**.

## Why this one

- **Plan first.** Every run starts by resolving the topic (exact @handles,
  subreddits, repos, whether it's a forecastable event or a hiring-market
  question), writes a short `research-plan.md` into the project-local run,
  and only then executes. No cold keyword blasts or detached plan files.
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
| github | direct | free | repo stars, velocity |
| github-issues | direct | free | top issues by reactions + comment excerpts |
| reddit | direct | free* | top posts via Arctic-Shift archive — real score+comments *(best-effort)* |
| bluesky | direct | free* | top posts *(best-effort)* |
| launch-radar | direct | free (PH slice: free token) | what's shipping — Show HN + yc-oss + DevHunt momentum + category velocity |
| revenue-radar | direct | free | what's selling — Flippa sold prices + Substack bestseller tiers |
| meta-ads | direct | free Meta token | who's paying to advertise — Meta Ad Library (EU scope) |
| telegram | direct | *(opt-in)* own Telegram app creds + session | channel posts + discussion comments — separate research account only |
| tiktok-ig | direct | *(opt-in)* pay-per-use vendor key | TikTok/IG posts + comments — every run costs vendor credits |

Free direct channels are zero-config; one OpenRouter key (Tier 2) can drive
all three default LLM lenses at once. LLM channels activate when their key is
present. See [CONFIGURATION.md](CONFIGURATION.md).

A full **"what it sends where"** breakdown — per-connector endpoints, what
data leaves the machine, and which credential (if any) each channel uses —
is in [CONFIGURATION.md](CONFIGURATION.md#security--transparency--what-it-does-what-it-sends-where).
The short version: connectors send your research query text to their public
endpoints and nothing else; no Anthropic calls ever, no OpenAI calls unless
you opt in.

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

The skill is the complete workflow: it allocates one run under the launching
project's `research/` directory, writes the plan first, gathers channel
evidence there, and adds the session-authored synthesis and optional HTML
brief as siblings. Its connector call uses `--prepared-run`, so a lost or
stale run path cannot overwrite a completed bundle or mix topics.

The commands below expose the lower-level **raw-evidence runner**. A direct
topic run writes connector output and `manifest.json`; it does not author a
research plan, synthesis, or brief.

```bash
# Set this to the directory containing the installed skill's SKILL.md.
# Agents receive that absolute path during skill discovery; no Claude-only
# environment variable is required.
SKILL_DIR="/absolute/path/to/skills/deep-research"
SCRIPT="$SKILL_DIR/scripts/deep-research.py"

# what's live right now (read-only; creates no run)
python3 "$SCRIPT" --list-connectors

# raw connector evidence, automatically allocated under this project's research/
python3 "$SCRIPT" "LLM long-context memory failure modes"

# free hiring-market read for a skill/tech
python3 "$SCRIPT" "context engineering" --only hiring

# monorepo/package ownership override
python3 "$SCRIPT" "context engineering" \
    --project-root /absolute/path/to/project --only hackernews,hiring

# intentional standalone destination (bypasses project-root allocation)
python3 "$SCRIPT" "context engineering" \
    --output-dir ./scratch/hiring-evidence --only hiring

# render an existing synthesis beside it (or add --html-out for another name)
python3 "$SCRIPT" --render-html ./research/existing-run/synthesis.md
```

`--only a,b` / `--skip x,y` scope the channels; `--q name:query` aims a single
channel; `--max-items N` sets items per direct channel. `--allocate-run`
reserves and prints a unique run containing only its `_topic.txt` marker. The
skill passes that exact directory back via `--output-dir --prepared-run` after
writing `research-plan.md`; the prepared handoff requires the matching topic,
a non-empty plan, and no prior raw-run artifacts, then creates one atomic
`.raw-run.claim`. Plain `--output-dir` remains an intentionally permissive
low-level override for deliberate recovery after inspection.
`--launch-cwd /absolute/project/path` pins project discovery and relative raw
paths to the directory captured before an agent visits the skill/plugin tree.

## Output ownership

A complete skill-authored bundle stays together:

```text
<project>/research/deep-research-{slug}-{date}[-NN]/
├── research-plan.md
├── _topic.txt
├── .raw-run.claim         # hidden single-writer marker
├── manifest.json
├── <channel>.md (or <channel>.ERROR.md)
├── synthesis.md
└── brief.html (optional)
```

The launch directory is captured before plugin-path resolution. Its Git
top-level owns the default run; outside Git, the captured directory does. Use
`--project-root` when a narrower monorepo package should own the research.
Repeated same-topic runs reserve numbered siblings instead of overwriting.
An explicit `--output-dir` remains a direct-CLI escape hatch and may point
outside the project intentionally.

## Requirements

- Python 3.9+ (stdlib only — no pip install)
- Optional: `gh` (GitHub CLI) for a higher-rate GitHub connector
- Optional: `telethon` (pip) only if you enable the telegram connector
- API keys only for the LLM channels you want (see CONFIGURATION.md)

## Windows

The Python runner is **Windows-native**: stdlib + `threading` only, no
POSIX-only calls (`fcntl`, `pty`, `os.fork`, signal alarms, and friends are
banned by the selftest; the one `os.chmod` is guarded behind an `os.name`
check). Run it from PowerShell or cmd exactly as above:

```powershell
python skills\deep-research\scripts\deep-research.py --list-connectors
```

`scripts/selftest.sh` is a bash script — on Windows run it via **Git Bash**
or **WSL**:

```bash
bash skills/deep-research/scripts/selftest.sh
```

## License

MIT — see [LICENSE](LICENSE).

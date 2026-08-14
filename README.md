```text
████ ███   ███    ███  ████  ███ ████  ██  ███   ███ █  █ ████ ███
  █  █  █ █       █  █ █    █    █    █  █ █  █ █    █  █ █    █  █
 █   ███   ██     ███  ███   ██  ███  ████ ███  █    ████ ███  ███
█    █  █    █    █ █  █       █ █    █  █ █ █  █    █  █ █    █ █
████ ███  ███     █  █ ████ ███  ████ █  █ █  █  ███ █  █ ████ █  █
                  deep research · reactions from real humans
```

# ZBS Researcher

**ZBS Researcher — deep, multi-source research with native, full-breadth
social/community depth and auditable primary evidence.**
It reads the platforms from inside — live X via Grok's `x_search`, Telegram
communities through a real client session, the full Reddit archive via
Arctic-Shift, Threads, TikTok/IG, Bluesky — plus HN, GitHub, Polymarket and
a dozen more channels pulled in parallel, a research plan written before
every run, and a shareable HTML brief at the end. Every load-bearing claim
ships as a real quote + author handle + clickable live link, where a
web-index researcher sees only the indexed scraps. "Free/cheaper" is
not the pitch — quality is: minutes to the first report, $0 and zero keys
to start, but that is a property, not the argument.

## One-command install

```bash
npx -y @zbs-gg/zbs-researcher@latest
```

No node — the same two commands the installer runs (node not required):

```bash
claude plugin marketplace add zbs-gg/zbs-researcher
claude plugin install deep-research@zbs-researcher
```

**No node?** Install [Node.js LTS](https://nodejs.org) for the
npx one-liner, or skip node entirely — the two native commands above need
only the `claude` CLI.

## Demo

*(coming soon: live-board GIF from a terminal + screenshot of the wizard's
first question)*

<!--
CAPTURE (board GIF): record in a REAL terminal — a live TTY at >= 80
columns — NOT from inside an agent session. The animated connector board
intentionally does not render in the agent path: when stderr is not a TTY
it degrades to plain per-channel lines by design. Run directly:

    python3 skills/deep-research/scripts/deep-research.py "<topic>" \
        --only hackernews,github,reddit --max-items 5

Record with asciinema + agg, or terminal screen-capture -> GIF. Save as
docs/assets/board.gif and uncomment:

![Live connector board — direct terminal run](docs/assets/board.gif)
-->

<!--
CAPTURE (persona screenshot): open Claude Code in a fresh project with the
plugin installed and say "run deep research". Screenshot the FIRST
wizard question — the one where ZBS Researcher introduces itself by name
with the Auto / Manual / Skip options. Save as
docs/assets/persona-hello.png and uncomment:

![ZBS Researcher introduces itself in Claude Code](docs/assets/persona-hello.png)
-->

## Tiers at a glance

- **Tier 0 — free, no keys**: HN, hiring-signal, Polymarket, YouTube *(needs `yt-dlp`)*,
  GitHub, github-issues, Reddit, Bluesky, launch-radar, revenue-radar.
- **Tier 1 — your own keys**: LLM lenses Gemini / Grok / Perplexity.
- **Tier 2 — one OpenRouter key**: all three default LLM lenses at once.
- **Opt-in**: Telegram · TikTok/IG · Threads · Meta Ads.

The full channel table is in [Connectors](#connectors) below.

**What goes where — transparent:** connectors send only your query text to
public endpoints and nothing else; the full per-connector breakdown is in
[CONFIGURATION.md](CONFIGURATION.md#security--transparency--what-it-does-what-it-sends-where).

## What it is (plugin id: `deep-research`)

A Claude Code plugin for **plan-first, multi-channel deep research**. It
triangulates a topic across reasoning-model lenses **and** raw platform
signal, then synthesizes the contradictions — not just the top-ranked
summary.

Unlike a single web search, it pulls in parallel from up to **18 connectors**
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
- **It reads what was said, not what was tagged.** The YouTube channel opens
  videos and takes the caption track — and when the captions are missing or
  too poor to quote, it transcribes the audio itself (locally at $0 on Apple
  silicon, or via Groq/OpenRouter). A web index only ever sees the title and
  description, so that transcript is evidence no index holds.
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
| youtube | direct | free *(needs `yt-dlp`)* | what was **said** in videos — human captions when they exist, our own transcription when they don't |
| launch-radar | direct | free (PH slice: free token) | what's shipping — Show HN + yc-oss + DevHunt momentum + category velocity |
| revenue-radar | direct | free | what's selling — Flippa sold prices + Substack bestseller tiers |
| meta-ads | direct | free Meta token | who's paying to advertise — Meta Ad Library (EU scope) |
| telegram | direct | *(opt-in)* own Telegram app creds + session | channel posts + discussion comments — separate research account only |
| tiktok-ig | direct | *(opt-in)* pay-per-use vendor key | TikTok/IG posts + comments — every run costs vendor credits |
| threads | direct | *(key-gated)* free official token or pay-per-use vendor | Threads posts by keyword — official keeps Meta's TOP order, vendor adds engagement counts |

Free direct channels are zero-config; one OpenRouter key (Tier 2) can drive
all three default LLM lenses at once — and now transcription too. LLM channels activate when their key is
present. See [CONFIGURATION.md](CONFIGURATION.md).

A full **"what it sends where"** breakdown — per-connector endpoints, what
data leaves the machine, and which credential (if any) each channel uses —
is in [CONFIGURATION.md](CONFIGURATION.md#security--transparency--what-it-does-what-it-sends-where).
The short version: connectors send your research query text to their public
endpoints and nothing else; no Anthropic calls ever, no OpenAI calls unless
you opt in.

## Install

```bash
# from the marketplace
claude plugin marketplace add zbs-gg/zbs-researcher
claude plugin install deep-research@zbs-researcher

# or test locally without installing
claude --plugin-dir /path/to/zbs-researcher
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

# ENTITY FAN-OUT — deep mode: enumerate the top-N entities for a topic, then
# query EACH entity across every channel (an entity x channel dossier matrix,
# not one blanket query per channel). Preview the plan + budget first:
python3 "$SCRIPT" "LLM agent memory" --mode entity-fanout --entities-n 50 --dry-run
# then the full run (free channels on all N; paid lenses on the top-K):
python3 "$SCRIPT" "LLM agent memory" --mode entity-fanout --entities-n 50 --top-k 10
```

**Entity fan-out** (`--mode entity-fanout`) is the deep-research mode. It
enumerates the top-N entities (GitHub stars + HN mentions, free; an LLM lens is
required for product/people-shaped topics with no ranking repo), fans each
entity out across the channels — free channels on all N, paid LLM lenses on the
top-K only (`--paid-all` for all N) — and aggregates a per-entity dossier matrix
plus `brief.html`. It self-allocates its run and writes `research-plan.md` (with
the exact call budget) before firing. Honest cost/time: real token counts + wall
time, and a `degraded` flag when a channel was rate-limited — never `$0 / 40s`.
Flags: `--entities-n` (default 50), `--top-k` (10), `--concurrency` (6),
`--paid-budget`, `--paid-all`, `--dry-run`. Runs free with zero keys on
repo-shaped topics.

**Investigate mode** is the flagship playbook, not a `--mode` value: the
session (Claude) composes one short target-scoped query per source and runs
the loop itself — compose → fire → read → drill → synthesize, bounded at
4 rounds by default. The runner contributes three stateless primitives:

```bash
# fire ONE composed query on ONE source; stdout = exactly one JSON envelope
# {source, path, items, status, provenance}
python3 "$SCRIPT" "owner/repo memory leak" --fire github-issues \
    --output-dir ./scratch/investigate-run

# coverage-receipts: what a web-index researcher would structurally miss,
# rendered ONLY from the manifest's real provenance records — never inferred
python3 "$SCRIPT" --coverage ./scratch/investigate-run

# persist a human feedback note; the next run on this topic reads it back
python3 "$SCRIPT" --feedback "grok was gold, reddit stale" --topic "agent memory"
```

Repeated fires into the same `--output-dir` accumulate one `manifest.json`
with a provenance record and call receipt per fire — including the provider
route, timing, real vendor usage when returned, and an explicit actual,
estimated, or unavailable cost state. HTTP response bodies obey the connector's
total wall-clock deadline; a timeout leaves an atomic private error receipt
instead of an indefinitely open paid call. One run directory accepts only one
active fire at a time; the cross-process lock prevents a slow paid call from
being overwritten by a second operator. The manifest is replaced atomically
with owner-only permissions. The feedback note is saved locally to
inform the next run on the topic (relayed to a Cartographer install only when
you connect one — it is never described as "learned"). The full playbook
(compose table, drill bounds, paid-lens budget) lives in the skill's
INVESTIGATE MODE section; the knobs and the eval harness are in
[CONFIGURATION.md](CONFIGURATION.md#investigate-mode).

Before it searches, investigate decomposes the person's broad question into
the decision, the then/now delta, the hidden entities, and the changes that
could overturn the answer. Before synthesis, every load-bearing claim gets the
date of the fact — not merely the page date — and one proof tier: T1 primary,
T2 first-hand numbers, T3 informed opinion, or T4 unsupported. T4 may be cited
only to challenge a claim. Evidence older than 12 months without current T1/T2
confirmation moves to an explicit stale/historical section instead of driving
the recommendation; unresolved questions stay visible.

The local eval harness can also compare a stored run with Parallel's paid deep
research, but only by explicit choice:

```bash
python3 "$SKILL_DIR/scripts/eval_harness.py" "<same question>" \
    --beast-dir RUN_DIR --baseline parallel --processor ultra \
    --artifact-dir PRIVATE_ARTIFACT_DIR
```

A configured key never triggers this baseline by itself. Both sides are scored
on quoted-source depth, known freshness, and native social coverage; unavailable
or undated evidence stays unavailable or unknown rather than becoming a fake
zero. See [Configuration](CONFIGURATION.md#paid-baseline-parallel-deep-research-opt-in)
for the provider, cost, and data boundary.

With `--artifact-dir`, the duel keeps the complete provider JSON, readable
answer, normalized citation receipts showing what entered each score, run ID,
state, timing, processor, and the published price basis. Files are replaced
atomically with private permissions, and all recorded paths inside the bundle
are relative. Omit the flag to retain the original lightweight eval behavior.

### First official Researcher vs Parallel benchmark

The benchmark controller freezes the five-question English suite before any
answer exists, snapshots a completed investigate run, gates one Parallel Ultra
attempt, creates blind A/B material, and derives a result only after both the AI
audit and owner scores are complete:

```bash
python3 "$SKILL_DIR/scripts/duel_benchmark.py" init \
    --confirm-price-checked
python3 "$SKILL_DIR/scripts/duel_benchmark.py" snapshot-researcher \
    --bundle research/duel-v1-... --question q01 --run-dir RUN_DIR
python3 "$SKILL_DIR/scripts/duel_benchmark.py" run-parallel \
    --bundle research/duel-v1-... --question q01
```

The last command is a no-network cost/readiness preview. A paid attempt requires
a separate `--confirm-paid` after its Researcher answer is frozen; a stored key,
suite approval, price check, or previous question never grants reusable consent.
Only a recorded technical failure permits `--retry-technical`, and every attempt
is preserved. Runtime bundles stay in ignored `research/` with private atomic
files; questions, rubric, code, and synthetic tests are the only committed data.
Before a Researcher snapshot is accepted, every paid `manifest.calls[]` receipt
must carry an actual or estimated USD amount, or an unavailable state reconciled
to a conservative USD cost entry by `call_id`; all such amounts count toward the
USD 10 cap. Each AI audit uses a claim ledger with citation-fit, fact date,
freshness, support status, and evidence note rather than three unchecked
completion flags. The first result is internal and the tool never publishes or
merges it.

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

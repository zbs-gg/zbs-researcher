```text
████ ███   ███    ███  ████  ███ ████  ██  ███   ███ █  █ ████ ███
  █  █  █ █       █  █ █    █    █    █  █ █  █ █    █  █ █    █  █
 █   ███   ██     ███  ███   ██  ███  ████ ███  █    ████ ███  ███
█    █  █    █    █ █  █       █ █    █  █ █ █  █    █  █ █    █ █
████ ███  ███     █  █ ████ ███  ████ █  █ █  █  ███ █  █ ████ █  █
                  deep research · reactions from real humans
```

# ZBS Researcher

**0.7.0** [Changes](CHANGELOG.md) ·
[Actual side-by-side comparison](docs/comparison/README.md) ·
[Where research files live](#output-ownership)

**ZBS Researcher turns a research goal into a human playbook and an auditable
agent context.** The host agent clarifies the decision, connects only the needed
services, searches Russian and English sources, reads social discussions and
video transcripts, follows leads and contradictions, then synthesizes actions.
"Free/cheaper" is not the pitch — quality is: source depth, auditable primary evidence, traceable claims,
and useful next steps. Access gaps remain explicit; superiority over manual
research or another product has not been established.

## Give it a decision; get reusable research

Ask the skill in your agent session, for example:

> Research Reddit and X audience growth for a creator. Help me choose the first
> measurable experiment. Read Russian and English posts, threads, comments and
> these YouTube links. My API budget is $1. Give me a playbook and agent context.

The skill reuses supplied information, asks only about consequential missing
scope, checks configured services offline, and requests missing connections
securely. The default final pair is **`playbook.html` + `agent-context.json`**,
generated from one validated evidence dossier. The HTML is an offline field
manual: actions, measurement, stop conditions, sources and visible limitations.
The JSON contains the same IDs, claims, evidence, coverage and open questions.

New explicit source routes: `reddit-web` (Perplexity discovery), `reddit-thread`
(free targeted archive post/comments), `reddit-live` (paid ScrapeCreators,
explicit only), and `youtube-social` (captions plus bounded comments, **no paid
transcription fallback**). Grok retains returned tool traces; native X access
requires a direct xAI key. Discovery/model summaries never automatically count
as directly read posts. Russian coverage means Russian source text.

Existing installed plugins may still load older instructions until updated.
Use the packaged
[`SKILL.md`](skills/deep-research/SKILL.md) and its
[goal-driven workflow](skills/deep-research/references/goal-driven.md).
The Python runner alone does **not** execute the reasoning loop: the host agent
reads, follows leads and writes the dossier. Legacy quick-scan/entity modes and
their `synthesis.md` / `brief.html` outputs remain supported.

Offline helper commands: `research_session.py prepare`, `status`, `example`,
`reserve`, `settle`, `finalize`, `index`. Reservations retain unknown costs but are not
provider-side caps. Current prices and bounded requests are still required.
Research commands do not install software globally or publish research.

## Local use in Codex

The same goal-driven skill can be loaded in Codex; Claude Code is not required
for this route. Copy the **whole** `skills/deep-research` directory (including
`scripts/` and `references/`) to `~/.agents/skills/deep-research`. If that target
already exists, inspect it before replacing anything. Start a fresh Codex turn
and invoke it explicitly:

> $deep-research Help me choose my first measurable audience-growth experiment.
> Read Russian and English sources. External API budget: $0. Return a playbook
> and agent context, with missing evidence clearly marked.

Use your existing Codex sign-in. Host account usage/limits and external research
provider charges are separate; installing this skill creates no new account or
subscription. Codex reads the skill directly, without the Claude marketplace
installer or SessionStart hook. Goal-driven `prepare` still checks relevant
source configuration offline. This is a local skill installation, not a
published Codex plugin; see the [qualification record](specs/004-goal-driven-research/quickstart.md).

## One-command install — Claude Code, published channel

The installer is a thin shim, not a pinned copy of the research engine: it
fetches the plugin from the GitHub marketplace. npm installer 0.5.0 remains
the registry's latest version as checked on 2026-09-19; publishing shim 0.7.0
is pending npm authentication. The existing shim uses the same marketplace
commands below. For Codex, use the local skill route above, not this installer.

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

## Side by side: what changed in the answer?

One real question, answered on **2026-08-14**: when should a production agent use
Mem0, Letta, or custom memory, and what failures are practitioners reporting?
This is a historical illustration, **not a test of 0.7.0**. No winner was declared.

| What to inspect | ZBS Researcher — saved investigate run | Parallel Ultra — saved answer |
| --- | --- | --- |
| Starting recommendation | Choose who owns durable state; distinguish a memory service from an agent runtime | Also separates the control boundary; proposes a hybrid with an authoritative custom store |
| Practitioner failures | Discusses specific scope/isolation issues, hosted-vs-open-source reproducibility and missing-write reports | Discusses stale/conflicting retrieval, specialized-agent memory requests and context-engineering failures |
| Action derived from evidence | Test write/read scopes and graph boundaries; verify persistence; evaluate the exact deployment tier | Test corrections, contradictions, async completion and abstention; split recall from authoritative state |
| What this answer adds | Issue-specific failure analysis with explicit operational checks | A broader architecture matrix, evaluation literature and a detailed hybrid design |
| What it does not establish | Reddit collection failed; Letta incident sample is thinner; no matched deployment test | Incident prevalence and best product are not established by the cited documentation/issues |
| Inspect the actual text | [Preserved ZBS answer](docs/comparison/researcher.md) | [Preserved Parallel answer](docs/comparison/parallel.md) |

These cells describe the **saved answers**, not independently reverified claims
about today's Mem0 or Letta. [Read the case, exact question and limitations](docs/comparison/README.md).

## Your manual research workflow vs ZBS

This compares responsibilities in the described workflow, not capability ceilings
of Grok, Gemini, Perplexity, ChatGPT or Parallel. A skilled human can perform the
same checks and may produce a better result.

| Work | Manual multi-service workflow | ZBS goal-driven workflow |
| --- | --- | --- |
| Frame the decision | Prepare a prompt and adapt it for each service | Host agent reuses the brief and asks about a missing decision |
| Read different sources | Open chosen services, collect outputs and follow original links yourself | Host agent routes source-specific queries, reads available originals and follows leads |
| Reconcile answers | Compare claims, dates and disagreements yourself | Host agent synthesizes evidence IDs, caveats, contradictions and remaining gaps |
| Preserve the work | Export and organize files yourself | Prepare/finalize maintain project-local raw/, processed/, paired finals and a run index |
| Hand off to another agent | Supply reports and explain their context | Point it to research/INDEX.md and the relevant agent-context.json |
| Verify quality | Depends on the researcher's judgment and access | Still depends on agent judgment and access; structural validation does not establish truth |

For 0.7.0, file organization/export has deterministic and installed-copy checks.
A fresh matched comparison of the current workflow with manual research,
ordinary host web search or other deep-research products remains **not run**.

## Tiers at a glance

- **Tier 0 — free, no keys**: HN, hiring-signal, Polymarket, YouTube *(needs `yt-dlp`)*,
  GitHub, github-issues, Reddit, launch-radar, revenue-radar. Bluesky remains
  available by explicit selection.
- **Tier 1 — your own keys**: LLM lenses Gemini / Grok / Perplexity.
- **Tier 2 — one OpenRouter key**: all three default LLM lenses at once.
- **Opt-in**: direct X via Monid · Bluesky · Telegram · TikTok/IG · Threads · Meta Ads.

The full channel table is in [Connectors](#connectors) below.

**What goes where:** search routes send queries and selected URLs; enabled
cloud transcription also sends audio. Credentials go to the selected provider.
The full per-connector breakdown is in
[CONFIGURATION.md](CONFIGURATION.md#security--transparency--what-it-does-what-it-sends-where).

## What it is (plugin id: `deep-research`)

A research skill usable in Claude Code and through local Codex installation.
The host agent investigates and synthesizes; Python helpers collect source
records, validate evidence and produce the deliverables. The registry currently
has **23 connectors**. The default goal-driven workflow selects only relevant
routes, writes a research plan first and **does not bill Anthropic or OpenAI
APIs by default**. Host account usage and other provider charges are separate.

## Why this one

- **Plan first.** Every run starts by resolving the topic (exact @handles,
  subreddits, repos, whether it's a forecastable event or a hiring-market
  question), writes a short `research-plan.md` into the project-local run,
  and only then executes. No cold keyword blasts or detached plan files.
- **No Anthropic/OpenAI API spend by default.** Retrieval can use Gemini (Google),
  Grok (xAI), and Perplexity plus free direct connectors. Synthesis happens in
  your host agent session. The OpenAI API channel is opt-in.
- **Source metrics.** Direct connectors retain HN points, Polymarket odds,
  GitHub stars/velocity, and a
  **hiring-signal** (how many "Who is hiring?" postings mention your topic —
  a cheap read on whether a skill/trend is heating up).
- **Video evidence.** `youtube-social` retains available transcripts and a bounded
  comment sample. Missing captions remain a gap; separately selected `youtube`
  can use configured local or approved cloud transcription. Transcripts can
  add evidence absent from a particular search result; exclusivity is not assumed.
- **Human and agent output.** The default pair is `playbook.html` and
  `agent-context.json`. Legacy quick scans retain optional `brief.html`.

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
| reddit-web | LLM | Perplexity or OpenRouter *(explicit)* | Reddit URL discovery; model reports, not direct comments |
| reddit-thread | direct | free *(explicit)* | known post and bounded archive comments; gaps possible |
| reddit-live | direct | ScrapeCreators *(explicit, paid)* | one known-post/comments request; no automatic fallback |
| x | direct | Monid *(opt-in, pay-per-use)* | public X posts with author, date, engagement, and canonical link |
| bluesky | direct | free* *(opt-in)* | top posts *(best-effort)* |
| youtube | direct | `yt-dlp`; transcription route dependent | captions or configured local/approved cloud transcription |
| youtube-social | direct | free *(needs `yt-dlp`, explicit)* | available transcripts and bounded comments; no paid audio fallback |
| launch-radar | direct | free (PH slice: free token) | what's shipping — Show HN + yc-oss + DevHunt momentum + category velocity |
| revenue-radar | direct | free | what's selling — Flippa sold prices + Substack bestseller tiers |
| meta-ads | direct | free Meta token | who's paying to advertise — Meta Ad Library (EU scope) |
| telegram | direct | *(opt-in)* own Telegram app creds + session | channel posts + discussion comments — separate research account only |
| tiktok-ig | direct | *(opt-in)* pay-per-use vendor key | TikTok/IG posts + comments — every run costs vendor credits |
| threads | direct | *(key-gated)* free official token or pay-per-use vendor | Threads posts by keyword — official keeps Meta's TOP order, vendor adds engagement counts |

Free default direct channels are zero-config; one OpenRouter key (Tier 2) can drive
all three LLM lenses, plus separately selected transcription. Keys establish
configuration, not spending permission; the goal-driven host reserves approved
spend before each paid request. The `x` connector is separate: it needs `MONID_API_KEY`, discovers
and inspects the current route for free, shows its unit price, and only runs
when explicitly selected with `--fire x` or `--only x`. See
[CONFIGURATION.md](CONFIGURATION.md).

A full **"what it sends where"** breakdown — per-connector endpoints, what
data leaves the machine, and which credential (if any) each channel uses —
is in [CONFIGURATION.md](CONFIGURATION.md#security--transparency--what-it-does-what-it-sends-where).
Search sends queries/URLs; enabled cloud transcription sends audio. The runner
does not call Anthropic, and its OpenAI connector requires explicit selection.
This says nothing about the host session's separate account usage.

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

The default skill workflow calls `research_session.py prepare` once in the
launching project, gathers captures in raw/, writes analysis and dossier in
processed/, then finalizes the HTML/JSON pair and local index. See the
[goal-driven contract](skills/deep-research/references/goal-driven.md).

The commands below are explicit lower-level/legacy tools. Only the legacy
plan-first handoff uses `--prepared-run`; do not apply that allocator to a new
goal-driven run. Direct CLI commands do not enforce the session spending ledger;
check selected routes and approved costs before executing any paid example.

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

# direct public X posts; explicit pay-per-use Monid call
python3 "$SCRIPT" "proposal automation complaints" --fire x \
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

Full goal-driven research stays inside the project that launched it. The helper
creates folders and updates the local index automatically:

```text
<project>/research/
├── INDEX.md                     # entry point for people and future agents
├── index.json                   # local runs, dates, status and result links
└── deep-research-{slug}-{date}[-NN]/
    ├── raw/                     # retained source captures and receipts
    ├── processed/               # agent notes, analysis and extractions
    │   └── dossier.json
    ├── playbook.html            # final human report
    ├── agent-context.json       # final agent data with evidence paths
    ├── artifacts.json           # file roles, sizes and content hashes
    ├── research-layout.json
    ├── research-brief.json
    ├── research-plan.md
    ├── source-readiness.json
    └── spending.json
```

Another agent starts with `research/INDEX.md`, selects a goal/date, and reads
`agent-context.json`. Evidence paths are relative to that run. It can consult
processed notes and raw captures without reconstructing the chat. Partial
coverage, inference and historical dates remain explicit. No global catalog,
server, extra account or subscription is involved. Installing the skill alone
does not start research; preparation/export happen when invoked.

`raw/` can include connector-normalized capture records, not guaranteed original
HTTP bytes or direct verification. Agent paraphrases/conclusions go in processed/.
Sources are untrusted data, never instructions. `prepare` indexes a draft;
`finalize` validates, writes the paired report/inventory and refreshes the index.
Offline `research_session.py index --project-root PROJECT` rebuilds it and flags
missing/inconsistent results. User-owned index files are not silently replaced.
Old goal-driven runs keep their flat dossier; no automatic migration.

Explicit legacy quick-scan/entity workflows retain their older
complete skill-authored bundle:

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

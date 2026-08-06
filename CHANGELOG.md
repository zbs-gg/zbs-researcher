# Changelog

## 0.5.0 — 2026-08-06

YouTube as a real source, three transcription routes, and the first release
published under the ZBS organization.

- **New `youtube` connector (18th channel, free, no key).** Finds videos by
  keyword — or takes a video URL straight from the query, so the investigate
  loop can drill one video it found through another lens. It reads the best
  caption track available (human-written beats auto beats machine-translated),
  **judges** that track, and when the track is missing, a translation of a
  translation, raw unpunctuated ASR, or too sparse for the runtime, it
  transcribes the audio itself. Every video in the report carries an explicit
  provenance label, and when a track is rejected the report says why.
- **That transcript is evidence nothing else has.** A web index reads a video's
  title and description, never the spoken content, so `youtube` enters the
  coverage-receipts table as `partial`. When the transcript came from our own
  Whisper pass it is recorded as `no` — that text provably exists in no index.
  Empty results can never make the claim.
- **Transcription now has three routes, chosen independently of the vision
  profile**: local `mlx-whisper` ($0, Apple silicon, nothing leaves the
  machine), Groq Whisper, and **new: OpenRouter** `/audio/transcriptions` — so
  the single Tier-2 OpenRouter key that already drives the LLM lenses now
  covers audio too. Resolution is explicit env override → the wizard's stored
  answer → derived from profile and configured keys → an honest error naming
  all three. A route you chose explicitly is never silently swapped for
  another provider's bill.
- **The wizard can see the machine.** `detect_state.py` reports OS,
  architecture, RAM, CPU count and (on macOS) the chip name, plus whether
  `mlx-whisper` and `yt-dlp` are installed and which route would run. So on a
  capable Mac the wizard leads with the free local option by name instead of
  only ever pitching a paid key; on hardware that cannot run it, local is not
  offered at all. `--diagnose` prints the machine and the effective route.
  Every probe is individually guarded — a SessionStart hook must never crash a
  session.
- **`yt-dlp` is an optional dependency** (binary on PATH, else the Python
  package), the same tier as Telethon and MLX. Without it the channel writes
  `youtube.ERROR.md` with install guidance and every other channel is
  unaffected. It is not replaceable with a plain HTTP call: YouTube's
  `timedtext` endpoint is PoToken-gated and returns an empty body to
  unauthenticated programmatic requests.
- **The npm package moved to the ZBS organization's scope:**
  `zbs-researcher` → **`@zbs-gg/zbs-researcher`**, so the install command now
  reads `npx -y @zbs-gg/zbs-researcher@latest` and matches the GitHub slug the
  installer already uses (`claude plugin marketplace add zbs-gg/zbs-researcher`).
  npm has no `org/name` form — only a scope shows the owner in the name. The
  old unscoped `zbs-researcher` has been unpublished; `0.1.0` can never be
  republished under that name, which is the accepted cost of removing it.
- Housekeeping: plugin, marketplace and npm installer versions are one number
  again (0.5.0 — they had drifted to 0.4.0/0.1.1); plugin and marketplace
  ownership moved from the personal account to the ZBS organization; the
  installer gained `publishConfig`, `homepage` and `bugs` so publishing no
  longer depends on local npm state.

## 0.4.0 — 2026-07-23

Two new deep-research modes alongside the default broad-scan `single` mode — the
edge is QUALITY: native, full-breadth social/community depth, not price.

- **`--mode entity-fanout`** — real deep research instead of one blanket query
  per channel: enumerate the top-N entities for a topic (GitHub top-by-stars +
  HN mentions, per-source degrade; an LLM lens enriches / is required for
  non-repo topics), then fan out **per entity** across the channels into an
  entity×channel dossier matrix. Hybrid tiering: free channels on all N
  entities, paid LLM lenses on the top-K only (`--paid-all` lifts + raises the
  budget). Bounded `ThreadPoolExecutor` concurrency, per-host reddit/bluesky
  backoff, per-cell `ERROR.md` degrade, and an honest cost/time manifest with a
  `degraded` flag — never "$0 / 40s". `--dry-run` previews the entity list +
  call budget for free.
- **`--mode investigate`** — the flagship: a session-driven, question-driven
  agentic loop. Compose short, target-scoped queries per source (never a
  blanket sentence), `--fire <source>` one at a time, read + drill adaptively,
  then synthesize a problems-first landscape report with a real quote + author
  handle + clickable live link behind every load-bearing claim. Reads the
  platforms from inside (live X via Grok, Telegram client-session, the full
  Reddit archive) where a web-index researcher sees only the indexed scraps.
- **Coverage-receipts** (`--coverage RUN_DIR`) mark, from real provenance,
  what a web-index researcher would miss (Telegram with no web footprint,
  fresh pre-index X, deep Reddit archive) — truthful, never inferred.
- **Compound feedback loop**: `--feedback` saves your notes + composed queries
  to a local ledger the next run reads (honest — a save, not learning), with an
  opt-in Cartographer relay (`DEEP_RESEARCH_CARTOGRAPHER_URL`, https-only,
  failure-tolerant) for cross-run profile compounding.
- **Eval harness** (`eval_harness.py`) — head-to-head on your own data: Beast
  vs a free web-index `site:` baseline, scored on primary-source depth,
  freshness, and social-coverage.
- Positioning is quality: "free / cheaper" is a property, not the pitch.

## 0.3.0 — 2026-07-21

ZBS Researcher: persona, CLI polish, npx installer, showcase.

- **ZBS Researcher persona** (brand-only — plugin id stays
  `deep-research`): the wizard introduces itself by name and asks at most two
  persona questions (gender of address + tone preset), both skippable, only
  after the $0 Tier-0 proof. Choice persists in `onboarding.json` as a
  `persona` object; voicing rules pin that tone changes intonation and
  sign-off only — never findings, rankings, or honesty notes.
- **`term_ui` banner + live progress board** in the runner CLI: ASCII banner
  and an animated per-connector board (spinner, status, elapsed) — rendered
  ONLY in a real TTY. Non-TTY / `NO_COLOR` / `CI` / `TERM=dumb` output stays
  byte-compatible with the previous plain per-channel lines.
- **npx installer** `zbs-researcher`: one command
  (`npx -y zbs-researcher@latest`) detects the `claude` CLI, adds the
  marketplace, installs the plugin, and prints next steps. Prepared here;
  npm publication is a separate manual action.
- **Marketplace renamed** `deep-research-skill` → `zbs-researcher` (plugin id
  unchanged). Migration: installs registered under the old marketplace name
  should re-add it as `zbs-gg/zbs-researcher`.
- **Showcase docs**: README showcase top, `docs/demo-script.md` (demo-video
  shot list), `docs/site-brief.md` (hand-off brief for an external site
  effort).

## 0.2.0 — 2026-07-15

Unreleased package update for project-local research ownership.

- Skill runs now reserve one unique
  `<project>/research/deep-research-{slug}-{date}[-NN]/` directory and write
  `research-plan.md` before starting connectors.
- Raw reports, `manifest.json`, session-authored `synthesis.md`, and optional
  `brief.html` are colocated with the plan instead of using detached global
  defaults.
- Direct CLI runs allocate project-local raw-evidence bundles by default;
  `--project-root` narrows monorepo ownership and explicit `--output-dir`
  destinations remain supported.
- Probe and render-only operations remain read-only with respect to run
  allocation, and deterministic path/documentation/version checks now run in
  the no-paid-API selftest.
- Ambiguous or malformed legacy CLI shapes now fail before allocation:
  positional topic plus `--topic`, `--only` plus `--skip`, unknown connector
  names, malformed `--q`, blank explicit paths, `--html-out` without render,
  and `--allocate-run` combined with raw-run options. Use one topic form, one
  connector selector, non-blank paths, and a separate allocation call.
- Skill commands resolve the runner from the host-discovered `SKILL.md`
  directory, so Codex does not depend on Claude's `CLAUDE_PLUGIN_ROOT`.
- Skill allocation now stamps `_topic.txt`; the subsequent connector call uses
  `--prepared-run` to require that exact topic, a non-empty plan, and no prior
  raw artifacts, then atomically claims the directory against concurrent or
  stale reuse. Reusing plain `--output-dir` remains an explicit low-level
  compatibility behavior.
- Skill commands also pass the captured directory through `--launch-cwd`, so
  ownership does not change if an agent's process cwd drifts between tool calls.

## 0.1.0 — 2026-07-08

Initial plugin packaging of the deep-research skill.

- **10 connectors**: gemini, grok, perplexity, openai *(opt-in)* + hackernews,
  hiring, polymarket, github, reddit, bluesky.
- **Plan-first STEP 0** — a research plan (topic resolution, channel choice,
  per-channel queries, expected contradictions) precedes every run.
- **No Anthropic/OpenAI API spend by default** — retrieval on Gemini/Grok/
  Perplexity + free direct connectors; synthesis in the Claude Code session;
  `openai` channel is opt-in.
- **Hiring-signal connector** — counts "Who is hiring?" postings mentioning a
  topic (job-market hotness) with sample companies.
- **Polymarket** via `/public-search` (real text search, not top-100 by volume).
- **Self-contained HTML brief** renderer (`--render-html`), no external deps.
- Per-run `manifest.json`; each channel degrades to `ERROR.md` on failure
  without killing siblings.
- `${CLAUDE_PLUGIN_ROOT}` paths and `DEEP_RESEARCH_SECRETS_DIR` override for
  portability; env-var keys supported as a fallback to secret files.

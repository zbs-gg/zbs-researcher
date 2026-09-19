# Changelog

## 0.7.0 — 2026-09-19

Prepared 2026-09-05; publication authorized 2026-09-19. The GitHub plugin and npm
installer are separate distribution channels; see installer/RELEASE.md for status.

### Project-local research storage

- New goal-driven runs separate raw captures and processed analysis; the working
  dossier lives in processed/dossier.json. Final HTML/JSON stay at run root.
- Preparation/export maintain research/INDEX.md and index.json inside the
  launching project only; artifacts.json records file roles, sizes and hashes.
- Offline index rebuild detects changed dossiers/inventories and broken exports.
  User index conflicts and symlink escapes fail closed; flat legacy runs remain
  compatible without migration. No new service or provider charges.

### Goal-driven research and auditable sources

- **Goal-driven bilingual research and two deliverables.** The skill now starts
  from the decision, supplied links, source languages and approved budget;
  checks needed services offline; and follows seeds, leads and contradictions.
  `research_session.py` validates source references, direct-vs-model evidence,
  coverage, action support and paths, then exports an offline `playbook.html`
  and matching `agent-context.json`. Partial access stays visibly partial.
- **Read social evidence, preserve limits.** Explicit `reddit-web`,
  `reddit-thread`, `reddit-live` and `youtube-social` routes add citation-led
  discovery, known-post comments and bounded YouTube replies. Social video
  reading cannot silently bill audio transcription. Grok/Perplexity retain
  returned source/tool metadata, use current-date prompts, and xAI cost ticks
  normalize to actual USD. Legacy runner modes stay available. Existing
  installations need an update to load the new workflow.

- **Explicit public X source through Monid.** `--fire x` and `--only x` now
  discover and inspect an allowlisted Monid route, announce its quoted unit
  price before the paid run, preserve actual billing only when returned, and
  render auditable posts with canonical links. It is default-off and never a
  hidden fallback for a failed Grok/xAI or OpenRouter call. Bluesky is also
  default-off but remains explicitly selectable. Configuration docs now
  distinguish a standard xAI API key from supported SuperGrok OAuth clients.
- **Auditable investigate calls.** `--fire` now retains provider routing,
  timing, token usage, and actual vendor cost fields when available. Paid HTTP
  reads have a portable total wall-clock deadline; timeouts keep a private
  atomic error and cost-unavailable receipt. Fires into one run directory are
  serialized across processes, and the private manifest is replaced atomically,
  preventing slow paid calls from losing or overwriting each other's receipts.
- **Private five-question duel controller.** The first official Researcher vs
  Parallel benchmark now has a frozen English suite and `init`,
  `snapshot-researcher`, `run-parallel`, `blind`, and `report` commands. It
  preserves raw attempts, gates current-price acknowledgment separately from
  per-call paid consent, allows only technical retries, and fails closed on
  incomplete blind audits or scores. Runtime answers stay ignored and private;
  nothing is published or merged automatically.
- **Fail-closed duel accounting and claim audit.** Researcher snapshots now
  reconcile every paid call receipt to an actual, estimated, or conservative
  unavailable USD amount before applying the USD 10 cap. Blind audits now use
  a validated claim ledger with citation fit, fact date, freshness, support
  status, and an evidence note. Every runtime directory is mode `0700` on POSIX.
- **Paid Parallel baseline, explicit only.** A stored researcher run can now be
  compared with Parallel's Task API on the same depth, freshness, and native
  social axes. `--baseline parallel` is the only activation path; a configured
  key alone never spends. The CLI names the selected processor and verified
  list price before the call, restricts selection to the priced pro/ultra
  deep-research variants, and persists that price basis in `eval-log.jsonl`.
- **Reproducible paid-run receipts.** Optional `--artifact-dir` persistence now
  keeps the full Parallel response, readable answer, normalized counted and
  excluded citations, run ID/state/timing, processor, and published price
  basis. Bundle paths stay relative; files are atomically written with private
  permissions and scrubbed of keys and personal absolute paths.
- **Honest comparison failures.** Missing keys, failed starts, timeouts, and
  empty results remain explicit unavailable states while the researcher side
  is still scored. Parallel's undated citations remain `unknown`, never
  artificially fresh or zero.
- **Two real-duel scorer fixes.** Structured citation lists (`excerpts`) now
  count like singular excerpts without duplicate inflation, and corporate
  help/docs/blog pages on social domains no longer masquerade as native social
  conversation. YouTube spoken-content evidence is counted consistently with
  the existing provenance model.
- **Claims are dated and graded before synthesis.** Investigate now decomposes
  vague human questions, marks load-bearing claims T1-T4 using the date of the
  fact, bars T4 from support, and moves claims older than 12 months without
  current T1/T2 confirmation into an explicit stale/historical section.
- **Spec Kit initialized.** The repository carries a versioned constitution,
  living spec/plan/tasks, and Codex workflow skills. Originally implemented
  before this version bump.

### Installation and comparison

- Local Codex skill installation uses the existing account; the npm shim remains
  a Claude Code installer. README distinguishes these routes and published state.
- A dated, same-question ZBS/Parallel comparison includes preserved answer text,
  source/excerpt hashes, strengths and limitations. It is a historical example,
  not a fresh 0.7.0 benchmark or a completed blind evaluation.

## 0.6.0 — 2026-08-09

Research that checks whether an answer is true, not just whether it sounds good.

- **Claim grading and a staleness pass** (`SKILL.md` STEP I3.5). Every
  load-bearing claim now carries the date of the FACT (not the page) and a
  proof tier T1-T4, where T4 — clickbait, undated, unattributed — may be cited
  only to be knocked down. A claim older than 12 months without fresh
  confirmation cannot be load-bearing. Reports gain a mandatory "what people
  repeat that is no longer true" section.
- **Vague questions are taken as given** (STEP I-1). The loop decomposes
  "how do I run a Twitter account now" into then / now / what-changed itself
  instead of asking for a better-formed query. A tool that needs a clean query
  is a search box.
- **Parallel deep research as an opt-in baseline** in the eval harness
  (`--baseline parallel`). A configured key is never consent to spend it: the
  default stays the free web-index pass, and the harness says so.
- Scorer fixes found by running a real duel: the live API's `excerpts` field
  was being dropped (scoring an opponent's quotes at zero), and a platform's
  own help centre counted as reaching that platform natively. Both corrected
  against our own interest.

Field-tested on "как вести твиттер сейчас": five assistants disagreed about
X's ranking weights; the loop opened `xai-org/x-algorithm` and established that
the weight constants are referenced but never defined in the public code — so
the exact coefficients circulating in guides are unsupported by the source they
cite.

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

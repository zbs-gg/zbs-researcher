# zbs-researcher — Claude Code project instructions

Deep-research Claude Code plugin (skill `deep-research`): a multi-channel research runner — LLM lenses (Gemini/Grok/Perplexity, OpenAI opt-in, OpenRouter Tier-2) + direct connectors (HN, hiring, Polymarket, GitHub, github-issues, Reddit via Arctic-Shift, launch-radar, revenue-radar, Meta Ads, Telegram, TikTok/IG, Threads; Bluesky opt-in; public X via Monid opt-in/pay-per-use) + a conversational onboarding wizard.

**Three research modes** (`--mode`, plus a session playbook): `single` (broad-scan, one blanket query per channel), `entity-fanout` (enumerate top-N entities → per-entity fan-out matrix), and **`investigate`** — the flagship, **the forced default**: a session-driven agentic loop (compose short target-scoped queries per source → `--fire` → read → drill → problems-first synthesis) that reads the platforms from inside. **The product thesis: beat a web-index researcher (Parallel AI) on QUALITY — native full-breadth social/community depth + auditable primary evidence. "Free/cheaper" is NOT the pitch.** Always default to the deepest `investigate` mode unless the user explicitly asks for a quick scan.

## Operating contract (how to work in this repo)

**Current full-research entry (0.7.0, feature 004):** read
`skills/deep-research/references/goal-driven.md` after the loaded skill. Clarify
the decision only if missing; reuse supplied links/languages/budget, check only
needed services, investigate RU/EN sources and export `playbook.html` plus
`agent-context.json` from one validated dossier. The host agent remains the
reasoning loop. Do not promise complete platform access or a benchmark win.
Legacy wizard/quick-scan artifacts remain compatibility paths, not a second
intake to run after goal-driven preparation. No paid fallback is implicit.

**Project-local storage (0.7.0, feature 005):** new runs separate received
captures in raw/ from agent processing in processed/; the working dossier is
processed/dossier.json. The final pair stays at run root. Preparation/export
maintain only this project's research/INDEX.md and index.json; export adds a file
inventory. Reuse starts at the index, then agent-context.json with dates and
limits retained. No global catalog, root AGENTS.md edits or legacy migration.
Folder placement is not proof of direct retrieval; preserve old flat dossiers.

**Release/comparison boundary (feature 006):** version metadata is 0.7.0;
distribution status is recorded in installer/RELEASE.md. docs/comparison uses a historical 2026-08-14 pair,
not a new-version win. Original private benchmark records and pending owner
judgments remain unchanged. Public comparisons must retain dates and limits.

The same skill also supports local Codex installation as documented
in README. That route uses the existing Codex account and the offline prepare
check, not the Claude marketplace installer or SessionStart hook. Keep host
account usage distinct from connector API spend and record live qualification
per host; a Claude cache smoke does not establish Codex execution or vice versa.

This project is Nikita's proving ground for beating Parallel on research quality. The bar is high; do not take the easy path.

- **Spec Kit, always for new non-trivial work.** Use the repository-local workflow in `.agents/skills`: constitution → spec → plan → tasks → analyze → implementation → adversarial diff review. Older `docs/plans/` remain historical evidence; do not rewrite them into pretend-current plans. Plan-first, tests-always. A change without a living spec + tests + review is not done.
- **No shortcuts.** Never ship the easy version to close the task. If a real fix is bigger, say so and do it — or surface the tradeoff explicitly. Corner-cutting here is the failure mode to avoid.
- **Ignore the skill soup.** Use the local Spec Kit workflow and only task-relevant technical skills. Do NOT reach for unrelated global skills (personal/creative/marketing skills, the reflexive "invoke a skill first" habit) — they add context noise, not value, in this repo.
- **Land via PR to `origin/main`** (branch off `origin/main` — see [[two-unrelated-git-histories]]); merge/push/publish (npm, version bumps) are outward actions that need Nikita's explicit go.
- **Verify before claiming done:** full unittest suite green (`python3 -m unittest discover -s tests` from `skills/deep-research`) + `bash scripts/selftest.sh` 10/10 + no paid calls in tests.

## Repo map

- `skills/deep-research/SKILL.md` — the skill + onboarding wizard (STEP flow).
- `skills/deep-research/scripts/deep-research.py` — the runner: `Connector` registry, `KEYS`/`read_key()`, channels, ranking helpers, `--diagnose`, `--signal`, `--list-connectors`.
- `skills/deep-research/scripts/connectors/` — the connectors package (late-binding via `attach_runner`; shared helpers in `__init__.py`).
- `skills/deep-research/scripts/detect_state.py` — SessionStart hook (registered in the root `hooks/hooks.json`): emits JSON with boolean providers, never prints key values.
- `skills/deep-research/scripts/research_session.py` — offline intake, coverage/evidence validation, budget reservations and paired export; `playbook.py` — escaped offline HTML renderer.
- `skills/deep-research/scripts/connectors/reddit_research.py` — Perplexity discovery plus targeted archive/explicit paid live comments; `youtube-social` — captions/comments without paid audio fallback.
- `skills/deep-research/scripts/entity_fanout.py` — entity-fanout mode (enumerate → per-entity fan-out → matrix).
- `skills/deep-research/scripts/provenance.py` — web-index reachability + coverage-receipts (investigate mode).
- `skills/deep-research/scripts/investigate_feedback.py` — feedback ledger + Cartographer soft-plug; `eval_harness.py` — Beast vs free web-index or explicitly selected paid Parallel baseline; `duel_benchmark.py` — private five-question init/snapshot/paid-gate/blind/report controller.
- `skills/deep-research/tests/` — unittest suite.
- `specs/` — living Spec Kit feature artifacts; active feature is selected in `.specify/feature.json`.
- `docs/plans/` — historical pre-Spec-Kit plans, including investigate and entity-fanout.

## How to run checks

```bash
cd skills/deep-research
python3 -m unittest discover -s tests -p 'test_*.py'   # the whole suite
bash scripts/selftest.sh                                # 10-step smoke, does not call paid APIs
```

**Never run `unittest discover` from the repo root** — the global site-packages contains a foreign `tests` package that shadows ours.

## Hard rules

- **Budget invariant (R17):** the default run does not hit the Anthropic/OpenAI API; OpenAI is opt-in only. Paid calls (OpenRouter, vendors) never happen in tests, and at runtime only when keys are explicitly configured. Parallel additionally requires the per-run `--baseline parallel`; a stored key alone is never consent to spend.
- **Stdlib-only** (urllib, threading). Telethon/MLX are lazy optional imports only; `yt-dlp` is an optional external tool the youtube channel degrades without.
- **Windows-safe (R18):** no `signal.SIGALRM`, `os.killpg`, `fcntl`, `pty`, `os.fork`; threading only. Selftest greps for this.
- **Secrets:** keys come via `DEEP_RESEARCH_SECRETS_DIR` (default `~/.config/zbs-researcher/secrets`) or env; no key material in outputs, logs, or error messages.
- **Skill documentation selftest:** active SKILL.md stays under 500 lines and routes full research to `references/goal-driven.md`, with the HTML/JSON pair and budget/evidence contract. Legacy plan/investigate/claim markers remain ordered in `references/legacy-workflow.md`; that optional reference is not loaded for new goal-driven research. The literal `${CLAUDE_PLUGIN_ROOT}` remains forbidden in skill commands (but required in hooks). Preserve legacy raw-mode compatibility without reintroducing a second mandatory intake.
- Graceful degrade: a channel fails → `<name>.ERROR.md`, its neighbors keep going. Do not break this pattern.

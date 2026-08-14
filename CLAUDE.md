# zbs-researcher — Claude Code project instructions

Deep-research Claude Code plugin (skill `deep-research`): a multi-channel research runner — LLM lenses (Gemini/Grok/Perplexity, OpenAI opt-in, OpenRouter Tier-2) + free direct connectors (HN, hiring, Polymarket, GitHub, github-issues, Reddit via Arctic-Shift, Bluesky, launch-radar, revenue-radar, Meta Ads, Telegram, TikTok/IG, Threads) + a conversational onboarding wizard.

**Three research modes** (`--mode`, plus a session playbook): `single` (broad-scan, one blanket query per channel), `entity-fanout` (enumerate top-N entities → per-entity fan-out matrix), and **`investigate`** — the flagship, **the forced default**: a session-driven agentic loop (compose short target-scoped queries per source → `--fire` → read → drill → problems-first synthesis) that reads the platforms from inside. **The product thesis: beat a web-index researcher (Parallel AI) on QUALITY — native full-breadth social/community depth + auditable primary evidence. "Free/cheaper" is NOT the pitch.** Always default to the deepest `investigate` mode unless the user explicitly asks for a quick scan.

## Operating contract (how to work in this repo)

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
- **SKILL.md selftest contract:** the first occurrences of the markers `## STEP 0 — RESEARCH PLAN` → `--allocate-run` → `research-plan.md` → `--output-dir "$RUN_DIR"` → `synthesis.md` must appear in this order; the investigate markers `INVESTIGATE MODE` → `NEVER fire a blanket` → `--fire` → `--coverage` → `--feedback` stay ordered; and claim handling stays `STEP I-1 — DECOMPOSE` → `STEP I3.5 — DATE AND GRADE EVERY CLAIM` → fact date → T4 → 12-month staleness → `STEP I4 — SYNTHESIZE`. The literal `${CLAUDE_PLUGIN_ROOT}` is forbidden in SKILL.md (but required in `hooks/hooks.json`). Positioning markers `not the pitch — quality is` (SKILL + README) and `saved locally to inform the next run` (SKILL) must stay present.
- Graceful degrade: a channel fails → `<name>.ERROR.md`, its neighbors keep going. Do not break this pattern.

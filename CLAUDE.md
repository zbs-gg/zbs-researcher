# zbs-research — Claude Code project instructions

Deep-research Claude Code plugin (skill `deep-research`): a multi-channel research runner — LLM lenses (Gemini/Grok/Perplexity, OpenAI opt-in, OpenRouter Tier-2) + free direct connectors (HN, hiring, Polymarket, GitHub, github-issues, Reddit via Arctic-Shift, Bluesky, launch-radar, revenue-radar, Meta Ads, Telegram, TikTok/IG, Threads) + a conversational onboarding wizard.

## Repo map

- `skills/deep-research/SKILL.md` — the skill + onboarding wizard (STEP flow).
- `skills/deep-research/scripts/deep-research.py` — the runner: `Connector` registry, `KEYS`/`read_key()`, channels, ranking helpers, `--diagnose`, `--signal`, `--list-connectors`.
- `skills/deep-research/scripts/connectors/` — the connectors package (late-binding via `attach_runner`; shared helpers in `__init__.py`).
- `skills/deep-research/scripts/detect_state.py` — SessionStart hook (registered in the root `hooks/hooks.json`): emits JSON with boolean providers, never prints key values.
- `skills/deep-research/tests/` — unittest suite.
- `docs/plans/2026-07-17-002-feat-zbs-research-onboarding-wizard-plan.md` — the active plan (unified plan, R1–R23, U1–U15).

## How to run checks

```bash
cd skills/deep-research
python3 -m unittest discover -s tests -p 'test_*.py'   # the whole suite
bash scripts/selftest.sh                                # 10-step smoke, does not call paid APIs
```

**Never run `unittest discover` from the repo root** — the global site-packages contains a foreign `tests` package that shadows ours.

## Hard rules

- **Budget invariant (R17):** the default run does not hit the Anthropic/OpenAI API; OpenAI is opt-in only. Paid calls (OpenRouter, vendors) never happen in tests, and at runtime only when keys are explicitly configured.
- **Stdlib-only** (urllib, threading). Telethon/MLX are lazy optional imports only.
- **Windows-safe (R18):** no `signal.SIGALRM`, `os.killpg`, `fcntl`, `pty`, `os.fork`; threading only. Selftest greps for this.
- **Secrets:** keys come via `DEEP_RESEARCH_SECRETS_DIR` (default `~/.config/zbs-research/secrets`) or env; no key material in outputs, logs, or error messages.
- **SKILL.md selftest contract:** the first occurrences of the markers `## STEP 0 — RESEARCH PLAN` → `--allocate-run` → `research-plan.md` → `--output-dir "$RUN_DIR"` → `synthesis.md` must appear in this order; the literal `${CLAUDE_PLUGIN_ROOT}` is forbidden in SKILL.md (but required in `hooks/hooks.json`).
- Graceful degrade: a channel fails → `<name>.ERROR.md`, its neighbors keep going. Do not break this pattern.

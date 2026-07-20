# zbs-research — Claude Code project instructions

Deep-research Claude Code plugin (skill `deep-research`): многоканальный ресёрч-раннер — LLM-линзы (Gemini/Grok/Perplexity, OpenAI opt-in, OpenRouter Tier-2) + бесплатные direct-коннекторы (HN, hiring, Polymarket, GitHub, github-issues, Reddit via Arctic-Shift, Bluesky, launch-radar, revenue-radar, Meta Ads, Telegram, TikTok/IG, Threads) + разговорный onboarding-мастер.

## Карта репо

- `skills/deep-research/SKILL.md` — скилл + onboarding-мастер (STEP-флоу).
- `skills/deep-research/scripts/deep-research.py` — раннер: реестр `Connector`, `KEYS`/`read_key()`, каналы, ranking-хелперы, `--diagnose`, `--signal`, `--list-connectors`.
- `skills/deep-research/scripts/connectors/` — пакет коннекторов (late-binding через `attach_runner`; общие хелперы в `__init__.py`).
- `skills/deep-research/scripts/detect_state.py` — SessionStart-хук (регистрируется в корневом `hooks/hooks.json`): JSON с булевыми провайдерами, никогда не выводит значения ключей.
- `skills/deep-research/tests/` — unittest-сьюита.
- `docs/plans/2026-07-17-002-feat-zbs-research-onboarding-wizard-plan.md` — действующий план (unified plan, R1–R23, U1–U15).

## Как запускать проверки

```bash
cd skills/deep-research
python3 -m unittest discover -s tests -p 'test_*.py'   # вся сьюита
bash scripts/selftest.sh                                # 10-шаговый smoke, платные API не вызывает
```

**Никогда не запускай `unittest discover` из корня репо** — глобальный site-packages содержит чужой пакет `tests`, который затеняет наш.

## Жёсткие правила

- **Бюджет-инвариант (R17):** дефолтный запуск не бьёт в Anthropic/OpenAI API; OpenAI — только явный opt-in. Платные вызовы (OpenRouter, вендоры) — никогда в тестах, в рантайме только при явно настроенных ключах.
- **Stdlib-only** (urllib, threading). Telethon/MLX — только ленивые опциональные импорты.
- **Windows-safe (R18):** никаких `signal.SIGALRM`, `os.killpg`, `fcntl`, `pty`, `os.fork`; только threading. Selftest это грепает.
- **Секреты:** ключи через `DEEP_RESEARCH_SECRETS_DIR` (дефолт `~/elle/.secrets`) или env; никакого ключевого материала в выводах, логах и сообщениях об ошибках.
- **SKILL.md контракт selftest:** первые вхождения маркеров `## STEP 0 — RESEARCH PLAN` → `--allocate-run` → `research-plan.md` → `--output-dir "$RUN_DIR"` → `synthesis.md` обязаны идти в этом порядке; литерал `${CLAUDE_PLUGIN_ROOT}` в SKILL.md запрещён (в `hooks/hooks.json` — обязателен).
- Graceful degrade: канал падает → `<name>.ERROR.md`, соседи продолжают. Не ломать этот паттерн.

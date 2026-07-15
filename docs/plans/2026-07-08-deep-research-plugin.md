# feat: deep-research → устанавливаемый Claude Code плагин

Задача: превратить наш deep-research skill (SKILL.md + deep-research.py) в самостоятельный устанавливаемый плагин с marketplace-структурой, как mvanhorn/last30days-skill.
Контекст: сейчас скилл живёт распределённо — SKILL.md в `~/.claude/skills/deep-research/`, скрипт в `~/OpenClawWorkspace/scripts/research/`. Не портируемо, не устанавливается, не версионируется.
Loop-first: сигнал — `claude plugin validate` зелёный + `/deep-research:research` работает из установленного плагина; источник — selftest.sh + ручной прогон; критерий — устанавливается на чистой машине и гоняет бесплатные каналы; ингест — отчёт + план-outcome.

## Подход и почему

**Место:** `~/dev/__PROJECTS/deep-research-skill/` — свой git-репо ВНЕ ~/elle (правило no-root-dump: плагин = публикуемый продукт, не инфра харнесса). Имя репо по образцу Вана (`last30days-skill`), plugin `name: deep-research` → namespace `/deep-research:research`.

**Схема плагина (подтверждена по docs + реальному last30days):**
- ТОЛЬКО `plugin.json` внутри `.claude-plugin/`; всё остальное (`skills/`, scripts) — в корне плагина.
- `.claude-plugin/marketplace.json` с `source: "./"` делает репо самостоятельным marketplace → `/plugin marketplace add <repo>` затем `/plugin install deep-research`.
- Скрипт кладём внутрь плагина; в SKILL.md пути через `${CLAUDE_PLUGIN_ROOT}` (портируемо на любой машине).

**Секреты (портируемость без утечки):** скрипт уже читает env vars как fallback. Обобщаем: путь секрет-дира = `DEEP_RESEARCH_SECRETS_DIR` (default `~/.openclaw/secrets` — у Ника работает как есть; у чужих — env `GEMINI_API_KEY` и т.д.). Ключи Ника НЕ попадают в репо (.gitignore + скрипт хранит ключи в коде — нет, только читает).

**Целевое дерево:**
```
deep-research-skill/
├── .claude-plugin/
│   ├── plugin.json          — name, version 0.1.0, desc, author, license, keywords
│   └── marketplace.json     — self-hosted marketplace, source "./"
├── skills/deep-research/
│   ├── SKILL.md             — наш скилл, пути → ${CLAUDE_PLUGIN_ROOT}
│   └── scripts/
│       ├── deep-research.py — наш скрипт + DEEP_RESEARCH_SECRETS_DIR
│       └── selftest.sh      — smoke: --list-connectors + free HN/hiring
├── README.md                — что/чем отличается/установка/quickstart/таблица коннекторов
├── CONFIGURATION.md         — ключи: что free, что нужен ключ, env-имена, куда класть
├── CHANGELOG.md             — 0.1.0
├── LICENSE                  — MIT
└── .gitignore               — секреты, output-dirs, __pycache__
```

## Шаги (атомарные)
1. [ ] `mkdir -p ~/dev/__PROJECTS/deep-research-skill/{.claude-plugin,skills/deep-research/scripts}`; `git init`
2. [ ] `plugin.json` + `marketplace.json` (по образцу last30days, наши поля)
3. [ ] Перенести `deep-research.py` в `skills/deep-research/scripts/`; добавить `DEEP_RESEARCH_SECRETS_DIR` override (default сохраняет поведение у Ника)
4. [ ] Перенести SKILL.md в `skills/deep-research/`; заменить пути на `${CLAUDE_PLUGIN_ROOT}/skills/deep-research/scripts/deep-research.py`
5. [ ] `selftest.sh` — прогон бесплатных каналов, exit-код по результату
6. [ ] README.md + CONFIGURATION.md + CHANGELOG.md + LICENSE(MIT) + .gitignore
7. [ ] Верификация: `claude plugin validate`; `--list-connectors`; selftest; git-scan на утечку ключей
8. [ ] git commit (локально). Первый коммит на ветке, не в public remote.

## Критерии приёмки
- [ ] `claude plugin validate` в папке плагина → OK
- [ ] `python3 skills/deep-research/scripts/deep-research.py --list-connectors` → 10 коннекторов
- [ ] `selftest.sh` зелёный (free-каналы отдают контент)
- [ ] `grep -rE 'AIza|xai-|sk-|pplx-' --include=*.py --include=*.md` по репо → 0 реальных ключей
- [ ] README покрывает установку и plan-first + бюджет-инвариант

## Развилки (call-outs — нужен ответ Ника)
1. **Публикация.** РЕКОМЕНДУЮ: собрать локально + поставить через `--plugin-dir`/локальный marketplace; публичный GitHub-пуш — отдельным шагом по явному «да» (outward-facing, external-ship-gate). Альтернативы: сразу публичный GitHub / только локально без git.
2. **Автор в манифесте** (для будущей публикации): default `Nikita Shilov` + github `nkkmnk`. Бренд ZBS в паблике не форсим (канон: РФ-каналы = «ИИ-лаборатория Никиты Шилова»); для англо-GitHub — имя Ника. Assumption, поправимо.
3. **Судьба локального `~/.claude/skills/deep-research`.** РЕКОМЕНДУЮ оставить пока (рабочее), убрать после проверки плагина — иначе дубль `/deep-research` vs `/deep-research:research`.

## Риски / отложено на исполнение
- `${CLAUDE_PLUGIN_ROOT}` в skill-bash — проверить живьём при установке (docs подтверждают для hooks/mcp; для skill-инструкций валидирую на прогоне).
- Не-цели v1: Go MCP-бандл, TikTok/IG (ScrapeCreators), GitHub Actions CI, большой тест-корпус — фаза 2, если Ник захочет реальную публикацию.

Outcome: ✅ Сделано (2026-07-08). Репо `~/dev/__PROJECTS/deep-research-skill/`, git main @ed63ee7 (локально, без публикации — по выбору Ника).
Верификация: `claude plugin validate` ✔ passed; selftest ✔ (10 коннекторов, free-каналы, HTML self-contained, ноль платных API); key-leak scan ✔ чисто; оба JSON валидны.
Установлен: `claude plugin marketplace add ~/dev/__PROJECTS/deep-research-skill` + `install deep-research@deep-research-skill` → v0.1.0 scope user. Активируется как `/deep-research:deep-research` в новой сессии.
Отклонения от плана: скрипт правил не переносом а прямой правкой SECRETS (env-override DEEP_RESEARCH_SECRETS_DIR); output-dir пример в SKILL depersonalized (~/research вместо ~/OpenClawWorkspace).
Осталось (по команде Ника): (1) публичный GitHub-пуш через external-ship-gate + depersonalize текста (упоминания Nik/~/elle в SKILL); (2) убрать локальный дубль `~/.claude/skills/deep-research` после проверки плагина; (3) фаза 2 — CI/тесты/TikTok-IG если пойдёт в паблик.

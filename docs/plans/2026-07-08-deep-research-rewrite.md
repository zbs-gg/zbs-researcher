# План: переписать /deep-research — plan-first + 9 коннекторов + HTML

**Дата:** 2026-07-08
**Триггер:** Ник — «когда вызываешь ресёрч → СНАЧАЛА план ресёрча, потом запуск; добавить недостающие коннекторы; переписать скилл, DO больше не существует».
**Файлы:** `~/OpenClawWorkspace/scripts/research/deep-research.py`, `~/.claude/skills/deep-research/SKILL.md`

## Loop-first (4 вопроса)
1. **Сигнал:** скрипт `--list-connectors` отдаёт JSON живых каналов; `--render-html` даёт бриф; smoke-прогон каждого канала пишет непустой .md или ERROR.md.
2. **Источник:** stderr-лог per-channel (OK/ERROR + chars), manifest.json в output-dir.
3. **Критерий «работает»:** ≥2 zero-config коннектора (HN, Polymarket, GitHub) отдают контент без ключей; LLM-каналы отдают при наличии ключа; HTML открывается self-contained.
4. **Ингест:** отчёт Нику + этот план как контрольная точка.

## Что подтверждено живьём (smoke-тест 08-07)
- HN Algolia (https) ✓ · Polymarket gamma ✓ · GitHub (gh) ✓ · Perplexity ключ валиден ✓
- Reddit `.json` душится (HTML вместо JSON) · Bluesky 403 в sandbox → оба best-effort с degrade
- python `markdown` модуля нет → свой мини-конвертер (no deps, urllib-only стиль сохраняем)
- БАГ: скрипт читает `openai.txt`, реальный файл `openai-api-key.txt` → OpenAI-канал молча падал на env
- Миграция кода с DO УЖЕ сделана (ходит в api.openai.com); устарела только заметка в SKILL.md

## Коннекторы (9)
LLM-каналы (нужен ключ, все есть):
- gemini — YouTube+web grounding
- grok — X live
- openai — Reddit/HN/GitHub/social web_search  [фикс имени ключа]
- perplexity — sonar web/news  [НОВЫЙ]

Прямые zero-config (структурный сигнал, которого LLM не даёт):
- hackernews — Algolia points/comments  [НОВЫЙ]
- polymarket — gamma одды на рынках  [НОВЫЙ]
- github — repos/issues, stars/velocity через gh  [НОВЫЙ]
- reddit — search.json top+upvotes, best-effort degrade  [НОВЫЙ]
- bluesky — searchPosts, best-effort degrade  [НОВЫЙ]

Опционально (нет ключа — только каркас+доки): tiktok/instagram via SCRAPECREATORS_KEY, brave via BRAVE_API_KEY.

## Архитектура скрипта
- Реестр CONNECTORS (name → fn, kind=llm|direct, requires=[keys], default) + проверка доступности.
- Параллель через threading, graceful-degrade (ERROR.md), manifest.json.
- CLI: `--list-connectors` (JSON для plan-фазы), `--only/--skip`, `--q name:query` (repeatable) + legacy `--gemini-q/--grok-q/--openai-q`, `--max-items`, `--render-html <md> --html-out <html>`.
- HTML: мини markdown→HTML, dark-mode, inline CSS, system-font fallback, self-contained.

## Plan-first gate (главное поведенческое изменение)
SKILL.md STEP 0 (обязательно до запуска скрипта): агент строит **research plan** —
topic resolution (@handles / сабреддиты / каналы / сущности), какие коннекторы задействуем и почему,
per-channel запросы, ожидаемые противоречия. Показать план → потом запуск. `--list-connectors` кормит план реальными данными.

## Шаги
- [x] план зафиксирован (этот файл)
- [x] переписать deep-research.py (реестр, 6 новых каналов, фикс ключа, HTML, manifest, list-connectors)
- [x] smoke: `--list-connectors` (9/9 avail); HN+Polymarket+GitHub прогнаны; HTML self-contained; perplexity+openai живьём ✓
- [x] переписать SKILL.md (plan-first STEP 0, topic-resolution, 9 коннекторов, HTML-выход, DO/migration note убраны)
- [x] отчёт Нику + абсолютные пути

## Раунд 2 (08-07, реакция Ника: не жги Anthropic/OpenAI API + добавь hiring)
- **openai-канал → opt-in (default off)**: скрипт по умолчанию НЕ бьёт api.openai.com. Web/social дефолт = Gemini(Google)+Grok(xAI)+Perplexity + free direct. Синтез в сессии (не api.anthropic.com).
- Codex проверен живьём (codex-cli 0.136.0): нет простого web-search API (агент+playwright), в параллельный скрипт встраивать хрупко → НЕ делаю Codex-каналом; «GPT через Codex» = ручной путь, задокументирован.
- **hiring коннектор (новый, free, default on)**: HN "Who is hiring?" (последний месячный тред whoishiring via Algolia) → сколько вакансий упоминают тему + какие компании. July 2026: rag=99, agents=51, rust=49, context-eng=7. Ровно инсайт Ника про горячие темы.
- Итого 10 коннекторов (9 default + openai opt-in). SKILL.md: добавлен раздел «Budget rule — no Anthropic/OpenAI API by default».

## Итог прогонов (08-07)
- Polymarket переписан на `/public-search` (Gamma `/markets` капается на 100 по volume — не годился): BTC/выборы/GPT-5.6 бьёт точно.
- OpenAI-канал: баг чтения ключа (`openai.txt`→`openai-api-key.txt`) починен, живьём 34.5s/13KB.
- Perplexity: новый канал, живьён 9.2s/4.8KB, citation-first.
- Reddit/Bluesky в этом sandbox душатся (403/HTML) — degrade-friendly, у пользователя в проде могут работать; LLM-каналы дублируют охват.

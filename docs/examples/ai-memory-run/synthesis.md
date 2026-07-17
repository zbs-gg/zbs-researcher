# State of AI Memory — July 2026

Синтез 7 каналов (gemini/grok/perplexity + hackernews/hiring/github/polymarket).
reddit/bluesky — 403 (throttling), не участвуют. Дата: 2026-07-08.

## Bottom line

**«Память не решена» — это консенсус, а не спор.** Все три reasoning-канала
(web, X, YouTube) сходятся: универсального победителя нет, а настоящее узкое
место — **не сам memory-инструмент, а архитектура агента**, которая решает,
что держать в контексте. Retrieval во многом «закрыт», temporal-память и
долгий горизонт — нет. Терминология сместилась `prompt → context → memory
engineering`, и уже проклёвывается следующий виток — *salience engineering*
(не «что» в контексте, а «когда агенту говорить»).

Центральное событие полугодия, всплывшее **независимо в трёх каналах** (X,
YouTube, web) — июньская статья **«Are We Ready For An Agent-Native Memory
System?»**, стресс-тест ~12 систем (Mem0, Zep, Letta, Cognee, MemOS, A-MEM,
LightMem…). Именно она кристаллизовала «нет универсального победителя».

## Игроки и числа (осторожно — часть цифр спорные)

| Система | Что это | Сильна в | Числа (с оговорками) |
|---|---|---|---|
| **Mem0** | vector+graph+KV слой | latency, персонализация, продакшн | ~60K★ github, $24M Series A; LoCoMo multi-hop **51%**, LongMemEval **49%** |
| **Zep (Graphiti)** | темпоральный KG, validity windows | «что изменилось на прошлой неделе» | LongMemEval **63.8%** — 15 пунктов над Mem0 |
| **Letta (MemGPT)** | tiered self-editing, OS-подобная | retrieval простым файлом | LoCoMo filesystem **74%** (бьёт спец-тулы); 23.7K★ |
| **Cognee** | hybrid graph-vector, 14 режимов | сложный retrieval | «первый» по гибридной архитектуре |
| **Built-in** (ChatGPT/Claude/Gemini) | встроенная | удобство экосистемы | ChatGPT single-hop 63.79, слаб на multi-hop (42.9%) |

⚠️ **Черный ящик бенчмарков:** Evermind.ai заявляет 93% LoCoMo / 83% LongMemEval,
но формально не публикует. Mem0 публиковал «controversial» результаты про
MemGPT, которые Letta оспаривает. Числа между источниками не сходятся, потому
что меряют memory-тул в изоляции vs внутри агента.

## Противоречия — главная ценность прогона

1. **Простое бьёт сложное.** Letta-filesystem 74% > специализированных
   графов/векторов; голый Long Context выигрывает на DB-Bench (@chenchengpro).
   Прямо против нарратива «нужен навороченный memory-слой».
2. **Retrieval решён / temporal — нет.** Mem0 закрыл latency+персонализацию,
   но 49% vs 63.8% Zep на LongMemEval = темпоральное рассуждение (факты,
   которые меняются) в проде **не решено**.
3. **«Галлюцинации прошлого».** Факт обновился — система отдаёт старое.
   Append-only хранилища деградируют катастрофически на длинном горизонте.
   Graph-методы с lifecycle держат апдейты надёжнее.
4. **Стоимость структуры.** Глобальная перестройка (Mem0) — 374–552 сек;
   локальное обслуживание (LightMem) — 17 сек. **20–30× разрыв по латентности.**
5. **Авто-память опасна («instruction rot», @mattpocockuk).** Self-improving
   loops / авто-CLAUDE.md делают агента неуправляемым — он over-index'ит на
   плохие или устаревшие «воспоминания».
6. **External memory vs continual learning (философский, из YouTube).** RAG-
   память — это «memo, не память»; «Frozen Novice»: агент копит инфу, но веса
   не меняются → настоящей экспертизы нет. Лагерь консолидации в веса
   («биологический сон») vs лагерь практичной внешней памяти.

## Что дал каждый канал (триангуляция сработала)

- **perplexity** — структурный landscape + таблица бенчмарков с цитатами.
- **grok (X)** — живые голоса и дата-точная привязка к июньской статье;
  «фрагментировано как БД в 2003» (@stretchcloud); *salience engineering* как
  следующий термин (@zxcasd12451).
- **gemini (YouTube)** — концептуальный слой: «memory engineering» как
  преемник context engineering; «Frozen Novice»; спор external vs weights.
- **github** — то, чего LLM не подсветили: **memory poisoning** как новая
  атака-поверхность («Sleeper Memory Poisoning in LLM Agents»; «Securing
  LLM-Agent Long-Term Memory Against Poisoning»). Плюс звёзды/velocity
  (Mem0 60K, bytedance/deer-flow 76K, memvid 15K).
- **hackernews** — Elasticsearch persistent agent memory 0.89 recall (116 pts);
  Universal Memory Protocol (общий формат); Steve Yegge «Beads».
- **hiring** — *context engineering* = 7 постингов в July-2026 who-is-hiring.
  Показательный: **Kinelo** прямо про «context myopia — агенты не знают, чего
  не знают». Т.е. тема нанимается, но как ниша спецов, не hype-волна на джунов.

## Слабые места прогона (честно)

- **reddit + bluesky = 403** (throttling в этой сети) — community-голос
  недобран; X частично покрывает.
- **polymarket нерелевантен** — 0 рынков про AI-память; матчинг зацепил
  политический шум (Иран/Венесуэла). Тема не forecastable — коннектор честно
  бесполезен здесь.
- **HN Algolia** подмешал исторический шум (Stuxnet 2012, Jarvis-1 2023) —
  релевантность неидеальна.

## Почему это близко тебе (Pulse)

Конкурентный ландшафт памяти прямо пересекается с Pulse: Zep-temporal,
«галлюцинации прошлого», спор «retrieval solved / temporal not» и черный ящик
бенчмарков — это ровно те оси, где Pulse может честно позиционироваться
(«покажи, не продавай»: свой эвал на своих данных, а не заявленные 93%).
Найм-сигнал говорит, что рынок под это есть, но узкий — покупатель = команда,
которой болит temporal/долгий горизонт, а не «ещё один RAG».

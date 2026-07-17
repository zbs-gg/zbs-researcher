# Competitive landscape — deep-research / multi-platform research tools

_Compiled 2026-07-17 from a 4-segment parallel scan (commercial · open-source · MCP/skill ecosystem · social-listening+Telegram). Every segment independently converged on the same conclusion._

## TL;DR

- The **fan-out + reaction-weight engine is no longer a differentiator** — it's been cloned free and mature. The one true architectural peer is **`mvanhorn/last30days-skill`** (52k★, MIT, active daily): real per-platform connectors + engagement-weighted ranking, distributed as a Claude Code plugin. Everything else labelled "deep research" is an **LLM + generic web-search loop** with no social/reaction layer.
- **Three unoccupied gaps**, confirmed across all four segments:
  1. **Telegram as a first-class *scored research source*** — nobody. Telegram tooling is either account plumbing (Telethon MCPs) or an *output* channel (render report into a TG chat) or standalone OSINT scrapers not wired to any synthesis pipeline.
  2. **Non-coder product wrapper** — account / pricing / onboarding around the research core. Even last30days is a developer-adjacent install.
  3. **Client-facing / done-for-you delivery** — last30days is free/community, no commercial wrapper; that layer is uncontested.
- **Monetization red flag:** **GummySearch** (Reddit-only engagement research) **shut down Nov 2025 at $35K MRR / 10k paying customers** — couldn't license the commercial Reddit API. Do not build a paid product on fragile scraping.

## Segment 1 — Commercial "deep research" products

| Player | What / price (2026) | Beyond web? | Reactions? | Telegram? | Embeddable? |
|---|---|---|---|---|---|
| Perplexity Deep Research | multi-step web + cited synth; Sonar DR API ~$0.30-1.30/query, Pro $20/mo | incidental Reddit via index | no (relevance/recency) | no | yes (Sonar API) |
| OpenAI Deep Research | agentic browse+synth; o3-DR $10/$40 per M | web + granted connectors | no | no | yes (API) |
| Google Gemini Deep Research | agent, ~$2-5/task | web only | no | no | yes (API) |
| Exa | neural search API, $5-15/1k; raw retrieval, no synth | indexes social as base | no | no | infra |
| Tavily | search/extract/crawl, credit-priced | web-focused | no | no | infra/MCP |
| You.com Research API | tiered agent $6.50-300/1k; white-label friendly | web/news only | no | no | yes |
| Genspark / Manus | consumer super-agents, credit $20-250/mo | multi-source, closed | no | no | no |
| Elicit/Consensus/Undermind | academic-paper research | papers | citation-weighted | no | some API |
| **BuzzSumo** | engagement-ranked content research | articles+social | **yes (philosophy)** | no | no LLM synth |
| **TGStat** | Telegram-only analytics, RU-hosted | — | reach/citation | **yes, only TG** | no synth |
| **last30days-skill** | free MIT skill, ~50 platforms, engagement-scored | **yes** | **yes** | **no** | Claude plugin |

## Segment 2 — Open-source deep-research frameworks

All **LLM + generic web-search loop**, no social/reaction/Telegram — *except last30days*:

- `bytedance/deer-flow` 77k★ (LangGraph multi-agent, plan-first, web+crawler+code) · `khoj` 35k★ (AI second brain) · `stanford-oval/storm` 30k★ (stale Sep-2025) · `gpt-researcher` 28k★ (Tavily/Bing/Google retrievers) · `langchain-ai/open_deep_research` 12k★ (MCP-compatible — *could* bolt on a Reddit/TG MCP, none ships) · `dzhng/deep-research` 19k★ · `jina-ai/node-DeepResearch` 5k★ (transparent think-trace) · `local-deep-research` 8.7k★ (fully local, academic sources) · `morphic` 9k★ (Perplexity clone).
- **`last30days-skill` 52.5k★** — the only OSS peer with structured per-platform connectors + engagement weighting. No Telegram.
- Telegram OSINT scrapers exist (`ergoncugler/web-scraping-telegram`, Telsca) but are standalone, **not integrated into any research pipeline** — a separate category.

## Segment 3 — MCP / Claude-skill ecosystem

- Market splits: **raw-search tools** (Exa MCP, Tavily MCP, Firecrawl MCP incl. its `deep_research` tool, Perplexity MCP, Anthropic web_search $10/1k) — agent calls tool, does own synthesis — **vs one opinionated pipeline: last30days**.
- **Telegram in the ecosystem = plumbing or output only**: `chigwell/telegram-mcp`, `sparfenyuk/mcp-telegram` (account access via Telethon); Anthropic "Channels" (push TG/Discord/iMessage into a session, Mar 2026); ClawHub "Deep Research Agent" (~35k installs — renders reports *into* Telegram, doesn't source *from* it). **Nobody scores Telegram channels as a research source.**
- `Agent Reach` — 16 platforms incl. Chinese social, but no reaction weighting (fetch tool, not scored pipeline).

## Segment 4 — Social-listening + Telegram

- **Enterprise** (Brandwatch, Meltwater, Talkwalker $9-27K/yr, Sprout $199-399/seat + add-on, YouScan $499/mo CIS-focused): **dashboards + alerts, not query→report synthesis.** Telegram mostly a "secondary add-on" or unconfirmed. Only **Brand24/Mentionlytics** ($199-249/mo) confirm Telegram — but mention-alerting, not comment-thread mining.
- **Telegram specialists** (TGStat, Telemetr.io $0-499/mo, 11M+ channels): deep Telegram, **analytics-only** — "find a great channel but can't do anything with that info inside the tool." Single-platform, RU-hosted.
- **Indie AI** (NicheProwler "Intelligence Reports" but Reddit/YT/TikTok/IG no TG; MonetScope/IndieRadar/GummySearch/Syften Reddit-centric): none do Telegram.
- **Structural reason Telegram is underserved:** no public trending tab, no centralized discovery API, ephemeral channel churn → tools built on indexed API platforms treat it as an add-on. Discovery-without-index + Cyrillic/informal parsing is **real unsolved technical work**.

## Bottom line for ZBS Research

Empty intersection, confirmed 4×: **developer-installable, cheap, multi-platform, reaction-weighted research pipeline that treats Telegram channels+comments as a first-class scored source and outputs a synthesized report** (not a dashboard). Nearest template is last30days (fork-and-add-Telegram shape); the defensible edges are **Telegram + plan-first transparency + productized/client delivery**, not the fan-out engine or reaction-weighting alone.

## Sources (key)
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) · [bytedance/deer-flow](https://github.com/bytedance/deer-flow) · [gpt-researcher](https://github.com/assafelovic/gpt-researcher) · [langchain open_deep_research](https://github.com/langchain-ai/open_deep_research)
- [Perplexity pricing](https://docs.perplexity.ai/docs/getting-started/pricing) · [Exa](https://exa.ai/pricing) · [Tavily](https://www.tavily.com/pricing) · [You.com Research API](https://you.com/resources/research-api-by-you-com)
- [BuzzSumo](https://buzzsumo.com/content-research/) · [GummySearch (shut down)](https://gummysearch.com/pricing/) · [TGStat](https://tgstat.com/analytics) · [Telemetr.io](https://api.telemetr.io/docs/intro/tariff-plans)
- [Brand24 Telegram tools](https://brand24.com/blog/telegram-analytics-tools/) · [Mentionlytics Telegram](https://www.mentionlytics.com/blog/telegram-monitoring/) · [why Telegram monitoring differs](https://mediawatcher.ai/blog/why-telegram-monitoring-is-different-from-other-media-monitoring/)
- [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp) · [ergoncugler/web-scraping-telegram](https://github.com/ergoncugler/web-scraping-telegram)

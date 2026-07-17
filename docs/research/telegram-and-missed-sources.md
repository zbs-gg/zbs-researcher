# Telegram graph + missed sources (build reference)

_From this session's fact-checks. Feeds U6 (Telegram) and U8 (Meta Ad Library / money sources). Companion: docs/competitive/launch-market-radar-sources.md for launch/revenue sources._

## Telegram — channel discovery & graph (the moat, U6)
- **`channels.getChannelRecommendations`** — CONFIRMED live, Telethon-callable 2026. Recommends by **subscriber overlap** (not content). Non-Premium account = truncated list; **Premium = full list**. Zero cost. Working example: `github.com/MargotP/telegram_similar_channels_finder`:
  ```
  client(functions.channels.GetChannelRecommendationsRequest(channel=input_channel))
  ```
  BFS from seed channels = cheapest defensible graph expansion.
- **Forward-graph mining** (complements overlap — "who influences whom"): edge = source→dest per forwarded message. Prior art: `maxbundscherer/telegram-analysis` (forward/mention graph, NetworkX + Louvain, GEXF export), Bellingcat **Telepathy**. Overlap finds *similar* channels; forward-graph (walked backwards) finds *upstream originators* — one hop upstream is the value for fast-moving niches.
- **Paid discovery alternatives:** TGStat (token API, RU-hosted), Telemetr.io (REST $0/$25/$65/$199/$499/mo, free 1k req/mo, 1.8M+ channels, "Spy" keyword search).
- **snscrape** Telegram = public web-view HTML only, weaker than Telethon+MTProto — skip.
- **Safety (R9):** parse read-only from a **separate/secondary account**, never personal (ban risk + personal-DM exposure). Hard-warning gate before any session capture. Telethon = lazy/optional dependency (keeps Tier-0 install light + security posture clean).

## Missed / money sources (the "money is the reaction" tier — U8 + opt-in)
Ranked by signal-per-dollar for Nik's niches (OF-agency, AI-consulting, infoproducts, microsaas):

| Source | Access | Cost | Best niche |
|---|---|---|---|
| **Meta Ad Library API** (U8) | official; identity verification + App Review (5–10 days) for `ads_read` | free, ~200 calls/hr; **full commercial detail EU-only under DSA**, US = political + bucketed | OF-agency + infoproduct ad-spy (top gap) |
| **Whop Trends / Charts** | API + **ships an MCP server** (5 tools) | $99 lifetime / $29mo; Charts free browse | AI creator-econ, infoproducts (revenue-ranked) |
| **Gumtrends** | dataset (250k+ Gumroad products, est. revenue) | one-time fee | infoproducts (what actually sells) |
| **TikTok Creative Center** | free browser dashboard (top ads/hashtags/sounds), no API | free manual / ~$3/1k scraped | OF-agency, infoproduct |
| **Skool leaderboards** | no API, scrape | ~$3.70/1k communities (Apify) | infoproducts/coaching activity |
| **Product Hunt API v2** | official GraphQL, OAuth | free read, 6,250 pts/15min | microsaas launches |
| **G2 / Capterra** | no bulk API, anti-scrape | ~$0.006/review (Apify) | AI-consulting pain mining |
| **Upwork / Fiverr** | scraper-only | usage-based | AI-consulting demand + pricing |
| **BlackHatWorld** | public forum, no API | free | OF-agency operator playbooks (gold) |
| **acquire.com / Flippa** | Flippa has API + free sold-pages; acquire gated | free (Flippa) | microsaas proven-value/exit |
| **Discord public servers** | ToS bans scraping/self-bots | — | skip / metadata-only |
| **pytrends** | **archived Apr 2025** | fragile | use a fork or paid wrapper |

**Biggest structural gap nobody in the discourse stack covers:** competitor **ad-spend/creative intelligence** (Meta Ad Library + TikTok Creative Center) — what's actually being spent money on right now. For OF-agency + infoproduct research these are the two highest-value additions.

## Sources
[getChannelRecommendations docs](https://core.telegram.org/method/channels.getChannelRecommendations) · [MargotP finder](https://github.com/MargotP/telegram_similar_channels_finder) · [maxbundscherer/telegram-analysis](https://github.com/maxbundscherer/telegram-analysis) · [Telemetr.io](https://api.telemetr.io/docs/intro/tariff-plans) · [Meta Ad Library API](https://adlibrary.com/posts/meta-ad-library-api-limitations) · [Whop API](https://docs.whop.com/api-reference) · [Gumtrends](https://gumtrends.com/) · [Product Hunt API](https://api.producthunt.com/v2/docs)

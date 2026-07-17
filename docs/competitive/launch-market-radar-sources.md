# Market-radar sources — launch & revenue/exit platforms

_Scan 2026-07-17 (two parallel agents). Reference for building U12 (launch-radar) + U13 (revenue/exit-radar). Prices/endpoints are snippet-sourced — **verify live before building** (per U12/U13 execution notes)._

## Why a separate layer

Discourse sources (Reddit/HN-comments/Telegram) show "what's discussed." Market-radar shows **action + traction**: what got built, how the maker framed it, and — the part discourse structurally can't give — **what actually sells / sold**. Two sub-layers:

- **Launch-radar** — what's shipping now (momentum, category velocity, maker positioning).
- **Revenue/exit-radar** — revenue-verified traction and realized exits (proven value, not launch-day hype).

## Launch-radar sources

| Source | Access | Cost | Signal | Niche |
|---|---|---|---|---|
| **Product Hunt** | GraphQL API v2, OAuth token | free read (commercial needs PH approval); 6250 pts/15min | daily launches, upvotes, maker comments, category rank | AI creator-econ, microsaas |
| **Show HN** | HN Algolia API, `show_hn` tag | **free, no auth**, 10k req/hr | technical-critique comments (pre-mortem) | AI consulting, hypothesis-val |
| **yc-oss/api** | GitHub-hosted JSON (daily Algolia refresh) | free, no auth (unofficial) | funded-startup competitive context | AI consulting |
| **DevHunt** | listings as GitHub PRs → GitHub API | free (quasi-open) | dev-tools launches | AI consulting |
| **MicroLaunch** | scrape-only | free | monthly ranking rewards **sustained traction** | microsaas (best niche match) |
| Peerlist / Uneed / Fazier / TinyLaunch / BetaList / Launching Next | scrape-only | free | daily/weekly launch feeds; BetaList = pre-launch demand | indie/microsaas |
| SaaSHub | scrape-only | — | "alternatives to X" — category/competitor mapping (not new-today) | AI consulting |

**Shortlist by signal-per-effort:** PH → Show HN (already covered) → yc-oss → MicroLaunch → (Peerlist/Uneed as best-effort).

## Revenue/exit-radar sources (the additive layer)

| Source | Access | Cost | Signal | Niche |
|---|---|---|---|---|
| **Flippa** | documented API (`search_listings`) + free per-listing sold-price pages | free | **realized exit prices/multiples**, ~100 listings/day | microsaas |
| **Substack** | public leaderboards (Rising hourly, Bestsellers ARR-ranked daily) | **free** | subscriber-revenue ranking | infoproducts (newsletter slice) |
| **Whop Trends** | API + **ships an MCP server** (5 tools) | $99 lifetime / $29mo | revenue-ranked products/communities/courses, launch-pattern | AI creator-econ, infoproducts |
| **Gumtrends** | dataset (250k+ Gumroad products) | one-time fee | estimated revenue per infoproduct | infoproducts |
| Whop Charts | free browse | free | native revenue-ranked charts | AI creator-econ |
| Toolify | scrape-only | free | **SimilarWeb traffic-rank** (sustained-usage proxy) | AI tools |
| Acquire.com | live gated (signup+NDA) | free multiples report only | acquisition multiples | microsaas (weak — gated) |

**Best value ranked:** Substack (free) → Flippa (API + free sold-pages) → Whop Trends ($99, MCP-pluggable) → Gumtrends (one-time).

## Deliberately skipped

- **TAAFT / Futurepedia / Insidr / AI-directory clones** — re-skin the "new AI tool announced" signal PH already carries, worse freshness, gameable vote metrics. Not additive. (Toolify is the exception — traffic-rank is real.)
- **AI-consulting market-radar** — no good launch/trend source exists (services market, no product-launch analog; Clutch/GoodFirms are review-count, not trend). Explicit gap, documented in the plan's Non-goals.

## Unique signal vs discourse (confirmed by both agents)
1. Launch-momentum (day-1/week-1 vote velocity = market pull).
2. **Category-velocity** (how many "AI agent for X" launched this week — leading indicator; the hypothesis-validation signal).
3. Maker's own positioning (tagline/tags before outside reaction reframes it).
4. Revenue-verified traction + realized exits (Flippa/Whop/Substack/IH) — what discourse never shows.

## Sources
- [Product Hunt API](https://api.producthunt.com/v2/docs) · [rate limits](https://api.producthunt.com/v2/docs/rate_limits/headers)
- [HN Algolia API](https://hn.algolia.com/api) · [yc-oss/api](https://github.com/yc-oss/api) · [DevHunt repo](https://github.com/MarsX-dev/devhunt)
- [MicroLaunch](https://microlaunch.net/) · [Peerlist Launchpad](https://help.peerlist.io/individual/launchpad/introduction)
- [Flippa](https://flippa.com/) · [Substack leaderboard](https://substack.com/leaderboard/) · [Whop Trends](https://whoptrends.com/) · [Whop Charts](https://whop.com/charts/) · [Gumtrends](https://gumtrends.com/) · [Toolify](https://www.toolify.ai/)

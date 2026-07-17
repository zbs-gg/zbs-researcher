# ZBS Research — positioning (working draft)

_Derived from the 2026-07 competitive scan. One page, for decisions — not marketing copy._

## The one-line

> A **plan-first, reaction-weighted research skill that treats Telegram channels + comments as a first-class source** — the depth of a hands-on operator's research, installable on a client's own cheap keys, outputting a synthesized report instead of a dashboard.

## Who else is here (honest)

- **`last30days-skill`** (52k★, free, MIT) — the real prior art. Same shape: engagement-weighted multi-platform fan-out + synthesis, Claude-plugin distribution. **Lead by crediting it, not pretending to be first.**
- **Deep-research frameworks** (deer-flow, gpt-researcher, khoj…) — LLM + web-search loop. No social, no reactions, no Telegram.
- **Enterprise social-listening** (Brandwatch/Meltwater/Talkwalker, $9-27K/yr) — dashboards+alerts, Telegram = add-on.
- **Telegram specialists** (TGStat, Telemetr) — analytics-only, single-platform, RU-hosted.

## The wedge (what's actually defensible)

1. **Telegram as a scored research source.** Nobody does it. Technically real (discovery without a public index, channel graph, Cyrillic/informal parsing) — Nik already solves this. Highest-value for CIS / crypto / creator-economy niches where Telegram *is* the discourse and Western tools are blind.
2. **Plan-first transparency.** Every commercial product is one-click-opaque. For a paid client deliverable, showing + editing the research plan before it runs is a trust/UX edge.
3. **Client-portable, no vendor lock.** Runs on the client's own machine and cheap keys (Gemini/Grok/Groq + free connectors); a quiet month is ~$0, a busy one a few dollars. Contrast: walled consumer subs (Perplexity/OpenAI) can't be handed to a client as a tool.

**NOT the wedge** (don't pitch these as novel): the fan-out engine, reaction-weighting in general, "no vendor lock" at the dev-infra tier — all already claimed.

## Monetization shape (three layers, Telegram is the connective tissue)

| Layer | What | Why it holds |
|---|---|---|
| **Open-source core** | free skill, BYO-keys, self-serve (like last30days) | funnel + trust; the engine isn't defensible anyway |
| **Telegram premium / managed** | the moat: discovery + channel graph + parsing, optionally hosted | technically hard, uncontested, the thing people pay for |
| **Done-for-you (CIS niches)** | high-margin research delivery where the skill is Nik's multiplier | OF-agencies / infoproducts / crypto — Telegram-native, Western tools blind |

Optional 4th, if scaling past developers: **non-coder wrapper** (account/onboarding/dashboard around the core) — the second unoccupied gap, but a bigger build.

## Hard constraints (learned from the scan)

- **Don't build paid on scraping.** GummySearch died at $35K MRR on the Reddit API. Base the paid product on the **client's own Telegram account** (legal, their data) + official/archival sources (Arctic Shift for Reddit, official APIs). Keep fragile scrapers on the free tier only.
- **Reddit is a free-tier feature, never a paid dependency.**
- **Two deployment profiles** (from ideation): *self* = local/$0/Mac; *client* = cloud-cheap/portable. Media transcription/vision is a pluggable backend, not hardcoded local compute.

## Open questions for Nik

1. (a) free skill + premium-Telegram, (b) done-for-you multiplier, or the layered blend above?
2. Which niche to anchor the done-for-you proof first — OF-agencies, infoproducts, or crypto?
3. Is the non-coder wrapper (gap #2) worth building, or stay developer-installable and win on Telegram depth?

# Access & pricing — every source/provider (build reference)

_Consolidated from this session's fact-checks (2026-07). Prices/limits are as-found; **verify live before building** (several are snippet-sourced). Feeds U4/U6/U7/U8/U9 and the tier model._

## Reddit access (2026)
- **Self-service OAuth CLOSED since Nov 2025** ("Responsible Builder Policy") — must file an approval ticket, waits of days-to-weeks, some never answered. Once approved: **100 QPM free** non-commercial. PRAW 7.8.1 still standard but needs an approved app.
- **Keyless dead:** `.json` → 403 since ~May 2026 (TLS fingerprinting + IP reputation). `.rss` throttled to **1 req/min** since Jun 2026.
- **Arctic-Shift** (arctic-shift.photon-reddit.com, github ArthurHeitmann/arctic_shift): free no-auth API + dumps + search UI, 2005–2026, Pushshift-schema. Full-text search limited to single-subreddit/user. **Score fields plausible but UNCONFIRMED in API — load-bearing, probe first (U11).** Best free default.
- **PullPush.io** — free Pushshift-compatible, inconsistent limits, recurring outages.
- **ScrapeCreators Reddit** — `post/comments` full trees, ~1 credit/call.
- ⚠️ **GummySearch shut down Nov 2025 at $35K MRR / 10k customers** — couldn't license the commercial Reddit API. Do not build paid on Reddit scraping; keep Reddit free-tier only.

## Video-platform vendors (TikTok / Instagram)
- **ScrapeCreators** — genuinely pay-as-you-go, **no subscription, credits never expire**. 100 free credits on signup. Freelance $47 = 25,000 credits ($1.88/1k); Business $497 = 500k ($0.99/1k). TikTok: 21 endpoints incl. a **Transcript** endpoint + search (Users/Hashtag/Keyword/Top) + comments. IG: from $0.0006/req; comments ~90% success (most error-prone). A **$10 "Solo Dev" / 5k-credit tier is reported by 3rd parties but NOT on the live pricing page** — check the billing dashboard.
- **Apify** — Free plan $5/mo credit (**hard-caps**, no PAYG overflow → forces $29/mo Starter). TikTok: apidojo $0.30/1k (cheapest), clockworks $1.70/1k. IG: $2.70/1k free-tier ($1.90 Scale). Reddit: $0.58–1.15/1k.
- **Low-volume verdict** (~2–5k calls/mo): Apify Free ≈ $0–10/mo (cheap actors, accept caps) OR ScrapeCreators $47 one-time = 5–12 months runway (~$4–9/mo amortized). **Free-OSS** (flaky): instaloader (IG, logged-out light, ban-risk if authed), davidteather/TikTok-Api (needs proxies), yt-dlp (video/metadata, no comment trees).
- **LinkedIn** — Proxycurl **killed** (LinkedIn+MS lawsuit Jan 2025, shut Jul 2025). EnrichLayer successor ~$588/yr. Apify cookie-based = real perma-ban risk; cookieless = shallow, no comments. hiQ precedent: public scraping ≠ CFAA crime but ToS breach; realistic exposure = account ban. Cheapest safe = manual/semi-auto on own session. **De-prioritized (R12).**

## Cloud transcription / vision (client profile) & local (self profile)
- **Groq Whisper** (PAYG, no subscription): turbo **$0.04/hr** audio, large-v3 $0.111/hr, 10s min/request. 5 hrs/mo = **$0.20**. (Nik already has a Groq key.)
- **Gemini 2.5 Flash**: audio input ~**$0.09/hr** (token-based, $1/M audio-in); vision **$0.00008–0.00046/image** (tiled, $0.30/M in). 300 images + 5 hrs ≈ **$0.70–0.85/mo**.
- **$10/mo ≈ 250 hrs audio (Groq) or ~20k images (Gemini)** — target volume ~$0.40/mo (3–4% of ceiling). $10 is a comfortable ceiling, not tight.
- **ScrapeCreators transcript endpoint** ~$0.001–0.002/call, flat by length (platform auto-caption quality, not Whisper).
- **Local (self profile, $0, Mac-bound):** MLX Whisper ~7–10× realtime; Gemma-3 vision in LM Studio. Cheaper alts: Deepgram Nova-3 $0.0077/min, AssemblyAI $0.15/hr.
- **Neither Anthropic nor OpenAI** in the media path (budget invariant R17).

## OpenRouter (Tier 2, one key) — U4
- Passes **provider-native tools**: Gemini `googleSearch` grounding, Grok `x_search` (with `x_search_filter`: handles/dates/media), Perplexity Sonar models (citations built in). Lenses are **preserved, not flattened**.
- **Use explicit native tool schema, NOT `:online`** (which forces a search every call — dumber + pricier). **Raw HTTP is the safe path** — wrapper libs (Vercel ai-sdk, continue.dev) have open Gemini-grounding bugs. Our channels are already raw-`urllib`.
- Fee stack: provider token + provider search-context + **5.5% OpenRouter platform fee**, one invoice, PAYG.
- Caveats: Gemini **structured-JSON-output and search-grounding are mutually exclusive** through OpenRouter; Perplexity access has flip-flopped — **smoke-test before relying**; single gateway = single point of failure. Keep direct keys as the independent-blast-radius alternative.

## Sources
Reddit: [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) · [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) · [RSS rate-limit blog](https://lapcatsoftware.com/articles/2026/6/3.html)
Vendors: [ScrapeCreators](https://scrapecreators.com/) · [Apify pricing](https://apify.com/pricing) · [Proxycurl shutdown](https://nubela.co/blog/goodbye-proxycurl/)
Cloud: [Groq pricing](https://groq.com/pricing) · [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
OpenRouter: [Web search docs](https://openrouter.ai/docs/guides/features/plugins/web-search) · [pricing](https://openrouter.ai/pricing)

<grounding>
CONSOLIDATED GROUNDING — multi-platform research plugin with reaction-weighting (July 2026)

## Topic context
Personal research aggregator (private → free public release). Today: Reddit + AI deep-research, X via Grok, YouTube via Gemini, HN+comments, Telegram channels via Telethon on separate account ("gold that doesn't exist on external internet, especially comments"). Wants: add TikTok/IG cheaply, then release free. Existing base: Claude Code plugin "deep-research" v0.2.0 — Python stdlib-only connector registry, 10 connectors (gemini/grok/perplexity LLM lenses + free direct: hackernews, hiring, polymarket, github, reddit[dead 403], bluesky), parallel threading, ERROR.md degrade, manifest.json, plan-first, HTML brief. Budget canon: no Anthropic/OpenAI API by default; flat-rate subs (Claude Max, Codex) preferred; Mac 64GB + LM Studio/MLX local models available.

## Research digest 1 — Reddit access (July 2026)
- Self-service OAuth registration CLOSED since Nov 2025 ("Responsible Builder Policy") — must file approval ticket, waits of days-weeks, some never answered (Apollo-Reborn#82). Once approved: 100 QPM free non-commercial. PRAW 7.8.1 alive but needs approved app.
- Paid tier $0.24/1k calls REPORTED not confirmed (2023-origin number, min commitment ~$12K conflicting).
- Reddit for Researchers: university+PI+IRB only — hard gate for indie.
- Keyless dead: .json → 403 since ~May 28 2026 (TLS fingerprinting + IP reputation); .rss cut to 1 req/min since Jun 11-12 2026 (confirmed via lapcatsoftware.com with headers); no reliable keyless path at throughput.
- Arctic Shift (arctic-shift.photon-reddit.com, github ArthurHeitmann/arctic_shift): actively maintained (June 2026 release), free no-auth API + dumps + search UI, 2005-2026 coverage, Pushshift-schema; full-text search limited to single-subreddit or single-user; score fields plausible but unconfirmed in API. Best free default.
- PullPush.io: free Pushshift-compatible, rate limits inconsistent (15-100/hr reports), recurring outages.
- ScrapeCreators Reddit: 6 endpoints incl post/comments (full trees), search, subreddit; ~1 credit/call; 100 free credits; tiers $10/$47/$497.

## Research digest 2 — video platforms + LinkedIn + local compute
- TikTok: ScrapeCreators 100 free credits, ~$0.0006-0.002/credit at volume ($47≈25K credits); 21 endpoints: profile/videos/video-info/Transcript endpoint/search (Users/Hashtag/Keyword/Top)/comments/replies/trending. Apify: $0.30-1.70/1k posts, $5/mo free credit. Official Research API = academic-only, ~4wk approval, unusable for indie. Creative Center = free browser dashboard (trending hashtags/sounds/top ads), no API. Free fallback davidteather/TikTok-Api alive but flaky (bot detection).
- Instagram: ScrapeCreators from $0.0006/req, 100 free; profile/reels/captions/comments (comments ~90% success, most error-prone). Apify Reel ~$1.00-2.60/1k, Comments ~$1.90-2.30/1k, $5/mo free ≈ 2k reels. Meta Graph API = Business/Creator own-account only (Basic Display dead Dec 2024). oEmbed = embed HTML only, no comments/counts. instaloader (MIT, v4.15.1 Apr 2026) free full metadata incl comments but ~1-2 req/30s unauthenticated, account-lock risk when scripted hard.
- LinkedIn: Proxycurl KILLED (LinkedIn+Microsoft lawsuit Jan 2025, shut July 4 2025, data deleted). EnrichLayer successor ~$588/yr 35K credits. Apify actors ~$3/1k: cookie-based = real perma-ban risk (LinkedIn restricted 58M+ accounts H1 2024), cookieless = shallow, no comments. hiQ precedent: public scraping ≠ CFAA crime but ToS breach; realistic indie exposure = account ban. Cheapest safe path: manual/semi-auto on own session at low volume.
- YouTube: Data API v3 unchanged: free 10k units/day, commentThreads.list=10 units (hundreds of pulls/day fine), search.list=100 units (expensive), videos.list=1. Transcripts fragile: youtube-transcript-api blocked by PoToken bot-detection (~100-200 req/hr soft IP limits); yt-dlp maintained but intermittent 403s (issue #16607); robust fallback = audio download + local Whisper (works even without captions).
- Local compute: MLX Whisper ~2x faster than whisper.cpp on large-v3-turbo; M-series ≈7-10x realtime (60min audio in 6-9min), $0 marginal. Vision: Gemma 3 multimodal in LM Studio (MLX engine, prompt caching) $0/image local; Gemini 2.5 Flash vision ~$0.0001-0.0005/image cloud (sub-cent, essentially free at personal volume).

## Research digest 3 — Telegram graph + missed sources
- channels.getChannelRecommendations CONFIRMED live, Telethon-callable 2026 (core.telegram.org/api/recommend; tl.telethon.dev). Recommends by SUBSCRIBER OVERLAP (not content). Non-Premium = truncated list, Premium = full. Working example github MargotP/telegram_similar_channels_finder: `client(functions.channels.GetChannelRecommendationsRequest(channel=input_channel))`. Zero cost. BFS from seed channels = cheapest defensible graph expansion.
- Forwards-graph mining prior art: maxbundscherer/telegram-analysis (forward/mention graph, NetworkX+Louvain, GEXF export); Bellingcat Telepathy. Edge = source→dest per forwarded message = "who influences whom" (info flow), complements subscriber-overlap.
- Paid discovery: TGStat token API (pricing opaque); Telemetr.io REST $0/$25/$65/$199/$499/mo, free 1k req/mo, 1.8M+ channels DB.
- snscrape Telegram: public web-view HTML only, weaker than Telethon — skip.
- Missed sources ranked (signal-per-dollar): Meta Ad Library API (official, free ~200 calls/hr, identity verification + App Review 5-10 days; full commercial detail EU-ONLY under DSA, US = political + bucketed) — top gap for OF-agency/infoproduct ad-spy. TikTok Creative Center top ads (free manual, ~$3/1k rows scraped). Whop API (official, credit-based) — infoproducts/cohorts. Skool leaderboards (no API, ~$3.70/1k communities via Apify) — coaching/infoproducts activity signal. Product Hunt API v2 (free GraphQL 6250 pts/15min) — microsaas launches. G2/Capterra (~$0.006/review Apify) — AI-consulting pain mining. Upwork/Fiverr scraper-only — consulting demand+pricing. Gumroad Discover via Gumtrends dataset (250k+ products w/ est revenue) — what actually SELLS. BlackHatWorld (free forum, no API) — OF-agency operator playbooks GOLD. Discord = ToS bans scraping/self-bots, metadata-only or skip. PodcastIndex free but transcripts <1% — needs own Whisper. pytrends ARCHIVED Apr 2025 (use pytrends-modern fork or paid). acquire.com ~1.3k listings scrapeable. App-store review mining free via unmaintained-but-working npm libs.
</grounding>

<constraints>
User (Nikita) verbatim requirements: multi-platform research plugin that accounts for people's REACTIONS (upvotes/likes/views/comments weighted). Sources wanted: Reddit posts+comments (asks the right official-API path now); HN posts+comments; Telegram (separate parsing account, folders of channels per theme, discover similar channels via API + build source graph, periodic folder refresh; niches: (a) AI onlyfans/fanvue-model business, (b) AI consulting, (c) infoproducts/education, (d) microsaas/pet-projects/hypothesis validation); X (has Grok subscription; posts/threads/articles/comments); YouTube (transcription+comments); TikTok (hashtag?profile?search + transcription+comments); IG Reels (transcription+comments); IG carousels (image recognition+comments); LinkedIn (image/video recognition+comments). His questions: (1) which important sources did he miss? (2) how to assemble ALL into a plugin that works well and does NOT cost a spaceship — maximally simple but working. Budget rule: no Anthropic/OpenAI API spend by default; prefers flat-rate subs + local Mac compute. He plans to release the plugin FREE publicly.
</constraints>

<axes>
1. source-access — how to reach each platform (method + cost): Reddit, X, YouTube, TikTok, IG, LinkedIn
2. telegram-graph — Telegram channel discovery, source graph, folder refresh
3. reactions-ranking — normalizing engagement cross-platform, comments as signal, ranking/dedup
4. architecture-cost — plugin pipeline design, local compute leverage, tiered fallbacks, cost ceiling
5. missed-sources — high-signal sources not yet in the list, per his 4 niches
</axes>

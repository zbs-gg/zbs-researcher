# Design research

Decision: host-agent research plus deterministic intake/export. Existing investigate
already follows leads; a second model runner would duplicate it. Instructions alone
cannot check output agreement, so use a small shared dossier validator/renderer.

Reddit: Perplexity discovers URLs; Arctic Shift `/api/posts/ids?ids=ID` and
`/api/comments/search?link_id=ID&limit=25` retrieve text and flat parent IDs.
An explicitly selected ScrapeCreators `/v1/reddit/post/comments?url=URL` is a
paid alternate, never automatic fallback. Body/author loss is in old renderer.
Sources: https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md
and https://docs.scrapecreators.com/v1/reddit/post/comments/

Direct Sonar supports search_domain_filter and search_language_filter. OpenRouter
filter forwarding is unproved; use site-restricted prompt and retained citations,
honestly labeling model summaries. Separate RU/EN queries avoid language crowding.
Source: https://docs.perplexity.ai/docs/sonar/filters

YouTube: reuse metadata/subtitle reader, add bounded `--write-comments` with
`youtube:comment_sort=top;max_comments=30,15,15,3,2`; preserve parent/thread IDs,
author/date/text. Comment failures must not discard transcripts. Default captions
include Russian and English. Sources: https://github.com/yt-dlp/yt-dlp#youtube
and https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/common.py

X: native x_search includes x_thread_fetch. Ask targeted seed thread/reply reads,
retain actual tool trace/citations; model paraphrases are not raw posts. Source:
https://docs.x.ai/developers/tools/x-search

Spend: xAI ticks / 1e10 gives actual cost; OpenRouter usage cost when returned.
Source: https://docs.x.ai/developers/cost-tracking
One dollar is feature allowance, distinct from prior probe. Reserve conservative
amounts before every live call; unknown cost retains reservation. Local receipts
are not an account-wide monetary cap.

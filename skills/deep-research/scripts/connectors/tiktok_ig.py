"""TikTok / Instagram connector (U7, R10): short-video user voice through a
pay-per-use vendor. OPT-IN twice on purpose — default=False in the registry
AND key-gated (requires=["scrapecreators"]) — because every run spends real
vendor credits, and the report header says so honestly.

Vendor adapter is selectable via DEEP_RESEARCH_TIKTOK_VENDOR:

  scrapecreators (default) — api.scrapecreators.com v1-style endpoints
      (x-api-key header): TikTok keyword search + per-video comments,
      Instagram search + per-media comments. Key from
      scrapecreators-key.txt / SCRAPECREATORS_KEY (the runner's KEYS).
  apify — act run-sync-get-dataset-items with APIFY_TOKEN (Bearer header,
      never in the URL). Posts only; comment pulls need scrapecreators.

Engagement (likes/comments/plays) rides through the runner's shared
rank_items (relevance floor + bounded engagement). Transcripts: when a post
carries media bytes AND media_backend resolves, the top ~3 videos are
transcribed; any transcript failure degrades to a metadata-only note — never
a crash. HTTP 402/429 from a vendor raises VendorQuotaError with an explicit
cost hint and propagates so run_connector writes ERROR.md.

Helpers (get_json / post_json / KEYS / rank_items) resolve through the
runner's live globals — see connectors/__init__.py.
"""
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import excerpt as _excerpt
from . import runner

SC_BASE = "https://api.scrapecreators.com"
VENDOR_ENV = "DEEP_RESEARCH_TIKTOK_VENDOR"
VENDORS = ("scrapecreators", "apify")
APIFY_TOKEN_ENV = "APIFY_TOKEN"
APIFY_BASE = "https://api.apify.com/v2"
APIFY_ACT = "clockworks~tiktok-scraper"
COST_NOTE = "pay-per-use vendor — each run costs vendor credits"

_SC_SEARCH_PATHS = {
    "tiktok": "/v1/tiktok/search/keyword",
    "instagram": "/v1/instagram/search",
}
_SC_COMMENT_PATHS = {
    "tiktok": "/v1/tiktok/video/comments",
    "instagram": "/v2/instagram/media/comments",
}
_COMMENT_POSTS = 3        # top posts that get comment pulls (each costs credits)
_COMMENTS_PER_POST = 5
_TRANSCRIBE_TOP = 3       # videos transcribed per run (media fetch + backend)
_MEDIA_BYTES_CAP = 25 * 1024 * 1024


class VendorQuotaError(RuntimeError):
    """Pay-per-use vendor refused for billing/quota reasons (402/429)."""


def _vendor():
    chosen = (os.environ.get(VENDOR_ENV, "") or "").strip().lower()
    if not chosen:
        chosen = "scrapecreators"
    if chosen not in VENDORS:
        raise RuntimeError(
            f"unknown TikTok/IG vendor {chosen!r} — set {VENDOR_ENV} to one "
            f"of: {', '.join(VENDORS)} (default: scrapecreators)."
        )
    return chosen


def _quota_guard(exc, vendor):
    if exc.code in (402, 429):
        raise VendorQuotaError(
            f"{vendor} returned HTTP {exc.code} — pay-per-use quota/credits "
            "exhausted or payment required. Each run costs vendor credits; "
            "top up the vendor balance or reduce scope before retrying."
        ) from exc


def _first(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _extract_items(data):
    """Pull the item list out of a vendor payload (shapes vary by endpoint)."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("search_item_list", "aweme_list", "posts", "items", "medias",
                "data", "comments"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _subdict(raw, key):
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def _normalize_post(raw, platform):
    """Vendor post -> one flat record; tolerant to per-vendor field naming.
    Returns None for entries with no text and no link (nothing citable)."""
    if not isinstance(raw, dict):
        return None
    if isinstance(raw.get("aweme_info"), dict):
        raw = raw["aweme_info"]
    stats = _subdict(raw, "statistics")
    author = _subdict(raw, "author")
    owner = _subdict(raw, "owner")
    author_meta = _subdict(raw, "authorMeta")
    text = _first(raw.get("desc"), raw.get("caption"), raw.get("title"),
                  raw.get("text"))
    handle = _first(author.get("unique_id"), author.get("uniqueId"),
                    author.get("username"), owner.get("username"),
                    author_meta.get("name"), raw.get("username"))
    post_id = _first(raw.get("aweme_id"), raw.get("id"), raw.get("pk"),
                     raw.get("code"))
    url = _first(raw.get("share_url"), raw.get("url"), raw.get("link"),
                 raw.get("permalink"), raw.get("webVideoUrl"))
    if not url and platform == "tiktok" and handle and post_id:
        url = f"https://www.tiktok.com/@{handle}/video/{post_id}"
    likes = _to_int(_first(stats.get("digg_count"), stats.get("like_count"),
                           raw.get("like_count"), raw.get("likes"),
                           raw.get("diggCount")))
    comments = _to_int(_first(stats.get("comment_count"),
                              raw.get("comment_count"),
                              raw.get("commentsCount"),
                              raw.get("commentCount")))
    plays = _to_int(_first(stats.get("play_count"), raw.get("play_count"),
                           raw.get("view_count"), raw.get("playCount"),
                           raw.get("video_view_count")))
    video = _subdict(raw, "video")
    media_url = _first(video.get("download_addr"), video.get("play_addr"),
                       raw.get("download_url"), raw.get("video_url"),
                       raw.get("videoUrl"), raw.get("media_url"))
    if isinstance(media_url, dict):  # TikTok addr objects: {"url_list": [...]}
        urls = media_url.get("url_list") or []
        media_url = urls[0] if urls else None
    if not text and not url:
        return None
    return {
        "platform": platform,
        "text": " ".join(str(text or "").split()),
        "author": handle or "?",
        "id": post_id,
        "url": url,
        "likes": likes or 0,
        "comment_count": comments or 0,
        "plays": plays,
        "media_url": media_url,
        "comments": [],
    }


def _normalize_comment(raw):
    if not isinstance(raw, dict):
        return None
    user = _subdict(raw, "user")
    owner = _subdict(raw, "owner")
    text = _first(raw.get("text"), raw.get("comment_text"), raw.get("content"))
    if not text:
        return None
    author = _first(user.get("unique_id"), user.get("uniqueId"),
                    user.get("username"), user.get("nickname"),
                    owner.get("username"), raw.get("username"))
    likes = _to_int(_first(raw.get("digg_count"), raw.get("like_count"),
                           raw.get("comment_like_count"), raw.get("likes")))
    return {
        "author": author or "?",
        "text": " ".join(str(text).split()),
        "likes": likes or 0,
    }


# ---------------------------------------------------------------------------
# ScrapeCreators vendor path
# ---------------------------------------------------------------------------
def _sc_get(path, params, key):
    url = SC_BASE + path + "?" + urllib.parse.urlencode(params)
    try:
        return runner("get_json")(url, headers={"x-api-key": key}, timeout=60)
    except urllib.error.HTTPError as exc:
        _quota_guard(exc, "scrapecreators")
        raise


def _sc_posts(query, key, max_items):
    pool = min(30, max(10, max_items * 2))
    posts = []
    for platform, path in _SC_SEARCH_PATHS.items():
        data = _sc_get(path, {"query": query}, key)
        for raw in _extract_items(data)[:pool]:
            post = _normalize_post(raw, platform)
            if post:
                posts.append(post)
    return posts


def _attach_comments(posts, key, top=_COMMENT_POSTS,
                     per_post=_COMMENTS_PER_POST):
    for post in posts[:top]:
        if not post.get("url"):
            continue
        try:
            data = _sc_get(
                _SC_COMMENT_PATHS[post["platform"]], {"url": post["url"]}, key
            )
        except VendorQuotaError:
            raise  # billing problems must surface, never degrade silently
        except Exception as exc:  # noqa: BLE001 — one post never kills siblings
            post["comment_note"] = f"comments unavailable: {str(exc)[:120]}"
            continue
        comments = (_normalize_comment(raw) for raw in _extract_items(data))
        post["comments"] = [c for c in comments if c][:per_post]


# ---------------------------------------------------------------------------
# Apify vendor path (act-run stub; posts only)
# ---------------------------------------------------------------------------
def _apify_posts(query, max_items):
    token = os.environ.get(APIFY_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(
            f"{VENDOR_ENV}=apify selected but {APIFY_TOKEN_ENV} is not set — "
            "create an API token at https://console.apify.com/ and export "
            "it. Apify act runs are pay-per-use (compute credits)."
        )
    url = f"{APIFY_BASE}/acts/{APIFY_ACT}/run-sync-get-dataset-items"
    body = {"searchQueries": [query], "resultsPerPage": max_items}
    try:
        data = runner("post_json")(
            # Token in the Authorization header, never in the URL.
            url, body, {"Authorization": f"Bearer {token}"}, timeout=600,
        )
    except urllib.error.HTTPError as exc:
        _quota_guard(exc, "apify")
        raise
    posts = (_normalize_post(raw, "tiktok") for raw in _extract_items(data))
    return [p for p in posts if p]


# ---------------------------------------------------------------------------
# Transcripts (best-effort; failure degrades to a metadata-only note)
# ---------------------------------------------------------------------------
def _media_backend():
    """Resolve media_backend.get_backend() — sibling module, imported lazily
    so the connector loads even where the scripts dir isn't on sys.path."""
    try:
        import media_backend
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import media_backend
    return media_backend.get_backend()


def _fetch_media_bytes(url, timeout=60, cap=_MEDIA_BYTES_CAP):
    """Module-level hook so tests never touch the network."""
    request = urllib.request.Request(url, headers={"User-Agent": runner("UA")})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(cap)


def _transcribe_top(posts, limit=_TRANSCRIBE_TOP):
    for post in posts[:limit]:
        media_url = post.get("media_url")
        if not media_url:
            continue
        try:
            blob = _fetch_media_bytes(media_url)
            if not blob:
                continue
            text = _media_backend().transcribe(blob, mime="audio/mp4")
            if text:
                post["transcript"] = text
        except Exception as exc:  # noqa: BLE001 — degrade to metadata-only
            post["transcript_note"] = (
                f"transcript unavailable ({str(exc)[:120]}) — metadata only"
            )


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------
def channel_tiktok_ig(query, out_path, max_items):
    """TikTok/IG posts + comments + engagement for a topic via the selected
    pay-per-use vendor, ranked by the shared relevance/engagement rules."""
    vendor = _vendor()
    key = ""
    if vendor == "scrapecreators":
        key = runner("KEYS").get("scrapecreators") or ""
        if not key:
            # select_connectors gates on requires=["scrapecreators"] first;
            # a direct call without a key still fails honestly.
            raise RuntimeError(
                "ScrapeCreators key not configured — put it in "
                "scrapecreators-key.txt (secrets dir) or SCRAPECREATORS_KEY. "
                "This is a pay-per-use vendor: each run costs vendor credits."
            )
        posts = _sc_posts(query, key, max_items)
    else:
        posts = _apify_posts(query, max_items)

    ranked = runner("rank_items")(
        posts, query, text_key="text", engagement_key="likes",
        comments_key="comment_count", max_items=max_items,
    )
    shown = ranked.items
    if vendor == "scrapecreators" and shown:
        _attach_comments(shown, key)
    _transcribe_top(shown)

    lines = [
        f"# TikTok / Instagram — posts + comments for: {query}\n",
        f"_Cost: {COST_NOTE} (vendor: {vendor})._\n",
    ]
    if vendor == "apify":
        lines.append(
            "_Note: the Apify act returns posts only — comment pulls need "
            "the scrapecreators vendor._\n"
        )
    if ranked.note:
        lines.append(f"_Note: {ranked.note}._\n")
    if not shown:
        lines.append("_No posts matched this topic._\n")
    for post in shown:
        lines.append(
            f"- **@{post['author']}** ({post['platform']}) — "
            f"{_excerpt(post['text'])}"
        )
        plays = (
            f", plays {post['plays']:,}" if post.get("plays") is not None else ""
        )
        lines.append(
            f"  - likes {post['likes']:,}, comments {post['comment_count']:,}"
            f"{plays}"
        )
        if post.get("url"):
            lines.append(f"  - {post['url']}")
        if post.get("transcript"):
            lines.append(f"  - transcript: {_excerpt(post['transcript'], 300)}")
        elif post.get("transcript_note"):
            lines.append(f"  - _{post['transcript_note']}_")
        if post.get("comment_note"):
            lines.append(f"  - _{post['comment_note']}_")
        for comment in post.get("comments", []):
            lines.append(
                f"  - @{comment['author']} (likes {comment['likes']}): "
                f"{_excerpt(comment['text'], 200)}"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(shown)

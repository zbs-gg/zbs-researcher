"""Threads connector (U15, R23): posts by keyword through two paths.

Official path — GET graph.threads.net/v1.0/keyword_search with a Threads
access token (threads-access-token.txt / THREADS_ACCESS_TOKEN). Free; quota
2,200 queries per rolling 24h per user; scopes threads_basic +
threads_keyword_search. Honest limits, stated in the report instead of
papered over: results carry NO engagement counts (likes/replies are
own-media-Insights-only), so the report keeps Meta's TOP-relevance order and
never fakes an engagement ranking. With Standard Access the search covers
ONLY the authenticated user's own posts — Advanced Access (App Review)
unlocks public search — and sensitive keywords return an empty array; an
empty result with a valid token says both.

The docs put the token in an `access_token` query param, so it rides in the
request URL — but it must NEVER appear in the rendered report or in any
raised-error text. HTTP errors are re-raised as HTTPError with the token
redacted from the URL, reason, and body, so run_connector's ERROR.md degrade
stays token-free.

Vendor path — ScrapeCreators GET /v1/threads/search?query=<q> with an
x-api-key header (key never in the URL): pay-per-use, 1 credit/request,
~10 posts per request (documented hard cap, no pagination) WITH engagement
counts (like/reply/repost/quote/reshare). Output is ranked through the
runner's shared rank_items (likes + reply corroboration) and carries an
explicit cost note.

Path selection: official token present AND DEEP_RESEARCH_THREADS_VENDOR
unset -> official. Token absent OR the env forces scrapecreators -> vendor
(clear error if the vendor key is missing). Unknown vendor value -> clear
error before any network call. With ONLY the scrapecreators key the
connector stays available (registry fallback_key) and routes to the vendor
automatically.

Helpers (get_json / KEYS / rank_items) resolve through the runner's live
globals — see connectors/__init__.py.
"""
import io
import os
import time
import urllib.error
import urllib.parse

from . import excerpt as _excerpt
from . import runner

OFFICIAL_URL = "https://graph.threads.net/v1.0/keyword_search"
SC_URL = "https://api.scrapecreators.com/v1/threads/search"
VENDOR_ENV = "DEEP_RESEARCH_THREADS_VENDOR"
VENDORS = ("scrapecreators",)
COST_NOTE = "pay-per-use vendor — 1 credit/request, ~10 posts"
NO_ENGAGEMENT_NOTE = (
    "official API returns no engagement counts — ordered by Meta's TOP "
    "relevance"
)
EMPTY_RESULT_NOTE = (
    "0 results with a valid token. This may mean the token has Standard "
    "Access — keyword search then covers only your own posts (Advanced "
    "Access via App Review unlocks public search) — or Meta's "
    "sensitive-keyword filter returned an empty set for this topic."
)
_FIELDS = ",".join((
    "id",
    "text",
    "media_type",
    "permalink",
    "timestamp",
    "username",
    "has_replies",
    "is_quote_post",
    "is_reply",
))
_REDACTED = "<redacted-token>"


def _select_path():
    """Resolve (path, key) from the vendor env + configured keys.

    Raises a clear RuntimeError for an unknown vendor value, a forced
    vendor without its key, or no key at all — before any network call.
    """
    chosen = (os.environ.get(VENDOR_ENV, "") or "").strip().lower()
    if chosen and chosen not in VENDORS:
        raise RuntimeError(
            f"unknown Threads vendor {chosen!r} — set {VENDOR_ENV} to one "
            f"of: {', '.join(VENDORS)}, or unset it to use the official "
            "API when a Threads token is configured."
        )
    keys = runner("KEYS")
    token = keys.get("threads") or ""
    sc_key = keys.get("scrapecreators") or ""
    if token and not chosen:
        return "official", token
    if chosen and not sc_key:
        raise RuntimeError(
            f"{VENDOR_ENV}={chosen} forces the ScrapeCreators vendor but no "
            "ScrapeCreators key is configured — put it in "
            "scrapecreators-key.txt (secrets dir) or SCRAPECREATORS_KEY. "
            "This is a pay-per-use vendor: 1 credit/request."
        )
    if not token and not sc_key:
        # select_connectors gates on requires=["threads"] with
        # fallback_key="scrapecreators" first; a direct call without any
        # key still fails honestly.
        raise RuntimeError(
            "Threads connector has no credentials — configure the official "
            "Threads token (threads-access-token.txt or "
            "THREADS_ACCESS_TOKEN; free, but Standard Access searches only "
            "your own posts until App Review) OR a ScrapeCreators key "
            "(scrapecreators-key.txt or SCRAPECREATORS_KEY; pay-per-use, "
            "1 credit/request)."
        )
    return "scrapecreators", sc_key


def _redact(value, token):
    return str(value or "").replace(token, _REDACTED)


def _official_fetch(query, token, limit):
    params = {
        "q": query,
        "search_type": "TOP",
        "limit": limit,
        "fields": _FIELDS,
        # Per the Threads docs the token is a query param. It is redacted
        # from every error path below and never rendered.
        "access_token": token,
    }
    url = OFFICIAL_URL + "?" + urllib.parse.urlencode(params)
    try:
        data = runner("get_json")(url, timeout=40)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 — body may be unreadable
            body = ""
        # Re-raise the same HTTPError shape (run_connector still writes
        # ERROR.md with the code) but with the token scrubbed from the
        # URL, the reason, and the body. `from None` drops the original
        # exception so no traceback context carries the raw URL.
        raise urllib.error.HTTPError(
            _redact(getattr(exc, "filename", "") or OFFICIAL_URL, token),
            exc.code,
            _redact(exc.reason, token),
            exc.headers,
            io.BytesIO(_redact(body, token).encode("utf-8")),
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Threads keyword_search request failed: "
            + _redact(getattr(exc, "reason", exc), token)
        ) from None
    if not isinstance(data, dict):
        return []
    posts = data.get("data")
    return posts if isinstance(posts, list) else []


def _date_str(value):
    """'YYYY-MM-DDT...' -> 'YYYY-MM-DD'; epoch seconds -> UTC date; else ''."""
    if isinstance(value, (int, float)) and value > 0:
        return time.strftime("%Y-%m-%d", time.gmtime(value))
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else ""


def _flags(post):
    flags = []
    if post.get("is_reply"):
        flags.append("reply")
    if post.get("is_quote_post"):
        flags.append("quote post")
    if post.get("has_replies"):
        flags.append("has replies")
    return flags


def _render_official(query, posts):
    lines = [
        f"# Threads — posts by keyword: {query}\n",
        f"_Note: {NO_ENGAGEMENT_NOTE}._\n",
    ]
    if not posts:
        lines.append(f"_{EMPTY_RESULT_NOTE}_\n")
    for post in posts:
        username = str(post.get("username") or "?")
        lines.append(f"- **@{username}** — {_excerpt(post.get('text'))}")
        meta = [part for part in (_date_str(post.get("timestamp")),
                                  ", ".join(_flags(post))) if part]
        if meta:
            lines.append(f"  - {' · '.join(meta)}")
        if post.get("permalink"):
            lines.append(f"  - {post['permalink']}")
    return lines


# ---------------------------------------------------------------------------
# ScrapeCreators vendor path
# ---------------------------------------------------------------------------
def _first(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _subdict(raw, key):
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def _extract_vendor_items(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("posts", "threads", "items", "results", "searchResults",
                "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _normalize_vendor_post(raw):
    """Vendor post -> flat record; tolerant to field naming. None when there
    is nothing citable (no text and no link)."""
    if not isinstance(raw, dict):
        return None
    if isinstance(raw.get("thread"), dict):
        raw = raw["thread"]
    caption = raw.get("caption")
    caption_text = caption.get("text") if isinstance(caption, dict) else caption
    text = _first(raw.get("text"), caption_text, raw.get("title"))
    user = _subdict(raw, "user")
    owner = _subdict(raw, "owner")
    username = _first(user.get("username"), owner.get("username"),
                      raw.get("username"))
    url = _first(raw.get("permalink"), raw.get("url"), raw.get("link"))
    if not url and username and raw.get("code"):
        url = f"https://www.threads.net/@{username}/post/{raw['code']}"
    if not text and not url:
        return None
    return {
        "text": " ".join(str(text or "").split()),
        "username": username or "?",
        "url": url,
        "timestamp": _first(raw.get("timestamp"), raw.get("taken_at"),
                            raw.get("published_on")),
        "like_count": _to_int(raw.get("like_count")),
        "direct_reply_count": _to_int(raw.get("direct_reply_count")),
        "repost_count": _to_int(raw.get("repost_count")),
        "quote_count": _to_int(raw.get("quote_count")),
        "reshare_count": _to_int(raw.get("reshare_count")),
    }


def _vendor_fetch(query, key):
    url = SC_URL + "?" + urllib.parse.urlencode({"query": query})
    # Key rides in the x-api-key header, never in the URL.
    data = runner("get_json")(url, headers={"x-api-key": key}, timeout=60)
    posts = (_normalize_vendor_post(raw) for raw in _extract_vendor_items(data))
    return [p for p in posts if p]


def _render_vendor(query, ranked):
    lines = [
        f"# Threads — posts by keyword: {query}\n",
        f"_Cost: {COST_NOTE}._\n",
    ]
    if ranked.note:
        lines.append(f"_Note: {ranked.note}._\n")
    if not ranked.items:
        lines.append("_No posts matched this topic._\n")
    for post in ranked.items:
        lines.append(f"- **@{post['username']}** — {_excerpt(post['text'])}")
        lines.append(
            f"  - likes {post['like_count']:,}, "
            f"replies {post['direct_reply_count']:,}, "
            f"reposts {post['repost_count']:,}, "
            f"quotes {post['quote_count']:,}, "
            f"reshares {post['reshare_count']:,}"
        )
        date = _date_str(post.get("timestamp"))
        if date:
            lines.append(f"  - {date}")
        if post.get("url"):
            lines.append(f"  - {post['url']}")
    return lines


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------
def channel_threads(query, out_path, max_items):
    """Threads posts by keyword: official keyword_search (Meta TOP order,
    no engagement counts) or the ScrapeCreators vendor (engagement-ranked,
    pay-per-use) — path chosen from the configured keys + vendor env."""
    path, key = _select_path()
    if path == "official":
        limit = min(100, max(25, max_items * 3))
        posts = _official_fetch(query, key, limit)[:max_items]
        lines = _render_official(query, posts)
        shown = len(posts)
    else:
        posts = _vendor_fetch(query, key)
        ranked = runner("rank_items")(
            posts, query, text_key="text", engagement_key="like_count",
            comments_key="direct_reply_count", max_items=max_items,
        )
        lines = _render_vendor(query, ranked)
        shown = len(ranked.items)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return shown

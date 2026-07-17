"""Launch-radar connector (U12, R22/KTD7): what's shipping around a topic.

Free-first sub-sources, each isolated (one failing -> note line, siblings
continue), all verified by live probes on 2026-07-18:

  1. Show HN (Tier 0) — HN Algolia with `tags=show_hn` (probe: 553 hits for
     "AI research tools"; points/num_comments/created_at_i present).
  2. yc-oss (Tier 0) — `all.json` is ~10 MB, so the connector reads
     `meta.json` (~66 KB) and pulls only the most recent non-empty batch
     files (~100-300 KB each), filtering client-side by topic tokens against
     name + one_liner. yc-oss entries have NO vote fields, so their momentum
     is recency-only (launched_at / batch date) and the report says so.
  3. DevHunt (Tier 0, best-effort) — tools are listed as GitHub PRs to
     MarsX-dev/devhunt (probe: the repo named in early planning,
     sidiDev/dev-hunt, does NOT exist; MarsX-dev/devhunt is the real one,
     "Submit: <tool>" PRs searchable via search/issues).
  4. Product Hunt (token-gated) — GraphQL v2 with a Bearer token from
     `producthunt-token.txt` / PRODUCTHUNT_TOKEN. Query shape follows the
     documented v2 schema (posts by votes within the window; topic match is
     client-side); it is NOT live-verified without a token, and any API
     error degrades to an honest note. Without a token the report carries
     one honest line instead of a silent gap.
  5. MicroLaunch / Toolify — intentionally NOT built in v1: the plan marks
     them best-effort/opt-in scrapes, and an unverifiable scrape is worse
     than an honest absence. Nothing is emitted for them.

Scoring: launch momentum = bounded engagement (log votes) x recency decay
(half-life ~30 days) x maker-engagement factor (log comments) — a pure
function. Items below the shared rank_items relevance floor are dropped
before momentum. Category velocity = count of on-topic launches inside the
90-day window per sub-source, rendered as a saturation-signal header.

Helpers (get_json/post_json/gh_api/read_key/ranking) resolve through the
runner's live globals — see connectors/__init__.py.
"""
import math
import time
import urllib.parse
from datetime import datetime, timezone

from . import runner

HALF_LIFE_DAYS = 30.0          # launch buzz half-life for recency decay
VELOCITY_WINDOW_DAYS = 90      # category-velocity (saturation) window
_YC_RECENT_BATCHES = 4         # most recent non-empty batches to pull
_DEVHUNT_REPO = "MarsX-dev/devhunt"
_PH_URL = "https://api.producthunt.com/v2/api/graphql"
_PH_QUERY = """
query LaunchRadar($first: Int!, $postedAfter: DateTime!) {
  posts(first: $first, order: VOTES, postedAfter: $postedAfter) {
    edges { node {
      name tagline votesCount commentsCount createdAt url
      user { username name }
    } }
  }
}
"""

_YC_SEASON_MONTH = {"winter": 1, "spring": 4, "summer": 7, "fall": 10}


def _now():
    """Current epoch seconds — module-level so tests can freeze time."""
    return time.time()


def _parse_ts(value):
    """Best-effort timestamp -> epoch seconds. Accepts epoch numbers and
    ISO-8601 strings (Z or explicit offset). Returns None when unparsable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def launch_momentum(votes, comments, age_days, half_life_days=HALF_LIFE_DAYS):
    """Pure launch-momentum score.

    engagement (log votes, where available) x recency decay (half-life
    ~30 days) x maker-engagement factor (log comments, where available).
    votes=None means the source has no vote fields (yc-oss) -> the base is
    1.0 and the score is recency-only.
    """
    decay = 0.5 ** (max(float(age_days), 0.0) / half_life_days)
    if votes is None:
        base = 1.0
    else:
        base = 1.0 + math.log10(1.0 + max(float(votes), 0.0))
    if comments is not None:
        base *= 1.0 + 0.25 * math.log10(1.0 + max(float(comments), 0.0))
    return base * decay


def _launch(name, source, url, created_ts, now, votes=None, comments=None,
            detail=""):
    age_days = max((now - created_ts) / 86400.0, 0.0) if created_ts else 3650.0
    return {
        "name": name,
        "source": source,
        "url": url,
        "date": time.strftime("%Y-%m-%d", time.gmtime(created_ts))
        if created_ts else "?",
        "age_days": age_days,
        "votes": votes,
        "comments": comments,
        "detail": detail,
        "momentum": launch_momentum(votes, comments, age_days),
    }


def _fetch_show_hn(topic, now, pool):
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(
        {"query": topic, "tags": "show_hn", "hitsPerPage": pool}
    )
    data = runner("get_json")(url, timeout=20)
    launches = []
    for h in data.get("hits") or []:
        title = h.get("title") or h.get("story_title") or "?"
        obj = h.get("objectID", "")
        created = h.get("created_at_i") or _parse_ts(h.get("created_at"))
        launches.append(_launch(
            title,
            "ShowHN",
            h.get("url") or f"https://news.ycombinator.com/item?id={obj}",
            created,
            now,
            votes=h.get("points") or 0,
            comments=h.get("num_comments") or 0,
        ))
    return launches


def _yc_batch_recency(slug):
    """Sortable (year, month) for slugs like 'summer-2026'; None otherwise."""
    parts = slug.lower().rsplit("-", 1)
    if len(parts) != 2 or parts[0] not in _YC_SEASON_MONTH:
        return None
    try:
        year = int(parts[1])
    except ValueError:
        return None
    return (year, _YC_SEASON_MONTH[parts[0]])


def _fetch_yc(topic, now, pool):
    meta = runner("get_json")(
        "https://yc-oss.github.io/api/meta.json", timeout=25
    )
    batches = []
    for slug, info in (meta.get("batches") or {}).items():
        key = _yc_batch_recency(slug)
        if key is None or not (info.get("count") or 0):
            continue
        if info.get("api"):
            batches.append((key, slug, info["api"]))
    batches.sort(reverse=True)
    launches = []
    for key, slug, api_url in batches[:_YC_RECENT_BATCHES]:
        year, month = key
        batch_fallback_ts = _parse_ts(f"{year:04d}-{month:02d}-01T00:00:00Z")
        for company in runner("get_json")(api_url, timeout=30) or []:
            created = _parse_ts(company.get("launched_at")) or batch_fallback_ts
            one_liner = company.get("one_liner") or ""
            launches.append(_launch(
                f"{company.get('name') or '?'} — {one_liner}".rstrip(" —"),
                "YC",
                company.get("url") or company.get("website") or "?",
                created,
                now,
                votes=None,       # yc-oss has no vote fields: recency-only
                comments=None,
                detail=company.get("batch") or slug,
            ))
        if len(launches) >= pool:
            break
    return launches


def _fetch_devhunt(topic, now, pool):
    found = runner("gh_api")(
        "search/issues?" + urllib.parse.urlencode(
            {"q": f"repo:{_DEVHUNT_REPO} is:pr {topic}", "per_page": pool}
        )
    )
    launches = []
    for it in found.get("items") or []:
        reactions = (it.get("reactions") or {}).get("total_count") or 0
        launches.append(_launch(
            it.get("title") or "?",
            "DevHunt",
            it.get("html_url") or "?",
            _parse_ts(it.get("created_at")),
            now,
            votes=reactions,
            comments=it.get("comments") or 0,
        ))
    return launches


def _fetch_product_hunt(topic, now, pool, token):
    posted_after = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - VELOCITY_WINDOW_DAYS * 86400)
    )
    data = runner("post_json")(
        _PH_URL,
        {"query": _PH_QUERY,
         "variables": {"first": pool, "postedAfter": posted_after}},
        {"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    edges = (((data.get("data") or {}).get("posts") or {}).get("edges")) or []
    launches = []
    for edge in edges:
        node = edge.get("node") or {}
        maker = (node.get("user") or {}).get("username") or ""
        tagline = node.get("tagline") or ""
        launches.append(_launch(
            f"{node.get('name') or '?'} — {tagline}".rstrip(" —"),
            "PH",
            node.get("url") or "?",
            _parse_ts(node.get("createdAt")),
            now,
            votes=node.get("votesCount") or 0,
            comments=node.get("commentsCount") or 0,
            detail=f"by @{maker}" if maker else "",
        ))
    return launches


def channel_launch_radar(query, out_path, max_items):
    """Aggregate Show HN + yc-oss + DevHunt (+ Product Hunt with a token)
    into one momentum-ranked launch report with a category-velocity header."""
    now = _now()
    pool = min(50, max(30, max_items * 3))
    relevance_score = runner("relevance_score")
    floor = runner("RELEVANCE_FLOOR")

    notes = []
    launches = []
    fetched_sources = []
    for label, fetch in (
        ("ShowHN", _fetch_show_hn),
        ("YC", _fetch_yc),
        ("DevHunt", _fetch_devhunt),
    ):
        try:
            launches.extend(fetch(query, now, pool))
            fetched_sources.append(label)
        except Exception as e:  # noqa: BLE001 — one source never kills siblings
            notes.append(
                f"{label}: unavailable — {type(e).__name__}: {str(e)[:120]}"
            )

    ph_token = runner("read_key")(
        ["producthunt-token.txt"], r"[A-Za-z0-9_\-]{20,}", "PRODUCTHUNT_TOKEN"
    )
    if not ph_token:
        notes.append("PH: token not configured (free read token unlocks it)")
    else:
        try:
            launches.extend(_fetch_product_hunt(query, now, pool, ph_token))
            fetched_sources.append("PH")
        except Exception as e:  # noqa: BLE001
            notes.append(
                f"PH: unavailable — {type(e).__name__}: {str(e)[:120]}"
            )

    # Relevance floor (shared with rank_items): drop off-topic launches so a
    # viral off-topic item can't dominate momentum or inflate velocity.
    on_topic = [
        it for it in launches if relevance_score(it["name"], query) >= floor
    ]
    if launches and not on_topic:
        notes.append(
            "no launch cleared the topic-relevance floor; "
            "showing best-effort matches (may be off-topic)"
        )
        on_topic = launches
    on_topic.sort(key=lambda it: -it["momentum"])

    velocity = {label: 0 for label in fetched_sources}
    for it in on_topic:
        if it["age_days"] <= VELOCITY_WINDOW_DAYS and it["source"] in velocity:
            velocity[it["source"]] += 1
    total_recent = sum(velocity.values())

    lines = [f"# Launch radar — what's shipping for: {query}\n"]
    per_source = " · ".join(f"{k}: {v}" for k, v in velocity.items()) or "none"
    lines.append(
        f"**Category velocity: {total_recent} similar launches in the last "
        f"{VELOCITY_WINDOW_DAYS} days** ({per_source}) — saturation signal.\n"
    )
    lines.append(
        "_Momentum = log-votes × recency decay (half-life "
        f"~{HALF_LIFE_DAYS:.0f}d) × comment factor. YC entries carry no vote "
        "fields, so their momentum is recency-only (launch/batch date)._\n"
    )
    shown = on_topic[:max_items]
    if not shown:
        lines.append("_No launches found._\n")
    for it in shown:
        stats = []
        if it["votes"] is not None:
            stats.append(f"{it['votes']} votes")
        if it["comments"] is not None:
            stats.append(f"{it['comments']} comments")
        if it["source"] == "YC":
            stats.append("recency-only")
        if it["detail"]:
            stats.append(it["detail"])
        stat_s = (", " + ", ".join(stats)) if stats else ""
        lines.append(
            f"- **{it['name']}** [{it['source']}] — "
            f"momentum {it['momentum']:.2f}{stat_s}, {it['date']}"
        )
        lines.append(f"  - {it['url']}")
    if notes:
        lines.append("")
        for note in notes:
            lines.append(f"_{note}._")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(shown)

"""Revenue/exit-radar connector (U13, R22/KTD7): what's selling / sold.

Free sub-sources, each isolated (one failing -> note line, siblings
continue), verified by live probes on 2026-07-18:

  1. Flippa sold listings (Tier 0) — `api.flippa.com/v3/listings` answers
     WITHOUT auth. Probe findings: `filter[status]=won` = 1,100 sold
     auctions with real final prices (current_price), profit/revenue per
     month, property_type and ends_at; `filter[status]=sold` = 0;
     `search_template=json` on flippa.com = HTTP 500; there is NO
     server-side text search (unknown filter names 400, a bare `q` is
     ignored). So the connector pulls recent sold pages (sort=-ends_at) and
     matches the topic client-side via the shared relevance floor. The JSON
     API being open means no HTML scraping fallback is needed; an API
     failure degrades to an honest note instead.
  2. Substack leaderboards (Tier 0) — `substack.com/api/v1/categories` +
     `api/v1/category/public/{id}/all?page=0` return the public leaderboard
     (25 publications) with bestseller TIER wording (`rankingDetail`, e.g.
     "Tens of thousands of paid subscribers") and a numeric tier
     (`author_bestseller_tier`). Substack publishes tier RANGES, not
     revenue — the report renders tier wording verbatim and NEVER invents
     ARR numbers.
  3. Whop Trends / Gumtrends — paid datasets, intentionally NOT built:
     each gets one honest "opt-in, not configured (paid dataset)" line and
     zero network calls. Decision recorded in the plan: if they are ever
     added, the default integration is a thin REST wrapper owned first-party
     (per the borrowing-customs rule); an MCP package would need a trust
     review before touching the harness.

Ranking: realized money first — Flippa sold price DESC (with profit/revenue
multiple where the listing carries numbers), Substack grouped by bestseller
tier DESC then leaderboard position. Never by votes/bids. Niche map:
Flippa -> microsaas, Substack -> infoproducts.

Helpers (get_json/ranking) resolve through the runner's live globals — see
connectors/__init__.py.
"""
import urllib.parse

from . import runner

_FLIPPA_API = "https://api.flippa.com/v3/listings"
_FLIPPA_PAGES = 2
_FLIPPA_PAGE_SIZE = 100
_SUBSTACK_API = "https://substack.com/api/v1"
_DEFAULT_CATEGORY = (4, "Technology")  # probe: id 4 = technology


def _fetch_flippa_sold(pool_pages=_FLIPPA_PAGES):
    listings = []
    for page in range(1, pool_pages + 1):
        url = _FLIPPA_API + "?" + urllib.parse.urlencode({
            "filter[status]": "won",       # probe: 'won' = sold auctions
            "page[size]": _FLIPPA_PAGE_SIZE,
            "page[number]": page,
            "sort": "-ends_at",            # most recently sold first
        })
        data = runner("get_json")(url, timeout=30)
        listings.extend(data.get("data") or [])
        if not (data.get("links") or {}).get("next"):
            break
    return listings


def _flippa_multiple(price, profit_pm, revenue_pm):
    """'≈N.N× annual profit/revenue' from the listing's own numbers; empty
    string when the listing carries none (never invented)."""
    try:
        price = float(price or 0)
        profit = float(profit_pm or 0)
        revenue = float(revenue_pm or 0)
    except (TypeError, ValueError):
        return ""
    if price <= 0:
        return ""
    if profit > 0:
        return f"≈{price / (profit * 12):.1f}× annual profit"
    if revenue > 0:
        return f"≈{price / (revenue * 12):.1f}× annual revenue"
    return ""


def _render_flippa(topic, max_items):
    relevance_score = runner("relevance_score")
    floor = runner("RELEVANCE_FLOOR")
    listings = _fetch_flippa_sold()
    rows, note = [], None
    for it in listings:
        price = it.get("current_price") or it.get("display_price") or 0
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = 0.0
        if price <= 0:
            continue
        text = " ".join(
            str(it.get(k) or "")
            for k in ("title", "summary", "property_type")
        )
        rows.append({
            "title": it.get("title") or "?",
            "price": price,
            "multiple": _flippa_multiple(
                price, it.get("profit_per_month"), it.get("revenue_per_month")
            ),
            "type": it.get("property_type") or "?",
            "sold": (it.get("ends_at") or "")[:10],
            "url": it.get("html_url") or "?",
            "relevance": relevance_score(text, topic),
        })
    on_topic = [r for r in rows if r["relevance"] >= floor]
    if rows and not on_topic:
        note = (
            "no sold listing matched the topic tokens; showing the "
            "highest-priced recent sales instead (may be off-topic)"
        )
        on_topic = rows
    # Realized price DESC — never votes/bids.
    on_topic.sort(key=lambda r: -r["price"])
    lines = [
        f"## Flippa — sold listings (realized prices) for: {topic}",
        "_Source: api.flippa.com sold ('won') auctions, most recent pages, "
        "ordered by final sale price._",
        "",
    ]
    if note:
        lines.append(f"_Note: {note}._\n")
    shown = on_topic[:max_items]
    if not shown:
        lines.append("_No sold listings found._")
    for r in shown:
        mult = f", {r['multiple']}" if r["multiple"] else ""
        lines.append(
            f"- **${r['price']:,.0f}** — {r['title']} "
            f"({r['type']}{mult}, sold {r['sold'] or '?'})"
        )
        lines.append(f"  - {r['url']}")
    return lines, len(shown)


def _pick_category(categories, topic):
    """Pick the Substack category whose name/slug tokens appear in the
    topic; default to Technology (honest note upstream when defaulted)."""
    tokens = set(runner("_rank_tokens")(topic))
    best, best_score = None, 0
    for cat in categories or []:
        cat_tokens = set(runner("_rank_tokens")(
            f"{cat.get('name') or ''} {cat.get('slug') or ''}"
        ))
        score = len(tokens & cat_tokens)
        if score > best_score:
            best, best_score = cat, score
    if best is not None:
        return best.get("id"), best.get("name") or best.get("slug") or "?", True
    return _DEFAULT_CATEGORY[0], _DEFAULT_CATEGORY[1], False


def _substack_tier(pub):
    """Numeric bestseller tier for ordering: the bestseller badge tier, or
    the paid-subscriber order of magnitude when the wording is about paid
    subscribers. Publications without a paid tier sort last."""
    tier = pub.get("author_bestseller_tier") or 0
    detail = (pub.get("rankingDetail") or "").lower()
    if "paid" in detail:
        tier = max(tier, pub.get("rankingDetailOrderOfMagnitude") or 0)
    return tier


def _render_substack(topic, max_items):
    categories = runner("get_json")(f"{_SUBSTACK_API}/categories", timeout=25)
    cat_id, cat_name, matched = _pick_category(categories, topic)
    data = runner("get_json")(
        f"{_SUBSTACK_API}/category/public/{cat_id}/all?page=0", timeout=25
    )
    pubs = data.get("publications") or []
    ordered = sorted(
        enumerate(pubs), key=lambda pair: (-_substack_tier(pair[1]), pair[0])
    )
    lines = [
        f"## Substack — {cat_name} leaderboard (bestseller tiers)",
        "_Substack publishes bestseller tiers (subscriber ranges), not "
        "revenue — tier wording below is verbatim, no revenue estimates._",
        "",
    ]
    if not matched:
        lines.append(
            f"_Note: no category matched the topic tokens; defaulting to "
            f"{cat_name}._\n"
        )
    shown = ordered[:max_items]
    if not shown:
        lines.append("_No leaderboard publications found._")
    for pos, pub in shown:
        tier_wording = pub.get("rankingDetail") or "no bestseller badge"
        free = pub.get("freeSubscriberCountOrderOfMagnitude") or ""
        free_s = f", {free} free subscribers" if free else ""
        author = pub.get("author_name") or "?"
        lines.append(
            f"- **{pub.get('name') or '?'}** — {author}; tier: "
            f"{tier_wording}{free_s} (leaderboard #{pos + 1})"
        )
        url = pub.get("base_url") or (
            f"https://{pub.get('hostname')}" if pub.get("hostname") else "?"
        )
        lines.append(f"  - {url}")
    return lines, len(shown)


def channel_revenue_radar(query, out_path, max_items):
    """Aggregate realized-revenue signal: Flippa sold prices + Substack
    bestseller tiers; Whop/Gumtrends stay honest opt-in stubs."""
    lines = [
        f"# Revenue radar — what's selling for: {query}\n",
        "_Niche map: Flippa → microsaas · Substack → infoproducts._\n",
    ]
    total = 0
    for label, render in (
        ("Flippa", _render_flippa),
        ("Substack", _render_substack),
    ):
        try:
            section, n = render(query, max_items)
        except Exception as e:  # noqa: BLE001 — one source never kills siblings
            lines.append(
                f"_{label}: unavailable — {type(e).__name__}: {str(e)[:120]}._\n"
            )
            continue
        lines.extend(section)
        lines.append("")
        total += n
    lines.append("## Opt-in paid sources (not configured)")
    lines.append("- Whop Trends: opt-in, not configured (paid dataset).")
    lines.append("- Gumtrends: opt-in, not configured (paid dataset).")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return total

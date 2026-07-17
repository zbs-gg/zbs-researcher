"""Meta Ad Library connector (U8, R6): money signal — who is PAYING to
advertise around a topic. Running ads for months = someone believes the
topic converts; that is a stronger commercial signal than any upvote.

Source: the official Meta Ad Library API (graph.facebook.com ads_archive),
free with an access token (Meta requires identity confirmation + App Review
for Ad Library API access; the token itself costs nothing).

Honest scope: the connector queries EU reach countries (DE/FR/NL/ES/IT/PL)
on purpose — the DSA forces Meta to expose FULL commercial-ad detail
(delivery dates, eu_total_reach, snapshot urls) for ads reaching the EU.
Outside the EU (e.g. the US) the Ad Library carries political/issue ads
only, so an EU query is where the commercial money signal actually lives —
and the report says so instead of pretending global coverage.

Aggregation: ads are grouped BY ADVERTISER (page_name) — the unit of "who
is spending" — with ads-matched / still-delivering counts, summed EU reach,
the longest delivery run and its running-since date, and one sample
snapshot url for manual verification. Sustained-spend proxy = longest
delivery duration x log-scaled total reach: Meta publishes reach, never
spend, for commercial ads, so nothing here is a revenue estimate and the
report never invents one.

Token gating: the connector declares `requires=["meta_ads"]`, so
select_connectors auto-skips it without a token and records the missing key
in the manifest — that IS the honest degrade. An HTTP 400 carrying an OAuth
error raises a clear token/App-Review message (surfaced via ERROR.md);
rate-limit and other HTTP failures propagate untouched.

Helpers (get_json / KEYS) resolve through the runner's live globals — see
connectors/__init__.py.
"""
import calendar
import math
import time
import urllib.error
import urllib.parse

from . import runner

AD_LIBRARY_URL = "https://graph.facebook.com/v21.0/ads_archive"
# EU default (R6): full commercial detail is EU-only under the DSA.
EU_COUNTRIES = ("DE", "FR", "NL", "ES", "IT", "PL")
_FIELDS = ",".join((
    "page_name",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "eu_total_reach",
    "ad_snapshot_url",
    "publisher_platforms",
))
_TOKEN_GUIDANCE = (
    "Meta Ad Library rejected the access token (HTTP 400 OAuth error). "
    "Ad Library API tokens expire and require Meta identity confirmation "
    "plus App Review approval for the Ad Library API — regenerate the token "
    "at https://www.facebook.com/ads/library/api/ and update "
    "meta-ads-token.txt (or META_ADS_TOKEN)."
)


def _now():
    """Current epoch seconds — module-level so tests can freeze time."""
    return time.time()


def _parse_day(value):
    """'YYYY-MM-DD[T...]' -> epoch seconds at UTC midnight; None if absent
    or unparsable (Ad Library delivery times are date-first strings)."""
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return calendar.timegm(time.strptime(text, "%Y-%m-%d"))
    except ValueError:
        return None


def spend_proxy(longest_days, total_reach):
    """Sustained-spend proxy: longest delivery duration x log-scaled reach.

    Pure function. Meta publishes reach, never spend, for commercial ads —
    this orders advertisers by "paid for a long time to reach many people"
    and is NOT a revenue estimate.
    """
    days = max(float(longest_days or 0), 0.0)
    reach = max(float(total_reach or 0), 0.0)
    return (1.0 + days) * (1.0 + math.log10(1.0 + reach))


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _fetch_ads(query, token, pool):
    params = {
        "search_terms": query,
        # Meta's documented list-literal format for country arrays.
        "ad_reached_countries": "[" + ",".join(f"'{c}'" for c in EU_COUNTRIES) + "]",
        "ad_type": "ALL",
        "fields": _FIELDS,
        "limit": pool,
        "access_token": token,
    }
    url = AD_LIBRARY_URL + "?" + urllib.parse.urlencode(params)
    try:
        data = runner("get_json")(url, timeout=40)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 — body may be unreadable
            detail = ""
        if e.code == 400 and ("oauth" in detail.lower()
                              or "access token" in detail.lower()):
            raise RuntimeError(_TOKEN_GUIDANCE) from e
        raise  # rate limits and everything else propagate untouched
    return data.get("data") or []


def channel_meta_ads(query, out_path, max_items):
    """Aggregate Meta Ad Library matches by advertiser: ad counts, EU reach,
    longest delivery run — a sustained-spend (money) signal for the topic."""
    token = runner("KEYS").get("meta_ads") or ""
    if not token:
        # select_connectors gates on requires=["meta_ads"] before this runs;
        # a direct call without a token still fails honestly.
        raise RuntimeError(
            "Meta Ad Library token not configured — put it in "
            "meta-ads-token.txt or META_ADS_TOKEN (free; requires Meta "
            "identity confirmation + App Review for Ad Library API access)."
        )
    now = _now()
    pool = min(100, max(50, max_items * 5))
    ads = _fetch_ads(query, token, pool)

    advertisers = {}
    for item in ads:
        page = item.get("page_name") or "?"
        start_ts = _parse_day(item.get("ad_delivery_start_time"))
        stop_raw = item.get("ad_delivery_stop_time")
        stop_ts = _parse_day(stop_raw)
        active = not stop_raw
        end_ts = now if active or stop_ts is None else stop_ts
        run_days = max((end_ts - start_ts) / 86400.0, 0.0) if start_ts else 0.0
        adv = advertisers.setdefault(page, {
            "ads": 0,
            "active": 0,
            "reach": 0,
            "longest_days": 0.0,
            "since_ts": None,
            "snapshot": "",
            "platforms": set(),
        })
        adv["ads"] += 1
        adv["active"] += 1 if active else 0
        adv["reach"] += _to_int(item.get("eu_total_reach"))
        adv["longest_days"] = max(adv["longest_days"], run_days)
        if start_ts is not None and (
            adv["since_ts"] is None or start_ts < adv["since_ts"]
        ):
            adv["since_ts"] = start_ts
        if not adv["snapshot"] and item.get("ad_snapshot_url"):
            adv["snapshot"] = item["ad_snapshot_url"]
        for platform in item.get("publisher_platforms") or []:
            adv["platforms"].add(str(platform))

    ordered = sorted(
        advertisers.items(),
        key=lambda kv: -spend_proxy(kv[1]["longest_days"], kv[1]["reach"]),
    )
    shown = ordered[:max_items]

    lines = [f"# Meta Ad Library — who's paying to advertise: {query}\n"]
    lines.append(
        "_Scope: EU only ("
        + ", ".join(EU_COUNTRIES)
        + ") — the DSA forces full commercial-ad transparency for ads "
        "reaching the EU; outside the EU (e.g. US) the Ad Library exposes "
        "political/issue ads only, so the commercial money signal lives "
        "here._\n"
    )
    lines.append(
        "_Sustained-spend proxy = longest ad runtime x log-scaled EU reach. "
        "Meta publishes reach, never spend, for commercial ads — nothing "
        "below is a revenue estimate._\n"
    )
    if not shown:
        lines.append("_No ads matched this topic in the EU Ad Library._\n")
    for page, adv in shown:
        since = (
            time.strftime("%Y-%m-%d", time.gmtime(adv["since_ts"]))
            if adv["since_ts"] is not None else "?"
        )
        lines.append(
            f"- **{page}** — {adv['ads']} ads matched "
            f"({adv['active']} still delivering), "
            f"EU reach >={adv['reach']:,}, "
            f"longest run {adv['longest_days']:.0f}d, running since {since}"
        )
        if adv["platforms"]:
            lines.append(f"  - platforms: {', '.join(sorted(adv['platforms']))}")
        if adv["snapshot"]:
            lines.append(f"  - sample snapshot: {adv['snapshot']}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(shown)

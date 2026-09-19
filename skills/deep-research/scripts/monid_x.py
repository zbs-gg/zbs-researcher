"""Optional direct-X retrieval through Monid's HTTPS API.

The paid boundary is deliberately narrow: discover and inspect are free, then
the caller is told the exact compatible route and quoted price before `run` is
sent. Unknown catalog routes fail closed. This module never reads credentials;
the runner passes the already-resolved key.

Stdlib only, Windows-safe, and fully injectable for offline tests.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, NamedTuple


API_BASE = "https://api.monid.ai/v1"
DISCOVERY_QUERY = "twitter X posts search by keyword with author date engagement"
TERMINAL_OK = {"COMPLETED", "SUCCEEDED"}
TERMINAL_ERROR = {"FAILED", "CANCELLED", "CANCELED"}


class MonidError(RuntimeError):
    pass


class MonidRouteError(MonidError):
    pass


class MonidRunError(MonidError):
    pass


class MonidTimeout(MonidError):
    pass


class Route(NamedTuple):
    provider: str
    endpoint: str
    price_type: str
    price_usd: float
    currency: str
    adapter: str


class SearchResult(NamedTuple):
    route: Route
    run_id: str
    posts: list[dict[str, Any]]
    usage: dict[str, Any]


_ADAPTERS = {
    ("tikhub", "/api/v1/twitter/web/fetch_search_timeline"): "tikhub-search",
    ("apify", "/apidojo/tweet-scraper"): "apify-tweet-scraper",
}


def _authorized_transport(api_key: str):
    def request_json(method: str, path: str, body=None, timeout: float = 30):
        url = f"{API_BASE}/{path.lstrip('/')}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read(4096).decode("utf-8", "replace")
            except Exception:
                detail = str(exc)
            finally:
                exc.close()
            raise MonidError(f"Monid HTTP {exc.code}: {detail[:800]}") from exc

    return request_json


def _price(price: Any) -> tuple[str, float, str]:
    if not isinstance(price, dict):
        raise MonidRouteError("compatible Monid route has no inspectable price")
    price_type = str(price.get("type") or "").upper()
    amount = price.get("amount")
    currency = price.get("currency")
    if isinstance(amount, dict):
        currency = amount.get("currency") or currency
        amount = amount.get("value")
    if (
        price_type not in {"PER_CALL", "PER_RESULT"}
        or isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or amount < 0
        or str(currency or "").upper() != "USD"
    ):
        raise MonidRouteError("compatible Monid route has an unsupported price")
    return price_type, float(amount), "USD"


def _select_route(discovery: Any, request_json) -> Route:
    rows = discovery.get("results") if isinstance(discovery, dict) else None
    if not isinstance(rows, list):
        raise MonidRouteError("Monid discovery returned no compatible X route")
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("provider") or ""), str(row.get("endpoint") or ""))
        adapter = _ADAPTERS.get(key)
        if not adapter:
            continue
        _, inspected = request_json(
            "POST", "inspect", {"provider": key[0], "endpoint": key[1]}, 30
        )
        if not isinstance(inspected, dict) or (
            inspected.get("provider"), inspected.get("endpoint")
        ) != key:
            raise MonidRouteError("Monid route inspection did not match discovery")
        price_type, amount, currency = _price(inspected.get("price"))
        return Route(key[0], key[1], price_type, amount, currency, adapter)
    raise MonidRouteError("Monid discovery returned no compatible X route")


def _run_input(route: Route, query: str, max_items: int) -> dict[str, Any]:
    if route.adapter == "tikhub-search":
        return {"queryParams": {"keyword": query, "search_type": "Latest"}}
    if route.adapter == "apify-tweet-scraper":
        return {"searchTerms": [query], "maxItems": max_items, "sort": "Latest"}
    raise MonidRouteError(f"unsupported Monid route adapter: {route.adapter}")


def _items_from_output(output: Any) -> list[Any]:
    if isinstance(output, list):
        if len(output) == 1 and isinstance(output[0], dict):
            for key in ("timeline", "items", "results", "data"):
                nested = output[0].get(key)
                if isinstance(nested, list):
                    return nested
        return output
    if isinstance(output, dict):
        for key in ("timeline", "items", "results", "data"):
            value = output.get(key)
            if isinstance(value, list):
                return value
    return []


def _first(mapping: Any, *keys: str):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def normalize_posts(output: Any, max_items: int) -> list[dict[str, Any]]:
    limit = max(0, int(max_items))
    if limit == 0:
        return []
    posts = []
    for raw in _items_from_output(output):
        if not isinstance(raw, dict):
            continue
        if raw.get("type") not in (None, "tweet", "post"):
            continue
        user = raw.get("user_info") or raw.get("author") or raw.get("user") or {}
        tweet_id = _first(raw, "tweet_id", "id", "rest_id")
        handle = _first(raw, "screen_name", "username", "userName") or _first(
            user, "screen_name", "username", "userName"
        )
        author_name = _first(user, "name", "display_name", "displayName")
        created_at = _first(raw, "created_at", "createdAt", "timestamp")
        text = _first(raw, "text", "full_text", "fullText")
        url = _first(raw, "url", "tweet_url", "tweetUrl")
        if not url and tweet_id:
            if handle:
                url = f"https://x.com/{handle}/status/{tweet_id}"
            else:
                url = f"https://x.com/i/web/status/{tweet_id}"
        posts.append({
            "tweet_id": str(tweet_id) if tweet_id is not None else None,
            "screen_name": str(handle) if handle is not None else None,
            "author_name": str(author_name) if author_name is not None else None,
            "created_at": str(created_at) if created_at is not None else None,
            "text": str(text) if text is not None else None,
            "url": str(url) if url is not None else None,
            "favorites": _first(raw, "favorites", "favorite_count", "likeCount"),
            "retweets": _first(raw, "retweets", "retweet_count", "repostCount"),
            "replies": _first(raw, "replies", "reply_count", "replyCount"),
            "quotes": _first(raw, "quotes", "quote_count", "quoteCount"),
            "bookmarks": _first(raw, "bookmarks", "bookmark_count", "bookmarkCount"),
            "views": _first(raw, "views", "view_count", "viewCount"),
        })
        if len(posts) >= limit:
            break
    return posts


def _dollars(cost: Any) -> tuple[float, str] | None:
    if not isinstance(cost, dict):
        return None
    value = cost.get("value")
    unit = str(cost.get("unit") or "DOLLAR").upper()
    currency = str(cost.get("currency") or "USD").upper()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or currency != "USD":
        return None
    divisors = {"DOLLAR": 1.0, "USD": 1.0, "CENT": 100.0, "MICRO_DOLLAR": 1_000_000.0}
    divisor = divisors.get(unit)
    if divisor is None:
        return None
    return float(value) / divisor, unit


def _usage(route: Route, result: dict[str, Any], posts: list[dict[str, Any]]):
    usage = {
        "provider": "monid",
        "route_provider": route.provider,
        "endpoint": route.endpoint,
        "run_id": str(result.get("runId") or ""),
        "result_count": result.get("resultCount")
        if isinstance(result.get("resultCount"), int)
        else len(posts),
        "price_type": route.price_type,
        "listed_cost": route.price_usd,
        "listed_cost_basis": route.price_type,
        "currency": route.currency,
        "cost_status": "quoted",
    }
    billing = result.get("billing")
    actual = _dollars(billing.get("actualCost")) if isinstance(billing, dict) else None
    if actual is not None:
        usage["cost"] = actual[0]
        usage["cost_status"] = "actual"
        usage["billing_unit"] = actual[1]
    return usage


def search(
    api_key: str,
    query: str,
    max_items: int = 10,
    *,
    request_json: Callable | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    announce: Callable[[Route], None] | None = None,
    max_wait_seconds: float = 300,
    poll_interval_seconds: float = 2,
) -> SearchResult:
    """Discover, inspect, announce, then execute one explicit X search."""
    if not api_key:
        raise MonidError("Monid API key is missing")
    if isinstance(max_items, bool) or not isinstance(max_items, int) or max_items <= 0:
        raise MonidError("max_items must be a positive integer")
    request_json = request_json or _authorized_transport(api_key)
    _, discovery = request_json(
        "POST", "discover", {"query": DISCOVERY_QUERY, "limit": 10}, 30
    )
    route = _select_route(discovery, request_json)
    if announce is not None:
        announce(route)

    _, result = request_json(
        "POST",
        "run",
        {
            "provider": route.provider,
            "endpoint": route.endpoint,
            "input": _run_input(route, query, max_items),
        },
        60,
    )
    if not isinstance(result, dict):
        raise MonidRunError("Monid run returned a non-object response")
    run_id = str(result.get("runId") or "")
    started = clock()
    while str(result.get("status") or "").upper() == "RUNNING":
        if clock() - started >= max_wait_seconds:
            raise MonidTimeout(
                f"Monid run {run_id or '?'} timed out after {max_wait_seconds:g}s"
            )
        sleep(poll_interval_seconds)
        _, result = request_json("GET", f"runs/{run_id}", None, 60)
        if not isinstance(result, dict):
            raise MonidRunError("Monid poll returned a non-object response")

    status = str(result.get("status") or "").upper()
    if status in TERMINAL_ERROR or status not in TERMINAL_OK:
        raise MonidRunError(f"Monid run {run_id or '?'} ended with status={status or 'UNKNOWN'}")
    provider_response = result.get("providerResponse") or {}
    provider_status = provider_response.get("httpStatus") if isinstance(provider_response, dict) else None
    if isinstance(provider_status, int) and not 200 <= provider_status < 300:
        raise MonidRunError(
            f"Monid route {route.provider}{route.endpoint} returned HTTP {provider_status}"
        )
    posts = normalize_posts(result.get("output"), max_items)
    return SearchResult(route, run_id, posts, _usage(route, result, posts))

"""Direct X via Monid contract tests.

Offline only: every discover, inspect, run, and poll response is supplied by a
fixture transport. No test can reach Monid or spend money.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"
MONID_X = SCRIPTS / "monid_x.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


monid_x = _load("monid_x_tests", MONID_X)
deep_research = _load("deep_research_monid_x_tests", RUNNER)


TIKHUB = ("tikhub", "/api/v1/twitter/web/fetch_search_timeline")
APIFY = ("apify", "/apidojo/tweet-scraper")


def discovered(provider="tikhub", endpoint=TIKHUB[1], price=0.0015):
    return {
        "results": [{
            "provider": provider,
            "endpoint": endpoint,
            "description": "Search X posts",
            "price": {
                "type": "PER_CALL",
                "amount": {"value": price, "currency": "USD"},
            },
        }],
        "count": 1,
    }


def inspected(provider="tikhub", endpoint=TIKHUB[1], price=0.0015):
    return {
        "provider": provider,
        "endpoint": endpoint,
        "summary": "keyword, search_type, cursor",
        "price": {
            "type": "PER_CALL",
            "amount": {"value": price, "currency": "USD"},
        },
    }


def tweet(**overrides):
    row = {
        "type": "tweet",
        "tweet_id": "2087425826262598063",
        "screen_name": "builder",
        "created_at": "Wed Aug 12 06:27:54 +0000 2026",
        "text": "Real practitioner complaint",
        "favorites": 379,
        "retweets": 39,
        "replies": 13,
        "quotes": 3,
        "bookmarks": 243,
        "views": "30229",
        "user_info": {"name": "Builder Name", "screen_name": "builder"},
    }
    row.update(overrides)
    return row


class FixtureTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, path, body=None, timeout=30):
        self.calls.append({"method": method, "path": path, "body": body, "timeout": timeout})
        if not self.responses:
            raise AssertionError(f"unexpected request {method} {path}")
        return self.responses.pop(0)


class MonidRunTests(unittest.TestCase):
    def test_non_positive_item_limit_fails_before_discovery_or_paid_run(self):
        transport = FixtureTransport([])
        with self.assertRaisesRegex(monid_x.MonidError, "positive integer"):
            monid_x.search(
                "monid_test_secret", "q", 0, request_json=transport,
                sleep=lambda _: None, announce=lambda _: self.fail("must not announce"),
            )
        self.assertEqual(transport.calls, [])

    def test_discovers_inspects_announces_then_runs_and_polls_tikhub(self):
        transport = FixtureTransport([
            (200, discovered()),
            (200, inspected()),
            (202, {
                "runId": "run-1", "status": "RUNNING",
                "price": inspected()["price"],
            }),
            (200, {
                "runId": "run-1", "status": "COMPLETED",
                "providerResponse": {"httpStatus": 200},
                "output": {"status": "ok", "timeline": [tweet()]},
                "resultCount": 1,
                "price": inspected()["price"],
                "billing": None,
            }),
        ])
        events = []
        result = monid_x.search(
            "monid_test_secret", "proposal AI", 7,
            request_json=transport, sleep=lambda _: events.append("sleep"),
            announce=lambda route: events.append((route.provider, route.endpoint, route.price_usd)),
        )

        self.assertEqual(events[0], (TIKHUB[0], TIKHUB[1], 0.0015))
        self.assertEqual(events[1], "sleep")
        self.assertEqual(
            [call["path"] for call in transport.calls],
            ["discover", "inspect", "run", "runs/run-1"],
        )
        run_body = transport.calls[2]["body"]
        self.assertEqual(run_body["provider"], "tikhub")
        self.assertEqual(run_body["input"]["queryParams"], {
            "keyword": "proposal AI", "search_type": "Latest",
        })
        self.assertEqual(len(result.posts), 1)
        post = result.posts[0]
        self.assertEqual(post["screen_name"], "builder")
        self.assertEqual(post["text"], "Real practitioner complaint")
        self.assertEqual(post["url"], "https://x.com/builder/status/2087425826262598063")
        self.assertEqual(result.usage["run_id"], "run-1")
        self.assertEqual(result.usage["listed_cost"], 0.0015)
        self.assertEqual(result.usage["listed_cost_basis"], "PER_CALL")
        self.assertNotIn("cost", result.usage)

    def test_apify_documented_route_is_supported_when_discovered(self):
        transport = FixtureTransport([
            (200, discovered("apify", APIFY[1], 0.003)),
            (200, inspected("apify", APIFY[1], 0.003)),
            (200, {
                "runId": "run-a", "status": "COMPLETED",
                "providerResponse": {"httpStatus": 200},
                "output": [tweet(screen_name="apifyuser")],
                "resultCount": 1,
                "price": {"type": "PER_CALL", "amount": 0.003, "currency": "USD"},
            }),
        ])
        result = monid_x.search(
            "monid_test_secret", "agent memory", 4,
            request_json=transport, sleep=lambda _: None, announce=lambda _: None,
        )
        self.assertEqual(transport.calls[2]["body"]["input"], {
            "searchTerms": ["agent memory"], "maxItems": 4, "sort": "Latest",
        })
        self.assertEqual(result.route.provider, "apify")
        self.assertEqual(result.posts[0]["screen_name"], "apifyuser")

    def test_unknown_discovered_route_fails_before_inspect_announce_or_run(self):
        transport = FixtureTransport([(200, discovered("unknown", "/twitter/search"))])
        announced = []
        with self.assertRaisesRegex(monid_x.MonidRouteError, "compatible"):
            monid_x.search(
                "monid_test_secret", "q", 3, request_json=transport,
                sleep=lambda _: None, announce=announced.append,
            )
        self.assertEqual([call["path"] for call in transport.calls], ["discover"])
        self.assertEqual(announced, [])

    def test_inspect_mismatch_fails_before_paid_run(self):
        transport = FixtureTransport([
            (200, discovered()),
            (200, inspected(endpoint="/changed")),
        ])
        with self.assertRaisesRegex(monid_x.MonidRouteError, "inspection"):
            monid_x.search(
                "monid_test_secret", "q", 3, request_json=transport,
                sleep=lambda _: None, announce=lambda _: self.fail("must not announce"),
            )
        self.assertEqual([call["path"] for call in transport.calls], ["discover", "inspect"])

    def test_completed_provider_error_is_not_success(self):
        transport = FixtureTransport([
            (200, discovered()), (200, inspected()),
            (200, {
                "runId": "run-bad", "status": "COMPLETED",
                "providerResponse": {"httpStatus": 429, "error": {"message": "limited"}},
                "output": None,
            }),
        ])
        with self.assertRaisesRegex(monid_x.MonidRunError, "429"):
            monid_x.search(
                "monid_test_secret", "q", 3, request_json=transport,
                sleep=lambda _: None, announce=lambda _: None,
            )

    def test_polling_timeout_is_bounded(self):
        transport = FixtureTransport([
            (200, discovered()), (200, inspected()),
            (202, {"runId": "run-slow", "status": "RUNNING"}),
            (200, {"runId": "run-slow", "status": "RUNNING"}),
        ])
        ticks = iter((0.0, 0.0, 2.0, 2.0))
        with self.assertRaisesRegex(monid_x.MonidTimeout, "timed out"):
            monid_x.search(
                "monid_test_secret", "q", 3, request_json=transport,
                sleep=lambda _: None, clock=lambda: next(ticks), max_wait_seconds=1,
                announce=lambda _: None,
            )

    def test_actual_micro_dollar_billing_is_distinct_from_listed_price(self):
        transport = FixtureTransport([
            (200, discovered()), (200, inspected()),
            (200, {
                "runId": "run-cost", "status": "COMPLETED",
                "providerResponse": {"httpStatus": 200},
                "output": {"timeline": []}, "resultCount": 0,
                "billing": {
                    "actualCost": {"value": 1500, "unit": "MICRO_DOLLAR", "currency": "USD"}
                },
            }),
        ])
        result = monid_x.search(
            "monid_test_secret", "q", 3, request_json=transport,
            sleep=lambda _: None, announce=lambda _: None,
        )
        self.assertEqual(result.usage["cost"], 0.0015)
        self.assertEqual(result.usage["cost_status"], "actual")
        self.assertEqual(result.usage["listed_cost"], 0.0015)

    def test_missing_post_fields_remain_unknown_not_invented(self):
        normalized = monid_x.normalize_posts({"timeline": [{"type": "tweet", "tweet_id": "99"}]}, 10)
        self.assertEqual(normalized, [{
            "tweet_id": "99", "screen_name": None, "author_name": None,
            "created_at": None, "text": None,
            "url": "https://x.com/i/web/status/99",
            "favorites": None, "retweets": None, "replies": None,
            "quotes": None, "bookmarks": None, "views": None,
        }])

    def test_zero_max_items_returns_no_posts(self):
        self.assertEqual(
            monid_x.normalize_posts({"timeline": [tweet()]}, 0),
            [],
        )


class RunnerXChannelTests(unittest.TestCase):
    def test_channel_x_renders_posts_and_records_route_usage_and_freshness(self):
        result = monid_x.SearchResult(
            route=monid_x.Route("tikhub", TIKHUB[1], "PER_CALL", 0.0015, "USD", "tikhub-search"),
            run_id="run-1",
            posts=monid_x.normalize_posts({"timeline": [tweet()]}, 10),
            usage={
                "provider": "monid", "route_provider": "tikhub",
                "endpoint": TIKHUB[1], "run_id": "run-1",
                "listed_cost": 0.0015, "cost_status": "quoted",
            },
        )
        usage, freshness = [], []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            deep_research, "_import_sibling", return_value=mock.Mock(
                search=mock.Mock(return_value=result)
            )
        ):
            out = Path(tmp) / "x.md"
            count = deep_research.channel_x(
                "proposal AI", out, 10, usage_sink=usage,
                freshness_sink=freshness,
            )
            rendered = out.read_text(encoding="utf-8")
        self.assertEqual(count, 1)
        self.assertEqual(usage, [result.usage])
        self.assertTrue(freshness)
        self.assertIn("@builder", rendered)
        self.assertIn("Real practitioner complaint", rendered)
        self.assertIn("https://x.com/builder/status/2087425826262598063", rendered)
        self.assertIn("quoted", rendered.lower())


if __name__ == "__main__":
    unittest.main()

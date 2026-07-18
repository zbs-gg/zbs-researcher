"""U15 — Threads connector (R23): posts by keyword through two paths.

Official path — GET graph.threads.net/v1.0/keyword_search with a Threads
access token (threads-access-token.txt / THREADS_ACCESS_TOKEN). Free, quota
2,200 queries/rolling-24h; Standard Access covers only the authenticated
user's OWN posts (Advanced Access via App Review unlocks public search);
results carry NO engagement counts, so the report keeps Meta's TOP order and
says so honestly. The token rides as an `access_token` query param per the
docs, but must NEVER appear in the rendered report or in any raised-error
text — HTTP errors propagate with the token redacted.

Vendor path — ScrapeCreators GET /v1/threads/search (x-api-key header),
pay-per-use (1 credit/request, ~10 posts) WITH engagement counts; output is
ranked through the runner's shared rank_items and carries a cost note.

Path selection: official token present AND DEEP_RESEARCH_THREADS_VENDOR
unset -> official. Token absent OR env forces scrapecreators -> vendor
(clear error if the vendor key is missing). Unknown vendor -> clear error.

All network is mocked — no live calls, no vendor credits spent in tests.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_threads", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import connectors as connectors_pkg
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "ai research tools"
TOKEN = "THAAtestOfficialToken1234567890secret"
SC_KEY = "sc_threads_test_key_9876543210"
VENDOR_ENV = "DEEP_RESEARCH_THREADS_VENDOR"


class FakeHTTP:
    """Stand-in for the runner's get_json. Routes by URL substring and
    records every (url, headers) pair."""

    def __init__(self, routes=(), error=None):
        self.routes = list(routes)
        self.error = error
        self.calls = []

    def __call__(self, url, headers=None, timeout=30):
        self.calls.append((url, dict(headers or {})))
        if self.error is not None:
            if callable(self.error) and not isinstance(self.error, BaseException):
                raise self.error(url)
            raise self.error
        for fragment, payload in self.routes:
            if fragment in url:
                return payload
        return {}


def official_payload():
    return {"data": [
        {"id": "17801", "text": "My honest ai research tools workflow on Threads",
         "media_type": "TEXT", "username": "lab.threads",
         "permalink": "https://www.threads.net/@lab.threads/post/AAA111",
         "timestamp": "2026-07-10T08:15:30+0000",
         "has_replies": True, "is_quote_post": False, "is_reply": False},
        {"id": "17802", "text": "quoting the big ai research tools debate",
         "media_type": "TEXT", "username": "meta.watcher",
         "permalink": "https://www.threads.net/@meta.watcher/post/BBB222",
         "timestamp": "2026-07-09T20:01:02+0000",
         "has_replies": False, "is_quote_post": True, "is_reply": True},
    ]}


def vendor_payload():
    return {"posts": [
        {"id": "T2", "text": "cute cat pictures compilation",
         "username": "cats.daily", "like_count": 999999,
         "direct_reply_count": 10, "repost_count": 2, "quote_count": 0,
         "reshare_count": 1,
         "permalink": "https://www.threads.net/@cats.daily/post/T2"},
        {"id": "T1", "text": "ai research tools thread — the full list I use",
         "username": "research.gal", "like_count": 320,
         "direct_reply_count": 45, "repost_count": 12, "quote_count": 3,
         "reshare_count": 5,
         "permalink": "https://www.threads.net/@research.gal/post/T1"},
    ]}


def official_routes():
    return [("graph.threads.net/v1.0/keyword_search", official_payload())]


def vendor_routes():
    return [("api.scrapecreators.com/v1/threads/search", vendor_payload())]


def http_429(url):
    """A throttle error as urllib would raise it: URL (token included) in
    filename, and a body that echoes the request URL back."""
    body = json.dumps({"error": {"message": "throttled", "url": url}})
    return urllib.error.HTTPError(
        url, 429, "Too Many Requests", None, io.BytesIO(body.encode("utf-8"))
    )


class ThreadsCase(unittest.TestCase):
    def setUp(self):
        connectors_pkg.attach_runner(deep_research.__dict__)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(VENDOR_ENV, None)

    def run_channel(self, fake, threads_key="", sc_key="", topic=TOPIC,
                    max_items=10):
        keys = dict(deep_research.KEYS)
        keys["threads"] = threads_key
        keys["scrapecreators"] = sc_key
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "threads.md"
            with contextlib.ExitStack() as stack:
                stack.enter_context(
                    mock.patch.object(deep_research, "get_json", fake))
                stack.enter_context(
                    mock.patch.object(deep_research, "KEYS", keys))
                n = deep_research.channel_threads(topic, out, max_items)
            return n, out.read_text(encoding="utf-8")


class OfficialPathTests(ThreadsCase):
    def test_request_shape_and_token_never_rendered(self):
        fake = FakeHTTP(routes=official_routes())
        n, text = self.run_channel(fake, threads_key=TOKEN)
        self.assertEqual(n, 2)
        self.assertEqual(len(fake.calls), 1)
        url, _headers = fake.calls[0]
        self.assertIn("graph.threads.net/v1.0/keyword_search", url)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(params["q"], [TOPIC])
        self.assertEqual(params["search_type"], ["TOP"])
        self.assertEqual(params["limit"], ["30"])  # min(100, max(25, 10*3))
        self.assertEqual(params["access_token"], [TOKEN])
        for field in ("id", "text", "media_type", "permalink", "timestamp",
                      "username", "has_replies", "is_quote_post", "is_reply"):
            self.assertIn(field, params["fields"][0])
        # the token must never leak into the rendered report
        self.assertNotIn(TOKEN, text)
        # posts render with handle, excerpt, date, flags, permalink
        self.assertIn("@lab.threads", text)
        self.assertIn("My honest ai research tools workflow", text)
        self.assertIn("2026-07-10", text)
        self.assertIn("has replies", text)
        self.assertIn("quote", text)
        self.assertIn("reply", text)
        self.assertIn("https://www.threads.net/@lab.threads/post/AAA111", text)

    def test_no_engagement_note_and_meta_order_kept(self):
        fake = FakeHTTP(routes=official_routes())
        _n, text = self.run_channel(fake, threads_key=TOKEN)
        self.assertIn("no engagement counts", text)
        self.assertIn("TOP relevance", text)
        # Meta's order is kept verbatim — no fake engagement ranking
        self.assertLess(text.index("lab.threads"), text.index("meta.watcher"))

    def test_empty_result_with_valid_token_gets_advanced_access_hint(self):
        fake = FakeHTTP(routes=[
            ("graph.threads.net/v1.0/keyword_search", {"data": []}),
        ])
        n, text = self.run_channel(fake, threads_key=TOKEN)
        self.assertEqual(n, 0)
        self.assertIn("Standard Access", text)
        self.assertIn("own posts", text)
        self.assertIn("Advanced Access", text)
        self.assertIn("App Review", text)
        self.assertIn("sensitive", text)
        self.assertNotIn(TOKEN, text)

    def test_http_429_propagates_with_token_redacted(self):
        fake = FakeHTTP(error=http_429)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.run_channel(fake, threads_key=TOKEN)
        exc = ctx.exception
        self.assertEqual(exc.code, 429)
        raised_text = "\n".join((
            str(exc),
            str(getattr(exc, "filename", "") or ""),
            str(getattr(exc, "reason", "") or ""),
            exc.read().decode("utf-8", "replace"),
        ))
        self.assertNotIn(TOKEN, raised_text)


class VendorPathTests(ThreadsCase):
    def test_vendor_path_when_official_token_absent(self):
        fake = FakeHTTP(routes=vendor_routes())
        n, text = self.run_channel(fake, sc_key=SC_KEY)
        self.assertEqual(n, 2)
        self.assertEqual(len(fake.calls), 1)
        url, headers = fake.calls[0]
        self.assertIn("api.scrapecreators.com/v1/threads/search", url)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(params["query"], [TOPIC])
        self.assertEqual(headers.get("x-api-key"), SC_KEY)
        self.assertNotIn(SC_KEY, url)  # key in the header, never the URL
        # engagement counts shown
        self.assertIn("likes 320", text)
        self.assertIn("replies 45", text)
        self.assertIn("reposts 12", text)
        # engagement-ranked with relevance floor: the on-topic post outranks
        # the off-topic viral one
        self.assertLess(text.index("research.gal"), text.index("cats.daily"))
        # honest cost note
        self.assertIn("pay-per-use vendor", text)
        self.assertIn("1 credit/request", text)
        self.assertIn("~10 posts", text)

    def test_both_keys_present_prefers_official(self):
        fake = FakeHTTP(routes=official_routes() + vendor_routes())
        _n, text = self.run_channel(fake, threads_key=TOKEN, sc_key=SC_KEY)
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("graph.threads.net", fake.calls[0][0])
        self.assertIn("no engagement counts", text)

    def test_env_override_forces_vendor_over_official_token(self):
        os.environ[VENDOR_ENV] = "scrapecreators"
        fake = FakeHTTP(routes=official_routes() + vendor_routes())
        _n, text = self.run_channel(fake, threads_key=TOKEN, sc_key=SC_KEY)
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("api.scrapecreators.com", fake.calls[0][0])
        self.assertIn("pay-per-use vendor", text)

    def test_forced_vendor_without_key_clear_error(self):
        os.environ[VENDOR_ENV] = "scrapecreators"
        fake = FakeHTTP()
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(fake, threads_key=TOKEN)
        message = str(ctx.exception)
        self.assertIn(VENDOR_ENV, message)
        self.assertIn("scrapecreators", message.lower())
        self.assertEqual(fake.calls, [])  # refused before any network call

    def test_unknown_vendor_value_clear_error(self):
        os.environ[VENDOR_ENV] = "wat"
        fake = FakeHTTP()
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(fake, threads_key=TOKEN, sc_key=SC_KEY)
        message = str(ctx.exception)
        self.assertIn("wat", message)
        self.assertIn("scrapecreators", message)
        self.assertEqual(fake.calls, [])


class GatingTests(ThreadsCase):
    def test_neither_key_unavailable_and_direct_call_errors(self):
        keys = dict(deep_research.KEYS)
        keys["threads"] = ""
        keys["scrapecreators"] = ""
        with mock.patch.object(deep_research, "KEYS", keys):
            conn = deep_research.CONNECTORS["threads"]
            self.assertFalse(conn.available())
            self.assertEqual(conn.missing_keys(), ["threads"])
            live, skipped = deep_research.select_connectors("threads", None)
            self.assertEqual([c.name for c in live], [])
            self.assertIn("threads", [c.name for c in skipped])
            # a direct call without any key still fails honestly
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "threads.md"
                with self.assertRaises(RuntimeError) as ctx:
                    deep_research.channel_threads(TOPIC, out, 5)
        message = str(ctx.exception)
        self.assertIn("THREADS_ACCESS_TOKEN", message)
        self.assertIn("scrapecreators", message.lower())

    def test_scrapecreators_key_alone_makes_connector_available(self):
        keys = dict(deep_research.KEYS)
        keys["threads"] = ""
        keys["scrapecreators"] = SC_KEY
        with mock.patch.object(deep_research, "KEYS", keys):
            conn = deep_research.CONNECTORS["threads"]
            self.assertTrue(conn.available())
            self.assertEqual(conn.missing_keys(), [])
            live, _skipped = deep_research.select_connectors("threads", None)
            self.assertEqual([c.name for c in live], ["threads"])


class RegistryTests(unittest.TestCase):
    def test_connector_registered_with_fallback_key(self):
        conn = deep_research.CONNECTORS["threads"]
        self.assertEqual(conn.kind, "direct")
        self.assertEqual(conn.requires, ["threads"])
        self.assertEqual(conn.fallback_key, "scrapecreators")

    def test_output_name(self):
        self.assertEqual(deep_research.OUTPUT_NAMES["threads"], "threads.md")

    def test_keys_registry_carries_threads_slot(self):
        self.assertIn("threads", deep_research.KEYS)


class WindowsSafetyTests(unittest.TestCase):
    def test_connector_source_avoids_posix_only_calls(self):
        source = (SCRIPTS / "connectors" / "threads.py").read_text(
            encoding="utf-8"
        )
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                      "pwd.", "grp.", "os.chmod"):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

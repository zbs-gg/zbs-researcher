"""U7 — TikTok / Instagram connector (R10): short-video user voice through a
pay-per-use vendor. OPT-IN twice: default=False in the registry AND key-gated
(requires=["scrapecreators"]).

channel_tiktok_ig (connectors/tiktok_ig.py) pulls posts + comments +
engagement for a topic through a selectable vendor adapter
(DEEP_RESEARCH_TIKTOK_VENDOR = scrapecreators (default) | apify), ranks them
with the runner's shared rank_items, optionally transcribes the top videos
through media_backend (failure degrades to a metadata-only note), and always
renders an honest cost line ("pay-per-use vendor — each run costs vendor
credits"). Vendor 402/429 raises a cost-hinting error that propagates so
run_connector writes ERROR.md.

All network is mocked — no live calls, no vendor credits spent in tests.
"""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_tiktok_ig", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import connectors as connectors_pkg
    from connectors import tiktok_ig as tiktok_ig_mod
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "ai research tools"
KEY = "sc_test_key_1234567890abc"
COST_NOTE = "pay-per-use vendor — each run costs vendor credits"


def http_error(code, reason="Payment Required"):
    return urllib.error.HTTPError(
        "https://api.scrapecreators.com/v1/tiktok/search/keyword",
        code, reason, None, io.BytesIO(b'{"error":"quota"}'),
    )


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
            raise self.error
        for fragment, payload in self.routes:
            if fragment in url:
                return payload
        return {}


def tiktok_search_payload():
    return {"search_item_list": [
        {"aweme_info": {
            "aweme_id": "731",
            "desc": "Top ai research tools I actually use daily",
            "statistics": {"digg_count": 5400, "comment_count": 210,
                           "play_count": 88000},
            "share_url": "https://www.tiktok.com/@labgirl/video/731",
            "author": {"unique_id": "labgirl"},
        }},
        {"aweme_info": {
            "aweme_id": "732",
            "desc": "unrelated dance clip",
            "statistics": {"digg_count": 900000, "comment_count": 12,
                           "play_count": 5000000},
            "share_url": "https://www.tiktok.com/@dancer/video/732",
            "author": {"unique_id": "dancer"},
        }},
    ]}


def instagram_search_payload():
    return {"posts": [
        {"id": "IG9", "caption": "ai research tools for reels workflows",
         "like_count": 340, "comment_count": 25,
         "permalink": "https://www.instagram.com/p/IG9/",
         "owner": {"username": "research.reels"}},
    ]}


def tiktok_comments_payload():
    return {"comments": [
        {"text": "which one reads PDFs?", "digg_count": 12,
         "user": {"unique_id": "curious_dev"}},
        {"text": "saved, thanks", "digg_count": 2, "user": {"nickname": "ana"}},
    ]}


def default_routes():
    return [
        ("/v1/tiktok/search/keyword", tiktok_search_payload()),
        ("/v1/instagram/search", instagram_search_payload()),
        ("/v1/tiktok/video/comments", tiktok_comments_payload()),
        ("/v2/instagram/media/comments", {"comments": [
            {"text": "love this ai research tools list", "like_count": 4,
             "owner": {"username": "igfan"}},
        ]}),
    ]


class TikTokIGCase(unittest.TestCase):
    def setUp(self):
        connectors_pkg.attach_runner(deep_research.__dict__)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("DEEP_RESEARCH_TIKTOK_VENDOR", None)
        os.environ.pop("APIFY_TOKEN", None)

    def run_channel(self, fake, key=KEY, topic=TOPIC, max_items=10,
                    post_json=None):
        keys = dict(deep_research.KEYS)
        keys["scrapecreators"] = key
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tiktok-ig.md"
            with contextlib.ExitStack() as stack:
                stack.enter_context(
                    mock.patch.object(deep_research, "get_json", fake))
                stack.enter_context(
                    mock.patch.object(deep_research, "KEYS", keys))
                if post_json is not None:
                    stack.enter_context(
                        mock.patch.object(deep_research, "post_json", post_json))
                n = deep_research.channel_tiktok_ig(topic, out, max_items)
            return n, out.read_text(encoding="utf-8")


class HappyPathTests(TikTokIGCase):
    def test_posts_comments_engagement_and_cost_note(self):
        fake = FakeHTTP(routes=default_routes())
        n, text = self.run_channel(fake)
        self.assertEqual(n, 3)
        self.assertIn(COST_NOTE, text)
        self.assertIn("@labgirl", text)
        self.assertIn("(tiktok)", text)
        self.assertIn("@research.reels", text)
        self.assertIn("(instagram)", text)
        self.assertIn("likes 5,400", text)
        self.assertIn("comments 210", text)
        self.assertIn("plays 88,000", text)
        self.assertIn("which one reads PDFs?", text)
        self.assertIn("(likes 12)", text)
        self.assertIn("https://www.tiktok.com/@labgirl/video/731", text)
        # relevance floor: on-topic post outranks the off-topic viral one
        self.assertLess(text.index("labgirl"), text.index("dancer"))
        # every ScrapeCreators call carried the x-api-key header
        self.assertTrue(fake.calls)
        for _url, headers in fake.calls:
            self.assertEqual(headers.get("x-api-key"), KEY)


class GatingTests(TikTokIGCase):
    def test_missing_key_gates_connector_and_direct_call_errors(self):
        keys = dict(deep_research.KEYS)
        keys["scrapecreators"] = ""
        with mock.patch.object(deep_research, "KEYS", keys):
            conn = deep_research.CONNECTORS["tiktok-ig"]
            self.assertFalse(conn.available())
            self.assertEqual(conn.missing_keys(), ["scrapecreators"])
            # default=False: not in the default set at all (not even skipped)
            live, skipped = deep_research.select_connectors(None, None)
            names = [c.name for c in live] + [c.name for c in skipped]
            self.assertNotIn("tiktok-ig", names)
            # opt-in without a key lands in skipped (requires gating)
            live, skipped = deep_research.select_connectors("tiktok-ig", None)
            self.assertEqual([c.name for c in live], [])
            self.assertIn("tiktok-ig", [c.name for c in skipped])
            # a direct call without a key still fails honestly
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "tiktok-ig.md"
                with self.assertRaises(RuntimeError) as ctx:
                    deep_research.channel_tiktok_ig(TOPIC, out, 5)
        message = str(ctx.exception).lower()
        self.assertIn("scrapecreators", message)
        self.assertIn("credits", message)

    def test_unknown_vendor_env_clear_error(self):
        os.environ["DEEP_RESEARCH_TIKTOK_VENDOR"] = "wat"
        fake = FakeHTTP()
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(fake)
        message = str(ctx.exception)
        self.assertIn("wat", message)
        self.assertIn("scrapecreators", message)
        self.assertIn("apify", message)
        self.assertEqual(fake.calls, [])  # refused before any vendor call

    def test_quota_402_raises_cost_hint_and_propagates(self):
        fake = FakeHTTP(error=http_error(402))
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(fake)
        message = str(ctx.exception)
        self.assertIn("402", message)
        self.assertIn("credit", message.lower())
        self.assertIsInstance(ctx.exception.__cause__, urllib.error.HTTPError)


class ApifyVendorTests(TikTokIGCase):
    def test_apify_vendor_without_token_clear_error(self):
        os.environ["DEEP_RESEARCH_TIKTOK_VENDOR"] = "apify"
        fake = FakeHTTP()
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(fake)
        self.assertIn("APIFY_TOKEN", str(ctx.exception))
        self.assertEqual(fake.calls, [])

    def test_apify_vendor_mocked_run_renders_posts(self):
        os.environ["DEEP_RESEARCH_TIKTOK_VENDOR"] = "apify"
        os.environ["APIFY_TOKEN"] = "apify_test_token"
        seen = {}

        def fake_post(url, body, headers, timeout=300):
            seen["url"] = url
            seen["body"] = body
            seen["headers"] = headers
            return [{"id": "9", "text": "ai research tools on tiktok",
                     "diggCount": 41, "commentCount": 3, "playCount": 900,
                     "webVideoUrl": "https://www.tiktok.com/@apify/video/9",
                     "authorMeta": {"name": "apify_author"}}]

        n, text = self.run_channel(FakeHTTP(), post_json=fake_post)
        self.assertEqual(n, 1)
        self.assertIn("run-sync-get-dataset-items", seen["url"])
        self.assertEqual(seen["headers"].get("Authorization"),
                         "Bearer apify_test_token")
        self.assertNotIn("apify_test_token", seen["url"])  # token never in URL
        self.assertIn("vendor: apify", text)
        self.assertIn("@apify_author", text)
        self.assertIn("likes 41", text)
        self.assertIn(COST_NOTE, text)


class TranscriptTests(TikTokIGCase):
    def routes_with_media(self):
        payload = tiktok_search_payload()
        payload["search_item_list"][0]["aweme_info"]["video"] = {
            "download_addr": {"url_list": ["https://cdn.example/731.mp4"]}
        }
        return [
            ("/v1/tiktok/search/keyword", payload),
            ("/v1/instagram/search", {"posts": []}),
            ("/v1/tiktok/video/comments", {"comments": []}),
        ]

    def test_transcript_failure_degrades_to_metadata_note(self):
        class Boom:
            def transcribe(self, blob, mime="audio/mp4"):
                raise RuntimeError("Groq key missing")

        fake = FakeHTTP(routes=self.routes_with_media())
        with mock.patch.object(tiktok_ig_mod, "_fetch_media_bytes",
                               lambda url: b"12345"), \
                mock.patch.object(tiktok_ig_mod, "_media_backend",
                                  lambda: Boom()):
            n, text = self.run_channel(fake)
        self.assertGreaterEqual(n, 1)
        self.assertIn("transcript unavailable", text)
        self.assertIn("metadata only", text)
        self.assertNotIn("Traceback", text)

    def test_transcript_success_included(self):
        class Fine:
            def transcribe(self, blob, mime="audio/mp4"):
                return "we compare five research agents on real papers"

        fake = FakeHTTP(routes=self.routes_with_media())
        with mock.patch.object(tiktok_ig_mod, "_fetch_media_bytes",
                               lambda url: b"12345"), \
                mock.patch.object(tiktok_ig_mod, "_media_backend",
                                  lambda: Fine()):
            _n, text = self.run_channel(fake)
        self.assertIn("transcript:", text)
        self.assertIn("five research agents", text)


class RegistryTests(unittest.TestCase):
    def test_connector_registered_opt_in_and_key_gated(self):
        conn = deep_research.CONNECTORS["tiktok-ig"]
        self.assertEqual(conn.kind, "direct")
        self.assertFalse(conn.default)
        self.assertEqual(conn.requires, ["scrapecreators"])
        self.assertIsNone(conn.fallback_key)

    def test_output_name(self):
        self.assertEqual(deep_research.OUTPUT_NAMES["tiktok-ig"], "tiktok-ig.md")


class WindowsSafetyTests(unittest.TestCase):
    def test_connector_source_avoids_posix_only_calls(self):
        source = (SCRIPTS / "connectors" / "tiktok_ig.py").read_text(
            encoding="utf-8"
        )
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                      "pwd.", "grp.", "os.chmod"):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

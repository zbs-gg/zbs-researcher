"""U8 — Meta Ad Library connector (R6): money signal, free with a token.

channel_meta_ads (connectors/meta_ads.py) queries the Meta Ad Library API
(graph.facebook.com ads_archive) with EU reach countries — full commercial ad
detail is EU-only under the DSA; US coverage would be political/issue ads
only — and aggregates the matched ads BY ADVERTISER (page_name): ads matched,
still-delivering count, summed EU reach, longest delivery run and
running-since date, one sample snapshot url. Sustained-spend proxy = longest
delivery duration combined with total reach (Meta publishes reach, never
spend — the report says so and invents nothing).

The connector is token-gated: `requires=["meta_ads"]` means select_connectors
auto-skips it when the token is absent and records the missing key in the
manifest — that IS the honest degrade (no silent gap, no fake data).

All network is mocked — no live calls in tests. Helpers (get_json / KEYS)
resolve through the runner's live module globals, so patching them on the
loaded deep-research module is honored inside the connector.
"""
import calendar
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time as time_mod
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
    SPEC = importlib.util.spec_from_file_location("deep_research_meta_ads", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import connectors as connectors_pkg
    from connectors import meta_ads
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "AI research tools"
TOKEN = "EAATestToken1234567890abcd"
# Fixed "now" so fixture ages are deterministic: 2026-07-17 00:00:00 UTC.
FIXED_NOW = calendar.timegm((2026, 7, 17, 0, 0, 0, 0, 0, 0))
DAY = 86400


def day(days_ago):
    return time_mod.strftime("%Y-%m-%d", time_mod.gmtime(FIXED_NOW - days_ago * DAY))


def ad(page, reach, start_days_ago, stop_days_ago=None, snapshot=None,
       platforms=("facebook", "instagram")):
    item = {
        "page_name": page,
        "ad_delivery_start_time": day(start_days_ago),
        "eu_total_reach": reach,
        "ad_snapshot_url": snapshot
        or f"https://www.facebook.com/ads/library/?id={abs(hash(page)) % 10**8}",
        "publisher_platforms": list(platforms),
    }
    if stop_days_ago is not None:
        item["ad_delivery_stop_time"] = day(stop_days_ago)
    return item


def oauth_400():
    body = json.dumps({
        "error": {
            "type": "OAuthException",
            "message": "Invalid OAuth access token.",
            "code": 190,
        }
    }).encode()
    return urllib.error.HTTPError(
        "https://graph.facebook.com/v21.0/ads_archive", 400, "Bad Request",
        None, io.BytesIO(body),
    )


def rate_limit_429():
    body = json.dumps({
        "error": {"message": "Application request limit reached", "code": 4}
    }).encode()
    return urllib.error.HTTPError(
        "https://graph.facebook.com/v21.0/ads_archive", 429, "Too Many Requests",
        None, io.BytesIO(body),
    )


class FakeGetJson:
    """Stand-in for the runner's get_json. Records URLs."""

    def __init__(self, result=None, error=None):
        self.result = result if result is not None else {"data": []}
        self.error = error
        self.urls = []

    def __call__(self, url, headers=None, timeout=30):
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return self.result


class MetaAdsCase(unittest.TestCase):
    """Base: wire THIS module's deep-research copy into the connectors
    package (last-attached wins across test files) and freeze time."""

    def setUp(self):
        connectors_pkg.attach_runner(deep_research.__dict__)
        patcher = mock.patch.object(meta_ads, "_now", lambda: FIXED_NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_channel(self, get_json, token=TOKEN, topic=TOPIC, max_items=10):
        keys = dict(deep_research.KEYS)
        keys["meta_ads"] = token
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "meta-ads.md"
            with mock.patch.object(deep_research, "get_json", get_json), \
                    mock.patch.object(deep_research, "KEYS", keys):
                n = deep_research.channel_meta_ads(topic, out, max_items)
            return n, out.read_text(encoding="utf-8")


class AggregationTests(MetaAdsCase):
    def test_ads_aggregate_by_advertiser_with_reach_and_counts(self):
        fake = FakeGetJson({"data": [
            ad("AcmeAI", 1000, start_days_ago=40),                      # active
            ad("AcmeAI", 2000, start_days_ago=25, stop_days_ago=5),    # stopped
            ad("SmallCo", 50, start_days_ago=5, stop_days_ago=1),
        ]})
        n, text = self.run_channel(fake)

        self.assertEqual(n, 2)  # two advertisers, not three ads
        # aggregated advertiser line: ad count + summed EU reach
        self.assertIn("AcmeAI", text)
        self.assertIn("2 ads matched", text)
        self.assertIn("3,000", text)
        self.assertIn("1 still delivering", text)
        # sustained-spend proxy inputs rendered: longest run + running-since
        self.assertIn("running since " + day(40), text)
        self.assertIn("40d", text)
        # sample snapshot url for manual verification
        self.assertIn("facebook.com/ads/library", text)
        # bigger sustained spend (reach + duration) ranks first
        self.assertLess(text.index("AcmeAI"), text.index("SmallCo"))

    def test_eu_scope_line_is_honest(self):
        fake = FakeGetJson({"data": [ad("AcmeAI", 10, start_days_ago=3)]})
        _, text = self.run_channel(fake)
        self.assertIn("EU", text)
        self.assertIn("DE", text)
        # honest note that US coverage would be political/issue ads only
        self.assertIn("political", text)
        # never pretend reach is revenue
        self.assertIn("reach", text.lower())
        self.assertNotIn("ARR", text)

    def test_request_shape_matches_ad_library_contract(self):
        fake = FakeGetJson({"data": []})
        _, text = self.run_channel(fake, max_items=10)
        self.assertEqual(len(fake.urls), 1)
        url = fake.urls[0]
        self.assertTrue(
            url.startswith("https://graph.facebook.com/v21.0/ads_archive?"), url
        )
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(params["search_terms"], [TOPIC])
        self.assertEqual(params["ad_type"], ["ALL"])
        self.assertEqual(params["access_token"], [TOKEN])
        for country in ("DE", "FR", "NL", "ES", "IT", "PL"):
            self.assertIn(country, params["ad_reached_countries"][0])
        for field in (
            "page_name", "ad_delivery_start_time", "ad_delivery_stop_time",
            "eu_total_reach", "ad_snapshot_url", "publisher_platforms",
        ):
            self.assertIn(field, params["fields"][0])
        # honest empty result
        self.assertIn("No ads matched", text)


class DegradeTests(MetaAdsCase):
    def test_missing_token_makes_connector_unavailable_and_skipped(self):
        keys = dict(deep_research.KEYS)
        keys["meta_ads"] = ""
        with mock.patch.object(deep_research, "KEYS", keys):
            conn = deep_research.CONNECTORS["meta-ads"]
            self.assertFalse(conn.available())
            self.assertEqual(conn.missing_keys(), ["meta_ads"])
            live, skipped = deep_research.select_connectors(None, None)
        self.assertIn("meta-ads", [c.name for c in skipped])
        self.assertNotIn("meta-ads", [c.name for c in live])

    def test_missing_token_skip_is_recorded_in_manifest(self):
        keys = dict(deep_research.KEYS)
        keys["meta_ads"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            argv = [str(RUNNER), TOPIC, "--only", "meta-ads",
                    "--output-dir", str(out_dir)]
            stderr = io.StringIO()
            with mock.patch.object(deep_research, "KEYS", keys), \
                    mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stderr(stderr):
                deep_research.main()
            manifest = json.loads(
                (out_dir / "manifest.json").read_text(encoding="utf-8")
            )
        self.assertEqual(manifest["connectors_run"], [])
        self.assertEqual(
            manifest["connectors_skipped"]["meta-ads"],
            "missing keys: ['meta_ads']",
        )

    def test_oauth_400_raises_clear_token_guidance(self):
        fake = FakeGetJson(error=oauth_400())
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(fake)
        message = str(ctx.exception)
        self.assertIn("token", message.lower())
        self.assertIn("App Review", message)
        self.assertNotIn(TOKEN, message)  # never echo the secret

    def test_rate_limit_propagates_as_http_error(self):
        fake = FakeGetJson(error=rate_limit_429())
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.run_channel(fake)
        self.assertEqual(ctx.exception.code, 429)


class RegistryTests(unittest.TestCase):
    def test_connector_registered_token_gated_direct_default(self):
        conn = deep_research.CONNECTORS["meta-ads"]
        self.assertEqual(conn.kind, "direct")
        self.assertEqual(conn.requires, ["meta_ads"])
        self.assertTrue(conn.default)
        self.assertIsNone(conn.fallback_key)

    def test_output_name_present(self):
        self.assertEqual(deep_research.OUTPUT_NAMES["meta-ads"], "meta-ads.md")

    def test_keys_dict_carries_meta_ads_entry(self):
        self.assertIn("meta_ads", deep_research.KEYS)

    def test_fresh_load_resolves_token_from_env_and_file(self):
        def fresh_keys(secrets_dir):
            spec = importlib.util.spec_from_file_location(
                "deep_research_meta_ads_fresh", RUNNER
            )
            module = importlib.util.module_from_spec(spec)
            added = scripts_path not in sys.path
            if added:
                sys.path.insert(0, scripts_path)
            try:
                spec.loader.exec_module(module)
            finally:
                if added:
                    sys.path.remove(scripts_path)
            return module.KEYS

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ):
                os.environ.pop("META_ADS_TOKEN", None)
                os.environ["DEEP_RESEARCH_SECRETS_DIR"] = tmp
                self.assertFalse(fresh_keys(tmp)["meta_ads"])

                os.environ["META_ADS_TOKEN"] = TOKEN
                self.assertEqual(fresh_keys(tmp)["meta_ads"], TOKEN)

                os.environ.pop("META_ADS_TOKEN", None)
                file_token = "12345|" + "a" * 24
                (Path(tmp) / "meta-ads-token.txt").write_text(
                    file_token + "\n", encoding="utf-8"
                )
                self.assertEqual(fresh_keys(tmp)["meta_ads"], file_token)
        # re-attach THIS module's runner copy (fresh loads re-bound it)
        connectors_pkg.attach_runner(deep_research.__dict__)


class WindowsSafetyTests(unittest.TestCase):
    def test_connector_source_avoids_posix_only_calls(self):
        source = (SCRIPTS / "connectors" / "meta_ads.py").read_text(encoding="utf-8")
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                      "pwd.", "grp."):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

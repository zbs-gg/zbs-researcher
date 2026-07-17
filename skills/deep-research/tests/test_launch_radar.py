"""U12 — Launch-radar connector (R22/KTD7): what's shipping around a topic.

channel_launch_radar (connectors/launch_radar.py) aggregates free launch
surfaces — Show HN (HN Algolia `show_hn` tag), yc-oss batch files, DevHunt
(GitHub PR listings on MarsX-dev/devhunt) — plus Product Hunt GraphQL when a
free read token is configured. Sub-sources are isolated: one failing writes a
note, siblings continue. Items are dropped below the shared rank_items
relevance floor, then ordered by launch momentum = bounded engagement ×
recency decay (half-life ~30 days) × comment factor. yc-oss entries carry NO
vote fields (verified live 2026-07-18) so their momentum is recency-only and
the report says so. A category-velocity header counts matched launches in the
90-day window per sub-source (saturation signal).

All network is mocked — no live calls in tests. The connector resolves the
runner's helpers (get_json / post_json / gh_api / read_key / ranking) through
live module globals, so patching them on the loaded deep-research module is
honored inside the connector.
"""
import calendar
import importlib.util
import re
import sys
import tempfile
import unittest
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
    SPEC = importlib.util.spec_from_file_location("deep_research_launch_radar", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import connectors as connectors_pkg
    from connectors import launch_radar
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "AI research tools"
# Fixed "now" so fixture ages are deterministic: 2026-07-17 00:00:00 UTC.
FIXED_NOW = calendar.timegm((2026, 7, 17, 0, 0, 0, 0, 0, 0))
DAY = 86400


def iso(days_ago):
    ts = FIXED_NOW - days_ago * DAY
    import time as _t
    return _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(ts))


def hn_hit(title, points, comments, days_ago, object_id="111"):
    return {
        "title": title,
        "points": points,
        "num_comments": comments,
        "created_at": iso(days_ago),
        "created_at_i": FIXED_NOW - days_ago * DAY,
        "objectID": object_id,
        "url": f"https://example.com/{object_id}",
    }


def yc_company(name, one_liner, days_ago, batch="Summer 2026", slug="co"):
    return {
        "name": name,
        "one_liner": one_liner,
        "launched_at": FIXED_NOW - days_ago * DAY,
        "batch": batch,
        "url": f"https://www.ycombinator.com/companies/{slug}",
        "website": f"https://{slug}.example.com",
    }


YC_META = {
    "batches": {
        "summer-2026": {
            "name": "Summer 2026",
            "count": 2,
            "api": "https://yc-oss.github.io/api/batches/summer-2026.json",
        },
        "spring-2026": {
            "name": "Spring 2026",
            "count": 1,
            "api": "https://yc-oss.github.io/api/batches/spring-2026.json",
        },
        "empty-batch": {
            "name": "Winter 2027",
            "count": 0,
            "api": "https://yc-oss.github.io/api/batches/winter-2027.json",
        },
    }
}


def devhunt_pr(title, days_ago, reactions=0, comments=0, number=7):
    return {
        "title": title,
        "created_at": iso(days_ago),
        "html_url": f"https://github.com/MarsX-dev/devhunt/pull/{number}",
        "comments": comments,
        "reactions": {"total_count": reactions},
    }


def ph_response(nodes):
    return {
        "data": {
            "posts": {
                "edges": [{"node": n} for n in nodes],
            }
        }
    }


def ph_node(name, tagline, votes, comments, days_ago, slug="tool"):
    return {
        "name": name,
        "tagline": tagline,
        "votesCount": votes,
        "commentsCount": comments,
        "createdAt": iso(days_ago),
        "url": f"https://www.producthunt.com/posts/{slug}",
        "user": {"username": "maker1", "name": "Maker One"},
    }


class FakeGetJson:
    """URL-routing stand-in for the runner's get_json. Records URLs."""

    def __init__(self, show_hn=None, yc_meta=None, yc_batches=None,
                 errors=None):
        self.show_hn = show_hn if show_hn is not None else {"hits": []}
        self.yc_meta = yc_meta if yc_meta is not None else {"batches": {}}
        self.yc_batches = yc_batches or {}  # slug -> [company, ...]
        self.errors = errors or {}          # substring -> exception
        self.urls = []

    def __call__(self, url, headers=None, timeout=30):
        self.urls.append(url)
        for needle, exc in self.errors.items():
            if needle in url:
                raise exc
        if "hn.algolia.com" in url:
            return self.show_hn
        if "yc-oss.github.io/api/meta.json" in url:
            return self.yc_meta
        m = re.search(r"/api/batches/([\w-]+)\.json", url)
        if m:
            return self.yc_batches.get(m.group(1), [])
        raise AssertionError(f"unexpected get_json url: {url}")


class FakeGhApi:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else {"items": []}
        self.error = error
        self.paths = []

    def __call__(self, path):
        self.paths.append(path)
        if self.error is not None:
            raise self.error
        return self.result


class FakePostJson:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else ph_response([])
        self.error = error
        self.calls = []  # (url, body, headers)

    def __call__(self, url, body, headers, timeout=300):
        self.calls.append((url, body, headers))
        if self.error is not None:
            raise self.error
        return self.result


class LaunchRadarCase(unittest.TestCase):
    """Base: wire THIS module's deep-research copy into the connectors
    package (last-attached wins across test files) and freeze time."""

    def setUp(self):
        connectors_pkg.attach_runner(deep_research.__dict__)
        patcher = mock.patch.object(launch_radar, "_now", lambda: FIXED_NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_channel(self, get_json, gh_api=None, post_json=None,
                    token="", topic=TOPIC, max_items=10):
        gh_api = gh_api if gh_api is not None else FakeGhApi()
        post_json = post_json if post_json is not None else FakePostJson()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "launch-radar.md"
            with mock.patch.object(deep_research, "get_json", get_json), \
                    mock.patch.object(deep_research, "gh_api", gh_api), \
                    mock.patch.object(deep_research, "post_json", post_json), \
                    mock.patch.object(deep_research, "read_key",
                                      lambda *a, **k: token):
                n = deep_research.channel_launch_radar(topic, out, max_items)
            return n, out.read_text(encoding="utf-8")


class AggregationTests(LaunchRadarCase):
    def test_topic_yields_launches_with_momentum_and_velocity(self):
        fake = FakeGetJson(
            show_hn={"hits": [
                hn_hit("Show HN: Parallax – AI research tools for biotech",
                       120, 45, days_ago=10, object_id="101"),
            ]},
            yc_meta=YC_META,
            yc_batches={
                "summer-2026": [yc_company(
                    "Scholarly", "AI research tools for scientists",
                    days_ago=20, slug="scholarly")],
                "spring-2026": [],
            },
        )
        ph = FakePostJson(ph_response([
            ph_node("ResearchPilot", "AI research tools copilot",
                    votes=300, comments=40, days_ago=5),
        ]))
        n, text = self.run_channel(fake, post_json=ph, token="x" * 24)

        self.assertGreaterEqual(n, 3)
        # every launch line carries a source tag + momentum score
        self.assertIn("[ShowHN]", text)
        self.assertIn("[YC]", text)
        self.assertIn("[PH]", text)
        self.assertIn("momentum", text)
        # votes/comments/date/url rendered where known
        self.assertIn("120", text)
        self.assertIn("45", text)
        self.assertIn("https://example.com/101", text)
        self.assertIn("https://www.producthunt.com/posts/tool", text)
        self.assertIn("ycombinator.com/companies/scholarly", text)
        # category-velocity header (all three are inside the 90-day window)
        self.assertIn("3 similar launches in the last 90 days", text)
        self.assertIn("saturation", text)

    def test_show_hn_url_carries_show_hn_tag(self):
        fake = FakeGetJson()
        self.run_channel(fake)
        hn_urls = [u for u in fake.urls if "hn.algolia.com" in u]
        self.assertTrue(hn_urls)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(hn_urls[0]).query)
        self.assertIn("show_hn", params["tags"][0])
        self.assertEqual(params["query"], [TOPIC])

    def test_off_topic_launch_dropped_by_relevance_floor(self):
        fake = FakeGetJson(show_hn={"hits": [
            hn_hit("Show HN: AI research tools organizer", 10, 3,
                   days_ago=5, object_id="201"),
            hn_hit("Show HN: My mechanical keyboard build", 900, 300,
                   days_ago=2, object_id="202"),
        ]})
        n, text = self.run_channel(fake)
        self.assertIn("organizer", text)
        self.assertNotIn("keyboard", text)
        # the dropped viral item does not inflate velocity
        self.assertIn("1 similar launches in the last 90 days", text)


class DegradeTests(LaunchRadarCase):
    def test_missing_ph_token_keeps_tier0_and_prints_honest_line(self):
        fake = FakeGetJson(
            show_hn={"hits": [
                hn_hit("Show HN: AI research tools digest", 50, 9,
                       days_ago=7, object_id="301"),
            ]},
            yc_meta=YC_META,
            yc_batches={"summer-2026": [yc_company(
                "Notewise", "AI research tools for note taking",
                days_ago=30)], "spring-2026": []},
        )
        ph = FakePostJson()
        n, text = self.run_channel(fake, post_json=ph, token="")
        self.assertEqual(n, 2)
        self.assertIn("[ShowHN]", text)
        self.assertIn("[YC]", text)
        # honest degrade line, and NO PH network attempt
        self.assertIn("token not configured", text)
        self.assertEqual(ph.calls, [])

    def test_failing_sub_source_leaves_siblings_intact_with_note(self):
        fake = FakeGetJson(
            show_hn={"hits": [
                hn_hit("Show HN: AI research tools workbench", 30, 5,
                       days_ago=3, object_id="401"),
            ]},
            errors={"yc-oss.github.io": RuntimeError("yc boom")},
        )
        n, text = self.run_channel(fake)
        self.assertEqual(n, 1)
        self.assertIn("workbench", text)
        self.assertIn("YC", text)
        self.assertIn("unavailable", text)

    def test_devhunt_error_notes_but_siblings_survive(self):
        fake = FakeGetJson(show_hn={"hits": [
            hn_hit("Show HN: AI research tools CLI", 12, 2,
                   days_ago=4, object_id="501"),
        ]})
        gh = FakeGhApi(error=RuntimeError("gh down"))
        n, text = self.run_channel(fake, gh_api=gh)
        self.assertEqual(n, 1)
        self.assertIn("CLI", text)
        self.assertIn("DevHunt", text)
        self.assertIn("unavailable", text)


class VelocityTests(LaunchRadarCase):
    def test_velocity_counts_only_window_launches_per_source(self):
        fake = FakeGetJson(
            show_hn={"hits": [
                hn_hit("Show HN: AI research tools alpha", 10, 1,
                       days_ago=10, object_id="601"),
                hn_hit("Show HN: AI research tools beta", 10, 1,
                       days_ago=80, object_id="602"),
                hn_hit("Show HN: AI research tools gamma (old)", 10, 1,
                       days_ago=200, object_id="603"),
            ]},
        )
        _, text = self.run_channel(fake)
        # 2 in window (10d, 80d), the 200-day launch renders but is not counted
        self.assertIn("2 similar launches in the last 90 days", text)
        self.assertIn("gamma", text)


class MomentumTests(LaunchRadarCase):
    def test_recency_decay_newer_beats_older_at_equal_votes(self):
        fake = FakeGetJson(show_hn={"hits": [
            hn_hit("Show HN: AI research tools old", 40, 10,
                   days_ago=60, object_id="701"),
            hn_hit("Show HN: AI research tools new", 40, 10,
                   days_ago=2, object_id="702"),
        ]})
        _, text = self.run_channel(fake)
        self.assertLess(
            text.index("AI research tools new"),
            text.index("AI research tools old"),
        )

    def test_no_vote_yc_entries_rank_recency_only_with_honest_note(self):
        fake = FakeGetJson(
            yc_meta=YC_META,
            yc_batches={
                "summer-2026": [yc_company(
                    "Papertrailer", "AI research tools for papers",
                    days_ago=15)],
                "spring-2026": [],
            },
        )
        n, text = self.run_channel(fake)
        self.assertEqual(n, 1)
        self.assertIn("[YC]", text)
        self.assertIn("recency-only", text)
        # no fabricated vote counts on the YC line
        yc_line = next(l for l in text.splitlines() if "[YC]" in l)
        self.assertNotIn("votes", yc_line)

    def test_momentum_pure_function_decays_and_boosts(self):
        m = launch_radar.launch_momentum
        self.assertGreater(m(40, 10, 2.0), m(40, 10, 60.0))
        self.assertGreater(m(400, 10, 5.0), m(4, 10, 5.0))
        self.assertGreater(m(40, 100, 5.0), m(40, 0, 5.0))
        # no votes -> recency-only, still positive and decaying
        self.assertGreater(m(None, None, 5.0), 0.0)
        self.assertGreater(m(None, None, 5.0), m(None, None, 90.0))


class RegistryTests(unittest.TestCase):
    def test_connector_registered_keyless_direct_default(self):
        conn = deep_research.CONNECTORS["launch-radar"]
        self.assertEqual(conn.kind, "direct")
        self.assertEqual(conn.requires, [])
        self.assertTrue(conn.default)
        self.assertTrue(conn.available())
        self.assertIn("shipping", conn.source.lower())

    def test_output_name_present(self):
        self.assertEqual(
            deep_research.OUTPUT_NAMES["launch-radar"], "launch-radar.md"
        )


class WindowsSafetyTests(unittest.TestCase):
    def test_connector_sources_avoid_posix_only_calls(self):
        for src in sorted((SCRIPTS / "connectors").glob("*.py")):
            text = src.read_text(encoding="utf-8")
            for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                          "pwd.", "grp."):
                self.assertNotIn(token, text, f"{src.name} uses {token}")


if __name__ == "__main__":
    unittest.main()

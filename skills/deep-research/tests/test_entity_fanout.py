"""U2 — fan-out orchestrator + ThreadPoolExecutor + reddit strategy.

For each entity, each selected channel runs as a separate cell. Cells drain
through a bounded ThreadPoolExecutor (concurrency cap); a failing cell degrades
to <channel>.ERROR.md without killing siblings; reddit uses the KTD3
topic-subreddits strategy (subs discovered once from the topic, entity queried
within them).

Tiering + budget (U3) and per-host backoff (U4) build on this file; their tests
live here too.

All network is mocked — no live calls, no paid calls.
"""
import importlib.util
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"
FANOUT = SCRIPTS / "entity_fanout.py"

_scripts_path = str(SCRIPTS)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


deep_research = _load("deep_research_fanout", RUNNER)
entity_fanout = _load("entity_fanout_fanout", FANOUT)


def entity(name, rank=0, repo=None):
    e = {"name": name, "type": "repo", "rank": rank, "sources": ["github"], "aliases": []}
    if repo:
        e["repo"] = repo
    return e


class RecordingChannel:
    """A fake channel_* fn that records (query, out_path) and writes canned md."""

    def __init__(self, *, raises=None, tracker=None):
        self.calls = []
        self.raises = raises
        self.tracker = tracker  # optional concurrency tracker

    def __call__(self, query, out_path, max_items):
        self.calls.append((query, str(out_path)))
        if self.tracker is not None:
            self.tracker.enter()
        try:
            if self.raises:
                raise self.raises
            Path(out_path).write_text(f"# result for {query}\n- item\n", encoding="utf-8")
            return 1
        finally:
            if self.tracker is not None:
                self.tracker.exit()


class ConcurrencyTracker:
    def __init__(self, hold=0.03):
        self.hold = hold
        self._lock = threading.Lock()
        self.current = 0
        self.peak = 0

    def enter(self):
        with self._lock:
            self.current += 1
            self.peak = max(self.peak, self.current)
        time.sleep(self.hold)

    def exit(self):
        with self._lock:
            self.current -= 1


class FakeArctic:
    """Records subreddit-discovery topic + posts/search URLs."""

    def __init__(self, subs=("LocalLLaMA", "LLMDevs"), posts=None):
        self.subs = list(subs)
        self.posts = posts or [
            {"id": "p1", "title": "Mem0 is great", "score": 40, "num_comments": 9,
             "subreddit": "LocalLLaMA", "selftext": "using mem0 in prod", "permalink": "/r/x/1"},
        ]
        self.discover_topics = []
        self.search_urls = []

    def discover(self, topic, limit=4):
        self.discover_topics.append(topic)
        return list(self.subs)

    def arctic_json(self, url, timeout=30):
        self.search_urls.append(url)
        return {"data": list(self.posts)}


class FakeRunner:
    def __init__(self, channels, arctic=None):
        # channels: {name: RecordingChannel}
        self.channels = channels
        self.arctic = arctic or FakeArctic()

    def as_globals(self):
        connectors = {
            name: types.SimpleNamespace(name=name, fn=fn)
            for name, fn in self.channels.items()
        }
        return {
            "CONNECTORS": connectors,
            "rank_items": deep_research.rank_items,
            "_arctic_shift_discover_subreddits": self.arctic.discover,
            "_arctic_shift_json": self.arctic.arctic_json,
            "ARCTIC_SHIFT_BASE": "https://arctic-shift.example/api",
            "_REDDIT_POOL_PER_SUB": 25,
            "_REDDIT_WINDOW_DAYS": 365,
        }


class BuildCellsTest(unittest.TestCase):
    def test_free_cells_cartesian(self):
        ents = [entity("mem0"), entity("zep"), entity("letta")]
        cells = entity_fanout.build_free_cells(ents, channels=("hackernews", "bluesky"))
        self.assertEqual(len(cells), 6)
        self.assertTrue(all(c["tier"] == "free" for c in cells))
        self.assertEqual({c["channel"] for c in cells}, {"hackernews", "bluesky"})


class RunMatrixTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _ctx(self, subs=("LocalLLaMA",)):
        return entity_fanout.FanoutContext("LLM agent memory", 5, reddit_subs=subs, sleep=lambda *_: None)

    def test_happy_each_cell_runs_once(self):
        hn = RecordingChannel()
        bsky = RecordingChannel()
        runner = FakeRunner({"hackernews": hn, "bluesky": bsky})
        entity_fanout.attach_runner(runner.as_globals())
        ents = [entity("mem0"), entity("zep"), entity("letta")]
        cells = entity_fanout.build_free_cells(ents, channels=("hackernews", "bluesky"))
        records = entity_fanout.run_matrix(cells, self.tmp, self._ctx(), concurrency=4)
        self.assertEqual(len(records), 6)
        self.assertTrue(all(r["status"] == "ok" for r in records))
        # each channel called once per entity, with the entity name as query
        self.assertEqual(sorted(q for q, _ in hn.calls), ["letta", "mem0", "zep"])
        self.assertEqual(sorted(q for q, _ in bsky.calls), ["letta", "mem0", "zep"])
        # output files written under entities/<slug>/<channel>.md
        self.assertTrue((Path(self.tmp) / "entities" / "mem0" / "hackernews.md").exists())

    def test_github_issues_query_uses_repo(self):
        ghi = RecordingChannel()
        runner = FakeRunner({"github-issues": ghi})
        entity_fanout.attach_runner(runner.as_globals())
        ents = [entity("mem0", repo="mem0ai/mem0"), entity("zep")]  # zep has no repo
        cells = entity_fanout.build_free_cells(ents, channels=("github-issues",))
        entity_fanout.run_matrix(cells, self.tmp, self._ctx(), concurrency=2)
        queries = sorted(q for q, _ in ghi.calls)
        self.assertEqual(queries, ["mem0ai/mem0", "zep"])  # repo when present, else name

    def test_concurrency_cap_respected(self):
        tracker = ConcurrencyTracker(hold=0.04)
        hn = RecordingChannel(tracker=tracker)
        runner = FakeRunner({"hackernews": hn})
        entity_fanout.attach_runner(runner.as_globals())
        ents = [entity(f"e{i}") for i in range(8)]
        cells = entity_fanout.build_free_cells(ents, channels=("hackernews",))
        entity_fanout.run_matrix(cells, self.tmp, self._ctx(), concurrency=2)
        self.assertLessEqual(tracker.peak, 2, f"peak concurrency {tracker.peak} exceeded cap 2")
        self.assertEqual(len(hn.calls), 8)

    def test_per_cell_degrade_writes_error_and_siblings_survive(self):
        good = RecordingChannel()
        bad = RecordingChannel(raises=RuntimeError("boom"))
        runner = FakeRunner({"hackernews": good, "bluesky": bad})
        entity_fanout.attach_runner(runner.as_globals())
        ents = [entity("mem0"), entity("zep")]
        cells = entity_fanout.build_free_cells(ents, channels=("hackernews", "bluesky"))
        records = entity_fanout.run_matrix(cells, self.tmp, self._ctx(), concurrency=4)
        by = {(r["entity"], r["channel"]): r for r in records}
        self.assertEqual(by[("mem0", "hackernews")]["status"], "ok")
        self.assertEqual(by[("mem0", "bluesky")]["status"], "error")
        # ERROR.md written, sibling ok file present
        self.assertTrue((Path(self.tmp) / "entities" / "mem0" / "bluesky.ERROR.md").exists())
        self.assertTrue((Path(self.tmp) / "entities" / "mem0" / "hackernews.md").exists())

    def test_empty_cells_noop(self):
        runner = FakeRunner({"hackernews": RecordingChannel()})
        entity_fanout.attach_runner(runner.as_globals())
        self.assertEqual(entity_fanout.run_matrix([], self.tmp, self._ctx()), [])


class RedditStrategyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_subs_discovered_once_from_topic(self):
        arctic = FakeArctic(subs=["LocalLLaMA", "LLMDevs"])
        runner = FakeRunner({}, arctic=arctic)
        entity_fanout.attach_runner(runner.as_globals())
        subs = entity_fanout.discover_reddit_subs("LLM agent memory")
        self.assertEqual(subs, ["LocalLLaMA", "LLMDevs"])
        self.assertEqual(arctic.discover_topics, ["LLM agent memory"])  # topic, once

    def test_discover_degrades_to_empty(self):
        arctic = FakeArctic()
        arctic.discover = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429"))
        runner = FakeRunner({}, arctic=arctic)
        entity_fanout.attach_runner(runner.as_globals())
        self.assertEqual(entity_fanout.discover_reddit_subs("x"), [])

    def test_reddit_cell_queries_entity_within_topic_subs(self):
        arctic = FakeArctic(subs=["LocalLLaMA", "LLMDevs"])
        runner = FakeRunner({}, arctic=arctic)
        entity_fanout.attach_runner(runner.as_globals())
        ctx = entity_fanout.FanoutContext(
            "LLM agent memory", 5, reddit_subs=["LocalLLaMA", "LLMDevs"], sleep=lambda *_: None
        )
        out = Path(self.tmp) / "reddit.md"
        n = entity_fanout._reddit_entity_cell("Mem0", ctx, out)
        self.assertGreaterEqual(n, 1)
        # queried BOTH topic subs, with the entity as the query term
        self.assertEqual(len(arctic.search_urls), 2)
        for url in arctic.search_urls:
            self.assertIn("query=Mem0", url)
        self.assertRegex(out.read_text(), r"Mem0")

    def test_reddit_cell_no_subs_is_honest_empty(self):
        runner = FakeRunner({})
        entity_fanout.attach_runner(runner.as_globals())
        ctx = entity_fanout.FanoutContext("x", 5, reddit_subs=[], sleep=lambda *_: None)
        out = Path(self.tmp) / "reddit.md"
        n = entity_fanout._reddit_entity_cell("Mem0", ctx, out)
        self.assertEqual(n, 0)
        self.assertIn("skipped", out.read_text())


class TieringTest(unittest.TestCase):
    """U3 — hybrid tiering + paid-budget cap + --paid-all."""

    def _ents(self, n):
        return [entity(f"e{i}", rank=i) for i in range(n)]

    def _counts(self, cells):
        free = sum(1 for c in cells if c["tier"] == "free")
        paid = sum(1 for c in cells if c["tier"] == "paid")
        return free, paid

    def test_hybrid_default(self):
        cells, rep = entity_fanout.plan_cells(
            self._ents(5), {"grok": "x", "gemini": "y"},
            free_channels=("hackernews", "github-issues"), k=2,
        )
        free, paid = self._counts(cells)
        self.assertEqual(free, 10)   # 5 entities x 2 free channels
        self.assertEqual(paid, 4)    # top-2 entities x 2 available lenses
        self.assertEqual(rep["paid_budget"], 4)
        self.assertEqual(rep["paid_trimmed"], 0)

    def test_paid_all_not_trimmed_back(self):
        # regression guard: --paid-all must raise the budget, not be trimmed
        # back to the default K x lenses.
        cells, rep = entity_fanout.plan_cells(
            self._ents(5), {"grok": "x", "gemini": "y"},
            free_channels=("hackernews",), k=2, paid_all=True,
        )
        free, paid = self._counts(cells)
        self.assertEqual(paid, 10)   # all 5 x 2 lenses, NOT trimmed to 4
        self.assertEqual(rep["paid_trimmed"], 0)
        self.assertEqual(rep["paid_budget"], 10)

    def test_explicit_budget_trims_keeping_top_rank(self):
        cells, rep = entity_fanout.plan_cells(
            self._ents(5), {"grok": "x", "gemini": "y"},
            free_channels=("hackernews",), k=2, paid_budget=2,
        )
        _, paid = self._counts(cells)
        self.assertEqual(paid, 2)
        self.assertEqual(rep["paid_trimmed"], 2)
        # the 2 surviving paid cells belong to the top-rank entity (e0)
        paid_entities = {c["entity"]["name"] for c in cells if c["tier"] == "paid"}
        self.assertEqual(paid_entities, {"e0"})

    def test_lens_absent_not_created(self):
        # only a grok key, no gemini, no openrouter fallback -> gemini absent
        cells, rep = entity_fanout.plan_cells(
            self._ents(5), {"grok": "x"},
            free_channels=("hackernews",), k=3,
        )
        self.assertEqual(rep["available_lenses"], ["grok"])
        paid_channels = {c["channel"] for c in cells if c["tier"] == "paid"}
        self.assertEqual(paid_channels, {"grok"})

    def test_openrouter_fallback_enables_all_lenses(self):
        _, rep = entity_fanout.plan_cells(
            self._ents(3), {"openrouter": "sk-or-x"}, k=1,
        )
        self.assertEqual(rep["available_lenses"], list(entity_fanout.PAID_LENSES))

    def test_free_never_gated_by_budget(self):
        cells, rep = entity_fanout.plan_cells(
            self._ents(4), {"grok": "x"},
            free_channels=("hackernews", "bluesky"), k=2, paid_budget=0,
        )
        free, paid = self._counts(cells)
        self.assertEqual(free, 8)   # 4 x 2 free channels — untouched by budget
        self.assertEqual(paid, 0)   # budget 0 => no paid cells


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", None, None)


class BackoffTest(unittest.TestCase):
    """U4 — per-host pacing + deterministic backoff (reddit/bluesky)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sleeps = []
        self.ctx = entity_fanout.FanoutContext(
            "topic", 5, sleep=lambda s: self.sleeps.append(s)
        )

    def test_paced_retries_then_succeeds(self):
        seq = [http_error(429), None]

        def thunk():
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return 5

        self.assertEqual(self.ctx.paced("reddit", thunk), 5)
        self.assertEqual(self.sleeps, [1.0])  # base * 2**0

    def test_paced_persistent_403_reraises(self):
        def thunk():
            raise http_error(403)

        with self.assertRaises(urllib.error.HTTPError):
            self.ctx.paced("bluesky", thunk)
        self.assertEqual(self.sleeps, [1.0, 2.0, 4.0])  # retries=3, deterministic

    def test_paced_non_throttle_status_not_retried(self):
        calls = []

        def thunk():
            calls.append(1)
            raise http_error(500)

        with self.assertRaises(urllib.error.HTTPError):
            self.ctx.paced("reddit", thunk)
        self.assertEqual(len(calls), 1)  # 500 is not retried
        self.assertEqual(self.sleeps, [])

    def test_run_cell_throttled_degrades_after_backoff(self):
        bad = RecordingChannel(raises=http_error(403))
        runner = FakeRunner({"bluesky": bad})
        entity_fanout.attach_runner(runner.as_globals())
        cell = {"entity": entity("mem0"), "channel": "bluesky", "tier": "free"}
        rec = entity_fanout._run_cell(cell, self.tmp, self.ctx)
        self.assertEqual(rec["status"], "error")
        self.assertEqual(len(bad.calls), 4)  # initial + 3 retries
        self.assertEqual(self.sleeps, [1.0, 2.0, 4.0])
        self.assertTrue((Path(self.tmp) / "entities" / "mem0" / "bluesky.ERROR.md").exists())

    def test_run_cell_non_throttled_not_retried(self):
        bad = RecordingChannel(raises=http_error(403))
        runner = FakeRunner({"hackernews": bad})
        entity_fanout.attach_runner(runner.as_globals())
        cell = {"entity": entity("mem0"), "channel": "hackernews", "tier": "free"}
        rec = entity_fanout._run_cell(cell, self.tmp, self.ctx)
        self.assertEqual(rec["status"], "error")
        self.assertEqual(len(bad.calls), 1)  # hackernews is not throttled — no retry
        self.assertEqual(self.sleeps, [])

    def test_host_locks_distinct_and_reused(self):
        self.assertIs(self.ctx.host_lock("reddit"), self.ctx.host_lock("reddit"))
        self.assertIsNot(self.ctx.host_lock("reddit"), self.ctx.host_lock("bluesky"))


if __name__ == "__main__":
    unittest.main()

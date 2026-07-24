"""U14 — Reddit channel on Arctic-Shift (R6, R21).

The old reddit.com/search.json path is dead (throttled). channel_reddit now
talks to the free Arctic-Shift archive. Live-probe facts these tests encode:

  - GET /api/posts/search returns {"data": [...]} with real `score` and
    `num_comments` fields;
  - free-text `query` REQUIRES a `subreddit` (or author) filter, so the
    channel discovers candidate subreddits first via
    GET /api/subreddits/search?subreddit_prefix=<topic token>;
  - no server-side score sort (sort_type is default|created_utc only), so
    ranking happens client-side via the U10 rank_items helper.

All network is mocked — no live calls in tests.
"""
import importlib.util
import io
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
    SPEC = importlib.util.spec_from_file_location("deep_research_reddit", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "context engineering"

SUBREDDIT_ROW = {
    "display_name": "LocalLLaMA",
    "subscribers": 550000,
    "title": "LocalLLaMA",
    "public_description": "Community about context engineering and local LLM agents",
}


def post(pid, title, score=None, num_comments=None, subreddit="LocalLLaMA", selftext=""):
    d = {
        "id": pid,
        "title": title,
        "subreddit": subreddit,
        "created_utc": 1780000000,
        "selftext": selftext,
    }
    if score is not None:
        d["score"] = score
    if num_comments is not None:
        d["num_comments"] = num_comments
    return d


class FakeArcticShift:
    """URL-routing stand-in for get_json. Records every URL it serves."""

    def __init__(self, subreddits=None, posts=None, posts_error=None):
        self.subreddits = subreddits if subreddits is not None else [SUBREDDIT_ROW]
        self.posts = posts if posts is not None else []
        self.posts_error = posts_error
        self.urls = []

    def __call__(self, url, headers=None, timeout=30):
        self.urls.append(url)
        if "/api/subreddits/search" in url:
            return {"data": self.subreddits}
        if "/api/posts/search" in url:
            if self.posts_error is not None:
                raise self.posts_error
            return {"data": self.posts}
        raise AssertionError(f"unexpected URL fetched: {url}")

    def post_search_urls(self):
        return [u for u in self.urls if "/api/posts/search" in u]


def run_channel(fake, topic=TOPIC, max_items=5):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "reddit.md"
        with mock.patch.object(deep_research, "get_json", fake):
            n = deep_research.channel_reddit(topic, out, max_items)
        return n, out.read_text()


class ArcticShiftHappyPathTests(unittest.TestCase):
    def test_posts_ranked_with_scores_and_formatted_markdown(self):
        fake = FakeArcticShift(posts=[
            post("aaa111", "Best pizza in town", score=9800, num_comments=2100),
            post("bbb222", "Context engineering field notes", score=180,
                 num_comments=43),
            post("ccc333", "More context engineering tricks", score=40,
                 num_comments=12),
        ])
        n, text = run_channel(fake)

        self.assertEqual(n, 3)
        # same output style as before: title, ▲score, comments, subreddit
        self.assertIn("**Context engineering field notes** — ▲180, 43 comments, r/LocalLLaMA", text)
        # permalink constructed from subreddit + id
        self.assertIn("https://www.reddit.com/r/LocalLLaMA/comments/bbb222", text)
        # ranked: on-topic first, off-topic viral demoted below both (floor)
        self.assertLess(text.index("field notes"), text.index("tricks"))
        self.assertLess(text.index("tricks"), text.index("Best pizza"))

    def test_only_arctic_shift_is_contacted(self):
        fake = FakeArcticShift(posts=[post("aaa", "Context engineering", score=5, num_comments=1)])
        run_channel(fake)
        self.assertTrue(fake.urls)
        for url in fake.urls:
            self.assertIn("arctic-shift.photon-reddit.com", url)
            self.assertNotIn("reddit.com/search.json", url)

    def test_post_search_carries_query_and_subreddit_params(self):
        fake = FakeArcticShift(posts=[])
        run_channel(fake)
        searches = fake.post_search_urls()
        self.assertTrue(searches)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(searches[0]).query)
        self.assertEqual(params["query"], [TOPIC])
        self.assertEqual(params["subreddit"], ["LocalLLaMA"])
        self.assertIn("after", params)  # recency window


class ArcticShiftDegradeTests(unittest.TestCase):
    def test_empty_result_writes_honest_empty_message(self):
        fake = FakeArcticShift(posts=[])
        n, text = run_channel(fake)
        self.assertEqual(n, 0)
        self.assertIn("No posts found", text)

    def test_no_name_match_falls_back_to_curated_net_not_blind(self):
        # New contract: when no subreddit matches the topic by name, discovery
        # no longer gives up — it falls back to the curated high-signal net and
        # searches it. With no posts there it still degrades honestly (n=0,
        # "No posts found"), but Reddit is no longer silently blind: the
        # curated subs WERE searched.
        fake = FakeArcticShift(subreddits=[], posts=[])
        n, text = run_channel(fake)
        self.assertEqual(n, 0)
        searched = fake.post_search_urls()
        self.assertTrue(searched)  # fallback searched, did not skip
        curated = {name for name, _ in deep_research._REDDIT_CURATED_SUBS}
        subs_hit = {
            urllib.parse.parse_qs(urllib.parse.urlparse(u).query)["subreddit"][0]
            for u in searched
        }
        self.assertTrue(subs_hit & curated)  # the net is the curated set
        self.assertIn("No posts found", text)

    def test_http_error_propagates_so_wrapper_writes_error_md(self):
        err = urllib.error.HTTPError(
            "https://arctic-shift.photon-reddit.com/api/posts/search",
            500, "Server Error", None, io.BytesIO(b"boom"),
        )
        fake = FakeArcticShift(posts_error=err)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reddit.md"
            with mock.patch.object(deep_research, "get_json", fake):
                with self.assertRaises(urllib.error.HTTPError):
                    deep_research.channel_reddit(TOPIC, out, 5)

    def _rate_limit_error(self):
        return urllib.error.HTTPError(
            "https://arctic-shift.photon-reddit.com/api/posts/search",
            429, "Too Many Requests", None, io.BytesIO(b"slow down"),
        )

    def test_429_is_retried_once_then_succeeds(self):
        # Observed live 2026-07-17: {"error":"Too many complex queries.
        # Please slow down."} — one polite retry rescues the run.
        state = {"failed": False}
        inner = FakeArcticShift(posts=[
            post("aaa", "Context engineering field notes", score=7, num_comments=3),
        ])
        outer_self = self

        def flaky(url, headers=None, timeout=30):
            if "/api/posts/search" in url and not state["failed"]:
                state["failed"] = True
                raise outer_self._rate_limit_error()
            return inner(url, headers=headers, timeout=timeout)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reddit.md"
            with mock.patch.object(deep_research, "get_json", flaky), \
                 mock.patch.object(deep_research, "_ARCTIC_SHIFT_RETRY_SLEEP", 0):
                n = deep_research.channel_reddit(TOPIC, out, 5)
            text = out.read_text()
        self.assertEqual(n, 1)
        self.assertIn("Context engineering field notes", text)

    def test_persistent_429_still_propagates(self):
        fake = FakeArcticShift(posts_error=self._rate_limit_error())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reddit.md"
            with mock.patch.object(deep_research, "get_json", fake), \
                 mock.patch.object(deep_research, "_ARCTIC_SHIFT_RETRY_SLEEP", 0):
                with self.assertRaises(urllib.error.HTTPError):
                    deep_research.channel_reddit(TOPIC, out, 5)

    def test_missing_score_fields_emit_degradation_note_not_crash(self):
        fake = FakeArcticShift(posts=[
            post("aaa", "Context engineering field notes"),
            post("bbb", "More context engineering tricks"),
        ])
        n, text = run_channel(fake)
        self.assertEqual(n, 2)
        self.assertIn("Context engineering field notes", text)
        low = text.lower()
        self.assertTrue(
            "degraded" in low or "without score" in low or "score fields" in low,
            f"no degradation note in output:\n{text}",
        )


class SubredditDiscoveryTests(unittest.TestCase):
    def test_concatenated_topic_name_beats_big_loose_match(self):
        # r/PromptEngineering (name = topic tokens concatenated, sparse
        # description) must beat a huge subreddit that only matches one
        # token — live pattern: "engineering" prefix returns meme subs.
        exact = {
            "display_name": "PromptEngineering",
            "subscribers": 8000,
            "title": "",
            "public_description": "",
        }
        loose = {
            "display_name": "EngineeringMemes",
            "subscribers": 900000,
            "title": "Engineering memes",
            "public_description": "The best engineering memes",
        }

        def fake(url, headers=None, timeout=30):
            assert "/api/subreddits/search" in url
            return {"data": [loose, exact]}

        with mock.patch.object(deep_research, "get_json", fake):
            subs = deep_research._arctic_shift_discover_subreddits(
                "prompt engineering"
            )
        self.assertEqual(subs[0], "PromptEngineering")


class CuratedFallbackTests(unittest.TestCase):
    """The reported failure (0 items): a multi-word technical query whose real
    home is r/LocalLLaMA, a name no query token prefixes. Name-prefix discovery
    returns only off-topic junk (r/Agent_SEO); the curated fallback is what
    turns a silent zero into dated, on-topic posts — and re-feeds the freshness
    axis eval_harness reads."""

    FAILING_QUERY = "AI agent memory Mem0 Letta problems"

    def test_junk_prefix_matches_fall_back_to_curated_and_return_dated_posts(self):
        junk_subs = [
            {"display_name": "Agent_SEO", "subscribers": 1200,
             "title": "", "public_description": "seo agents marketing"},
            {"display_name": "MemoryDefrag", "subscribers": 300,
             "title": "", "public_description": "defrag memes"},
        ]
        curated = {name for name, _ in deep_research._REDDIT_CURATED_SUBS}
        # The real, dated, on-topic post lives in a curated sub — junk subs
        # yield nothing, exactly as observed live.
        hit = post("zzz999", "Benchmarked 4 agent memory systems: Mem0 vs Letta",
                   score=340, num_comments=88, subreddit="LocalLLaMA")

        def fake(url, headers=None, timeout=30):
            if "/api/subreddits/search" in url:
                return {"data": junk_subs}
            if "/api/posts/search" in url:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                sub = params["subreddit"][0]
                return {"data": [hit] if sub in curated else []}
            raise AssertionError(f"unexpected URL: {url}")

        sink = []
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reddit.md"
            with mock.patch.object(deep_research, "get_json", fake):
                n = deep_research.channel_reddit(self.FAILING_QUERY, out, 5, sink)
            text = out.read_text()

        self.assertGreaterEqual(n, 1)  # was 0 before the fallback
        self.assertIn("Benchmarked 4 agent memory systems", text)
        self.assertIn("r/LocalLLaMA", text)
        self.assertTrue(sink)  # freshness axis fed — eval_harness reads this

    def test_curated_fallback_ranking_is_deterministic_and_on_topic(self):
        subs = deep_research._curated_fallback_subs(self.FAILING_QUERY)
        self.assertEqual(subs, deep_research._curated_fallback_subs(self.FAILING_QUERY))
        self.assertLessEqual(len(subs), deep_research._REDDIT_MAX_SUBS)
        # an AI-agent-memory query surfaces the LLM/agent hubs, not e.g. r/SaaS
        self.assertIn("LocalLLaMA", subs)
        self.assertTrue({"AI_Agents", "LangChain"} & set(subs))

    def test_single_token_query_does_not_force_every_prefix_match_relevant(self):
        # Regression: for a single-token query the topic "concatenation" equals
        # the subreddit_prefix, so every prefix hit contains it. The concat
        # override must NOT fire here, or a big off-topic sub (r/ragdoll for
        # "rag") would be forced relevant and outrank the real one by size.
        ragdoll = {"display_name": "ragdoll", "subscribers": 200000,
                   "title": "Ragdoll cats", "public_description": "ragdoll cat breed pictures"}
        real = {"display_name": "Rag", "subscribers": 5000, "title": "RAG",
                "public_description": "retrieval augmented generation rag for llms"}

        def fake(url, headers=None, timeout=30):
            assert "/api/subreddits/search" in url
            return {"data": [ragdoll, real]}

        with mock.patch.object(deep_research, "get_json", fake):
            subs = deep_research._arctic_shift_discover_subreddits("rag")
        self.assertIn("Rag", subs)
        # the real (on-topic, smaller) sub must beat the huge off-topic one
        self.assertLess(subs.index("Rag"), subs.index("ragdoll")
                        if "ragdoll" in subs else len(subs))
        self.assertNotEqual(subs[0], "ragdoll")

    def test_single_token_query_with_only_offtopic_prefix_hits_uses_curated(self):
        # "rag" where the only prefix hit is off-topic (r/ragdoll): nothing
        # clears the floor -> the curated net rescues it instead of searching
        # the cat subreddit.
        ragdoll = {"display_name": "ragdoll", "subscribers": 200000,
                   "title": "Ragdoll cats", "public_description": "ragdoll cat breed pictures"}

        def fake(url, headers=None, timeout=30):
            assert "/api/subreddits/search" in url
            return {"data": [ragdoll]}

        with mock.patch.object(deep_research, "get_json", fake):
            subs = deep_research._arctic_shift_discover_subreddits("rag")
        curated = {name for name, _ in deep_research._REDDIT_CURATED_SUBS}
        self.assertTrue(set(subs) & curated)
        self.assertNotEqual(subs[0], "ragdoll")

    def test_strong_name_match_short_circuits_fallback(self):
        # A real on-topic name match must NOT trigger the curated net (no
        # behaviour change / no extra breadth for queries that already work).
        row = {"display_name": "LocalLLaMA", "subscribers": 550000,
               "title": "LocalLLaMA",
               "public_description": "AI agent memory, Mem0, Letta and local LLMs"}

        def fake(url, headers=None, timeout=30):
            assert "/api/subreddits/search" in url
            return {"data": [row]}

        with mock.patch.object(deep_research, "get_json", fake):
            subs = deep_research._arctic_shift_discover_subreddits(self.FAILING_QUERY)
        self.assertEqual(subs, ["LocalLLaMA"])


class ConnectorRegistryTests(unittest.TestCase):
    def test_reddit_source_mentions_arctic_shift(self):
        source = deep_research.CONNECTORS["reddit"].source
        self.assertIn("arctic", source.lower())

    def test_reddit_stays_keyless_and_default(self):
        conn = deep_research.CONNECTORS["reddit"]
        self.assertEqual(conn.requires, [])
        self.assertTrue(conn.default)
        self.assertTrue(conn.available())


if __name__ == "__main__":
    unittest.main()

"""U10 — ranking upgrade: comment-evidence + relevance floor (R21).

Pure-function tests for the shared scoring helper in deep-research.py plus
one integration check that channel_hackernews actually orders by it.
No network: everything is fixture-driven / mocked.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_ranking", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "context engineering for LLM agents"


def item(title, votes, comments=None, **extra):
    d = {"title": title, "votes": votes}
    if comments is not None:
        d["comments"] = comments
    d.update(extra)
    return d


def rank(items, topic=TOPIC, **kw):
    kw.setdefault("text_key", "title")
    kw.setdefault("engagement_key", "votes")
    kw.setdefault("comments_key", "comments")
    return deep_research.rank_items(items, topic, **kw)


class RelevanceScoreTests(unittest.TestCase):
    def test_full_overlap_scores_higher_than_partial_and_none(self):
        full = deep_research.relevance_score(
            "Context engineering patterns for LLM agents", TOPIC
        )
        partial = deep_research.relevance_score(
            "How we manage context at scale", TOPIC
        )
        none = deep_research.relevance_score("Cute cat does a backflip", TOPIC)
        self.assertGreater(full, partial)
        self.assertGreater(partial, none)
        self.assertEqual(none, 0.0)

    def test_case_insensitive(self):
        a = deep_research.relevance_score("CONTEXT ENGINEERING", TOPIC)
        b = deep_research.relevance_score("context engineering", TOPIC)
        self.assertEqual(a, b)
        self.assertGreater(a, 0.0)

    def test_stopword_only_topic_does_not_gate(self):
        # No distinctive tokens to match against -> nothing to gate on.
        self.assertEqual(deep_research.relevance_score("anything at all", "the of and"), 1.0)

    def test_empty_text_is_zero(self):
        self.assertEqual(deep_research.relevance_score("", TOPIC), 0.0)
        self.assertEqual(deep_research.relevance_score(None, TOPIC), 0.0)


class RankItemsFloorTests(unittest.TestCase):
    def test_on_topic_high_engagement_outranks_off_topic_viral(self):
        on_topic = item("Context engineering for LLM agents in production", 150, 80)
        viral = item("Cute cat does a backflip on a skateboard", 12000, 3000)
        result = rank([viral, on_topic])
        self.assertEqual(result.items[0]["title"], on_topic["title"])
        self.assertIsNone(result.note)

    def test_off_topic_huge_votes_stays_below_every_on_topic_item(self):
        # Even a tiny on-topic item must strictly outrank the below-floor
        # viral one, regardless of the vote gap.
        small_on_topic = item("Notes on context engineering", 5, 2)
        viral = item("You won't believe this pasta recipe", 50000, 9000)
        result = rank([viral, small_on_topic])
        self.assertEqual(result.items[0]["title"], small_on_topic["title"])
        self.assertEqual(result.items[1]["title"], viral["title"])


class BotPenaltyTests(unittest.TestCase):
    def test_like_heavy_comment_light_penalized_vs_balanced_same_votes(self):
        too_clean = item("Context engineering for LLM agents — thread A", 5000, 2)
        balanced = item("Context engineering for LLM agents — thread B", 5000, 400)
        result = rank([too_clean, balanced])
        self.assertEqual(result.items[0]["title"], balanced["title"])

    def test_no_penalty_when_comment_data_unavailable(self):
        # Without a comments_key the same-votes items keep input order
        # (no fabricated penalty from absent data).
        a = item("Context engineering for LLM agents — first", 5000)
        b = item("Context engineering for LLM agents — second", 5000)
        result = rank([a, b], comments_key=None)
        self.assertEqual(
            [i["title"] for i in result.items], [a["title"], b["title"]]
        )


class DegradeTests(unittest.TestCase):
    def test_all_low_relevance_returns_best_effort_plus_note(self):
        items = [
            item("Cute cat does a backflip", 300, 40),
            item("Best pasta recipe of 2026", 900, 120),
        ]
        result = rank(items)
        # best-effort: still returns everything, higher engagement first
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0]["title"], "Best pasta recipe of 2026")
        self.assertTrue(result.note)

    def test_note_is_none_when_at_least_one_item_clears_floor(self):
        items = [
            item("Cute cat does a backflip", 300, 40),
            item("Context engineering for LLM agents", 10, 1),
        ]
        result = rank(items)
        self.assertIsNone(result.note)

    def test_empty_input_is_fine(self):
        result = rank([])
        self.assertEqual(result.items, [])


class StabilityTests(unittest.TestCase):
    def test_same_input_twice_gives_identical_order(self):
        items = [
            item("Context engineering for LLM agents", 100, 20),
            item("LLM agents in production", 100, 20),
            item("Cute cat", 5000, 900),
            item("Engineering better prompts", 40, 3),
        ]
        r1 = rank(list(items))
        r2 = rank(list(items))
        self.assertEqual(
            [i["title"] for i in r1.items], [i["title"] for i in r2.items]
        )

    def test_exact_ties_preserve_input_order(self):
        a = item("Context engineering for LLM agents — A", 100, 20)
        b = item("Context engineering for LLM agents — B", 100, 20)
        result = rank([a, b])
        self.assertEqual(
            [i["title"] for i in result.items], [a["title"], b["title"]]
        )

    def test_max_items_truncates_after_ranking(self):
        items = [
            item("Cute cat", 9000, 1000),
            item("Context engineering deep dive", 50, 10),
            item("LLM agents field notes", 40, 8),
        ]
        result = rank(items, max_items=2)
        self.assertEqual(len(result.items), 2)
        # the below-floor viral item must be the one truncated away
        titles = [i["title"] for i in result.items]
        self.assertNotIn("Cute cat", titles)

    def test_bounded_engagement_ten_k_votes_cannot_dominate_purely_on_votes(self):
        # Both on-topic; one has 100x the votes but the combined score must
        # stay within a bounded (log-ish) band, not 100x apart.
        lo = deep_research.engagement_score(100, 50)
        hi = deep_research.engagement_score(10000, 5000)
        self.assertLess(hi, lo * 4)


class HackerNewsRankingIntegrationTests(unittest.TestCase):
    def test_channel_hackernews_orders_on_topic_first(self):
        hits = [
            {  # off-topic viral — Algolia returned it first
                "title": "Show HN: I made a cat gif generator",
                "objectID": "1",
                "points": 9500,
                "num_comments": 2100,
                "created_at": "2026-05-01T00:00:00Z",
                "url": "https://example.com/cats",
            },
            {
                "title": "Context engineering for LLM agents",
                "objectID": "2",
                "points": 210,
                "num_comments": 130,
                "created_at": "2026-06-01T00:00:00Z",
                "url": "https://example.com/context",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hackernews.md"
            with mock.patch.object(
                deep_research, "get_json", return_value={"hits": hits}
            ):
                deep_research.channel_hackernews(TOPIC, out, 10)
            text = out.read_text()
        self.assertLess(
            text.index("Context engineering for LLM agents"),
            text.index("cat gif generator"),
        )
        # output style unchanged: pts/comments/discussion lines survive
        self.assertIn("210 pts, 130 comments", text)
        self.assertIn("https://news.ycombinator.com/item?id=2", text)


if __name__ == "__main__":
    unittest.main()

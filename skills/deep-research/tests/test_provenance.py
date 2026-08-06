"""U1 — coverage-provenance helper (R6, R7).

web_index_reachable classifies each source against the static reachability
table ("can a web-index researcher reach this content?") plus the freshness
override for live-social sources; provenance_record builds the truthful
per-fire record coverage-receipts render from. Pure functions — no network,
no keys, nothing mocked because nothing reaches the wire.
"""
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PROVENANCE = SCRIPTS / "provenance.py"

_scripts_path = str(SCRIPTS)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


provenance = _load("provenance_mod", PROVENANCE)


RECORD_KEYS = {
    "source", "query", "items", "fetched_at",
    "freshness_hours", "web_index_reachable", "reason",
}


class ReachabilityTableTest(unittest.TestCase):
    def test_telegram_is_no(self):
        tag, reason = provenance.web_index_reachable("telegram", 200)
        self.assertEqual(tag, "no")
        self.assertIn("web footprint", reason)

    def test_telegram_fresh_stays_no(self):
        # Already "no" — the freshness override must not touch it.
        tag, _ = provenance.web_index_reachable("telegram", 3)
        self.assertEqual(tag, "no")

    def test_github_is_yes(self):
        tag, _ = provenance.web_index_reachable("github", 10)
        self.assertEqual(tag, "yes")

    def test_known_yes_sources(self):
        for source in ("github-issues", "hackernews", "bluesky", "gemini",
                       "perplexity"):
            tag, _ = provenance.web_index_reachable(source, 100)
            self.assertEqual(tag, "yes", f"{source} must be web-reachable")

    def test_grok_old_is_partial(self):
        tag, reason = provenance.web_index_reachable("grok", 200)
        self.assertEqual(tag, "partial")
        self.assertIn("web index", reason)

    def test_grok_fresh_flips_to_no(self):
        # Live-X item 3h old — no web index has crawled it yet.
        tag, reason = provenance.web_index_reachable("grok", 3)
        self.assertEqual(tag, "no")
        self.assertIn("3h ago", reason)
        self.assertIn("not yet web-indexed", reason)

    def test_grok_unknown_age_stays_partial(self):
        # No age known — never over-claim un-reachability.
        tag, _ = provenance.web_index_reachable("grok", None)
        self.assertEqual(tag, "partial")

    def test_reddit_is_partial_regardless_of_freshness(self):
        # Arctic-Shift archive depth vs top-of-Google — not a live pre-index
        # story, so the freshness override does not apply.
        for age in (None, 3, 500):
            tag, reason = provenance.web_index_reachable("reddit", age)
            self.assertEqual(tag, "partial")
            self.assertIn("archive", reason)

    def test_youtube_is_partial_because_speech_is_not_indexed(self):
        # A web index reads the title and description; it does not read what
        # the speaker actually said.
        for age in (None, 3, 500):
            tag, reason = provenance.web_index_reachable("youtube", age)
            self.assertEqual(tag, "partial")
            self.assertIn("said", reason)

    def test_self_sourced_evidence_is_no_for_any_source(self):
        # We produced the text ourselves (own transcription): it provably
        # exists in no index. This is a fact about the run, not a heuristic.
        for source in ("youtube", "github", "hackernews"):
            tag, reason = provenance.web_index_reachable(
                source, 500, self_sourced=True
            )
            self.assertEqual(tag, "no", f"{source} self-sourced must be 'no'")
            self.assertIn("no web index", reason)

    def test_self_sourced_outranks_the_static_table(self):
        plain, _ = provenance.web_index_reachable("youtube", 500)
        owned, _ = provenance.web_index_reachable("youtube", 500,
                                                  self_sourced=True)
        self.assertEqual(plain, "partial")
        self.assertEqual(owned, "no")


class SelfSourcedRecordTests(unittest.TestCase):
    def test_record_carries_the_self_sourced_downgrade(self):
        record = provenance.provenance_record(
            "youtube", "context engineering", 3, self_sourced=True
        )
        self.assertEqual(record["web_index_reachable"], "no")

    def test_default_record_makes_no_self_sourced_claim(self):
        record = provenance.provenance_record("youtube", "q", 3)
        self.assertEqual(record["web_index_reachable"], "partial")

    def test_an_empty_result_can_never_claim_self_sourced(self):
        """Zero items means we produced nothing — claiming un-indexable
        evidence there would be a lie."""
        record = provenance.provenance_record(
            "youtube", "q", 0, self_sourced=True
        )
        self.assertEqual(record["web_index_reachable"], "partial")

    def test_unknown_source_defaults_to_yes(self):
        # Conservative default: never claim un-reachability we can't prove.
        tag, reason = provenance.web_index_reachable("some-new-connector", 5)
        self.assertEqual(tag, "yes")
        self.assertTrue(reason, "unknown-source reason must not be empty")

    def test_reasons_are_human_readable(self):
        for source in ("telegram", "grok", "reddit", "github", "made-up"):
            _, reason = provenance.web_index_reachable(source, 100)
            self.assertIsInstance(reason, str)
            self.assertGreater(len(reason.split()), 2,
                               f"{source} reason reads like prose, not a code")


class ProvenanceRecordTest(unittest.TestCase):
    def test_record_has_all_keys(self):
        record = provenance.provenance_record(
            "github", "mem0ai/mem0", [{"url": "https://github.com/x"}],
            newest_item_age_hours=10, fetched_at="2026-07-23T00:00:00+00:00")
        self.assertEqual(set(record), RECORD_KEYS)
        self.assertEqual(record["source"], "github")
        self.assertEqual(record["query"], "mem0ai/mem0")
        self.assertEqual(record["items"], 1)
        self.assertEqual(record["fetched_at"], "2026-07-23T00:00:00+00:00")
        self.assertEqual(record["freshness_hours"], 10)
        self.assertEqual(record["web_index_reachable"], "yes")

    def test_fetched_at_defaults_to_now_iso(self):
        record = provenance.provenance_record("github", "q", [])
        self.assertIsInstance(record["fetched_at"], str)
        # ISO-8601 shape: date, time separator, no key material, parseable.
        self.assertIn("T", record["fetched_at"])

    def test_empty_items_record_still_built(self):
        record = provenance.provenance_record(
            "grok", "agent memory pain", [], newest_item_age_hours=3)
        self.assertEqual(record["items"], 0)
        self.assertIsNone(record["freshness_hours"])
        # No items → no freshness claim → no pre-index override either.
        self.assertEqual(record["web_index_reachable"], "partial")

    def test_unknown_age_freshness_none(self):
        record = provenance.provenance_record(
            "telegram", "q", [{"url": "https://t.me/x/1"}])
        self.assertIsNone(record["freshness_hours"])
        self.assertEqual(record["web_index_reachable"], "no")

    def test_fresh_grok_record_carries_override(self):
        record = provenance.provenance_record(
            "grok", "q", [{"url": "https://x.com/a/status/1"}],
            newest_item_age_hours=3)
        self.assertEqual(record["web_index_reachable"], "no")
        self.assertIn("not yet web-indexed", record["reason"])

    def test_items_count_accepted_directly(self):
        # The fire path may already hold a count instead of the item list.
        record = provenance.provenance_record(
            "hackernews", "q", 7, newest_item_age_hours=48)
        self.assertEqual(record["items"], 7)
        self.assertEqual(record["freshness_hours"], 48)


if __name__ == "__main__":
    unittest.main()

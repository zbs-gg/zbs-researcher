"""Freshness wiring: structural channels record their newest item's age so the
eval can score freshness honestly (was always "unknown" before). Covers the
pure helpers (_to_epoch / _note_ts) and run_connector's sink plumbing.
"""
import importlib.util
import sys
import threading
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dr = _load("deep_research_freshness", RUNNER)


class ToEpochTests(unittest.TestCase):
    def test_epoch_number_passthrough(self):
        self.assertEqual(dr._to_epoch(1_700_000_000), 1_700_000_000.0)
        self.assertEqual(dr._to_epoch(1_700_000_000.5), 1_700_000_000.5)

    def test_epoch_string(self):
        self.assertEqual(dr._to_epoch("1700000000"), 1_700_000_000.0)

    def test_iso_with_z(self):
        # 2026-01-01T00:00:00Z == 1767225600 UTC
        self.assertEqual(dr._to_epoch("2026-01-01T00:00:00Z"), 1767225600.0)

    def test_iso_with_offset(self):
        self.assertEqual(
            dr._to_epoch("2026-01-01T03:00:00+03:00"), 1767225600.0
        )

    def test_iso_naive_is_assumed_utc(self):
        self.assertEqual(dr._to_epoch("2026-01-01T00:00:00"), 1767225600.0)

    def test_none_and_garbage_are_none(self):
        self.assertIsNone(dr._to_epoch(None))
        self.assertIsNone(dr._to_epoch(""))
        self.assertIsNone(dr._to_epoch("   "))
        self.assertIsNone(dr._to_epoch("not-a-date"))
        self.assertIsNone(dr._to_epoch("2026-13-99"))  # impossible calendar


class NoteTsTests(unittest.TestCase):
    def test_none_sink_is_noop(self):
        # Must not raise — a channel with no sink passed still calls _note_ts.
        self.assertIsNone(dr._note_ts(None, 1_700_000_000))

    def test_appends_parsed_epoch(self):
        sink = []
        dr._note_ts(sink, "2026-01-01T00:00:00Z")
        self.assertEqual(sink, [1767225600.0])

    def test_drops_unparseable_never_zeroes(self):
        sink = []
        dr._note_ts(sink, None)
        dr._note_ts(sink, "garbage")
        dr._note_ts(sink, "")
        self.assertEqual(sink, [])  # a missing timestamp must not fake fresh=0

    def test_drops_future_timestamp(self):
        # A clock-skewed/hallucinated future item must not clamp to a fake 0h.
        sink = []
        dr._note_ts(sink, time.time() + 7200)  # 2h ahead -> dropped
        dr._note_ts(sink, time.time() - 60)    # 1min ago -> kept
        self.assertEqual(len(sink), 1)


class XSnowflakeTests(unittest.TestCase):
    # id 2080203643035525617 -> 2026-07-23 08:09 UTC (verified against grok out)
    KNOWN_ID = "2080203643035525617"
    KNOWN_EPOCH = ((int("2080203643035525617") >> 22) + 1288834974657) / 1000.0

    def test_decodes_status_url(self):
        sink = []
        dr._note_x_post_ages(
            sink, f"see https://x.com/rohit_jsfreaky/status/{self.KNOWN_ID} lol"
        )
        self.assertEqual(len(sink), 1)
        self.assertAlmostEqual(sink[0], self.KNOWN_EPOCH, delta=1.0)

    def test_twitter_com_host_too(self):
        sink = []
        dr._note_x_post_ages(sink, f"https://twitter.com/x/status/{self.KNOWN_ID}")
        self.assertEqual(len(sink), 1)

    def test_multiple_ids_all_recorded(self):
        sink = []
        text = (
            f"https://x.com/a/status/{self.KNOWN_ID} and "
            f"https://x.com/b/status/2079846795803562041"
        )
        dr._note_x_post_ages(sink, text)
        self.assertEqual(len(sink), 2)

    def test_none_sink_and_empty_text_are_noops(self):
        self.assertIsNone(dr._note_x_post_ages(None, "https://x.com/a/status/123456"))
        sink = []
        dr._note_x_post_ages(sink, "")
        dr._note_x_post_ages(sink, None)
        self.assertEqual(sink, [])

    def test_absurd_ids_dropped(self):
        sink = []
        # id=1 decodes to the 2010 epoch (before any real post) -> dropped;
        # a 25-digit id decodes far in the future -> dropped.
        dr._note_x_post_ages(sink, "https://x.com/a/status/1")
        dr._note_x_post_ages(sink, "https://x.com/a/status/9999999999999999999999999")
        self.assertEqual(sink, [])

    @staticmethod
    def _id_for_epoch(epoch_s):
        ms = int(epoch_s * 1000) - 1288834974657
        return str(ms << 22)

    def test_near_future_id_dropped_not_faking_zero(self):
        # A hallucinated/future post 2h ahead must be DROPPED, never clamped to
        # a fake 0h "posted now" (the honesty invariant / review finding 1).
        sink = []
        future_id = self._id_for_epoch(time.time() + 7200)
        dr._note_x_post_ages(sink, f"https://x.com/a/status/{future_id}")
        self.assertEqual(sink, [])

    def test_recent_past_id_kept(self):
        sink = []
        recent_id = self._id_for_epoch(time.time() - 3600)  # 1h ago, real
        dr._note_x_post_ages(sink, f"https://x.com/a/status/{recent_id}")
        self.assertEqual(len(sink), 1)

    def test_non_status_x_links_ignored(self):
        sink = []
        dr._note_x_post_ages(sink, "https://x.com/someprofile and https://x.com/i/lists/5")
        self.assertEqual(sink, [])


class RunConnectorFreshnessTests(unittest.TestCase):
    def _manifest(self):
        return {"channels": {}, "connectors_skipped": {}}

    def _run(self, fn, name="fake"):
        conn = dr.Connector(name, "direct", fn, "test source", [])
        manifest = self._manifest()
        tmp = Path(self._tmp.name)
        # OUTPUT_NAMES must know the connector — register a temp entry.
        dr.OUTPUT_NAMES.setdefault(name, f"{name}.md")
        dr.run_connector(conn, "q", tmp, 5, manifest, threading.Lock(), announce=False)
        return manifest["channels"][name]

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_records_newest_age_from_sink(self):
        newest = time.time() - 3600.0  # 1h ago
        older = time.time() - 10 * 3600.0  # 10h ago

        def fn(query, out_path, max_items, freshness_sink=None):
            dr._note_ts(freshness_sink, older)
            dr._note_ts(freshness_sink, newest)  # newest wins (max epoch)
            out_path.write_text("ok")
            return 2

        rec = self._run(fn, "fake_fresh")
        self.assertEqual(rec["status"], "ok")
        self.assertIn("newest_item_age_hours", rec)
        # newest is ~1h old, not ~10h — the max epoch is chosen.
        self.assertAlmostEqual(rec["newest_item_age_hours"], 1.0, delta=0.2)

    def test_no_param_means_no_age_key(self):
        def fn(query, out_path, max_items):  # no freshness_sink at all
            out_path.write_text("ok")
            return 1

        rec = self._run(fn, "fake_noparam")
        self.assertEqual(rec["status"], "ok")
        self.assertNotIn("newest_item_age_hours", rec)

    def test_empty_sink_means_no_age_key(self):
        def fn(query, out_path, max_items, freshness_sink=None):
            out_path.write_text("ok")  # accepts the sink but records nothing
            return 0

        rec = self._run(fn, "fake_empty")
        self.assertEqual(rec["status"], "ok")
        self.assertNotIn("newest_item_age_hours", rec)


class RunConnectorEvidenceSinkTests(RunConnectorFreshnessTests):
    """The evidence sink is what turns "we transcribed this ourselves" into a
    coverage receipt, so its wiring needs the same guarantees as freshness."""

    def test_marker_records_the_self_sourced_count(self):
        def fn(query, out_path, max_items, evidence_sink=None):
            evidence_sink.append("self-transcribed:a")
            evidence_sink.append("self-transcribed:b")
            out_path.write_text("ok")
            return 2

        rec = self._run(fn, "fake_evidence")
        self.assertEqual(rec["status"], "ok")
        self.assertTrue(rec["self_sourced"])
        # the COUNT, not just a flag — provenance needs it to avoid
        # relabelling rows a web index can read
        self.assertEqual(rec["self_sourced_items"], 2)

    def test_connector_without_the_parameter_never_claims_it(self):
        def fn(query, out_path, max_items):  # no evidence_sink at all
            out_path.write_text("ok")
            return 1

        rec = self._run(fn, "fake_no_evidence")
        self.assertEqual(rec["status"], "ok")
        self.assertNotIn("self_sourced", rec)

    def test_untouched_sink_never_claims_it(self):
        def fn(query, out_path, max_items, evidence_sink=None):
            out_path.write_text("ok")  # accepts the sink, produces nothing
            return 3

        rec = self._run(fn, "fake_evidence_empty")
        self.assertEqual(rec["status"], "ok")
        self.assertNotIn("self_sourced", rec)

    def test_both_sinks_can_be_requested_together(self):
        def fn(query, out_path, max_items, freshness_sink=None,
               evidence_sink=None):
            dr._note_ts(freshness_sink, time.time() - 3600.0)
            evidence_sink.append("self-transcribed:a")
            out_path.write_text("ok")
            return 1

        rec = self._run(fn, "fake_both_sinks")
        self.assertIn("newest_item_age_hours", rec)
        self.assertEqual(rec["self_sourced_items"], 1)


if __name__ == "__main__":
    unittest.main()

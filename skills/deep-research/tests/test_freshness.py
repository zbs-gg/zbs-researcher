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


if __name__ == "__main__":
    unittest.main()

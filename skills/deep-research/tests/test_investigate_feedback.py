"""U4/U5 — investigate feedback ledger + Cartographer soft-plug.

record_feedback appends one honest JSON line per run (O_APPEND single-write,
loud OSError on failure); read_recent replays the last rows for a topic
newest-first; the optional Cartographer relay is HTTPS-only, failure-tolerant,
and never undoes the local write. detect_state surfaces relay availability as
a boolean + one honest doctor line that never claims the baseline learns.

All network is mocked — no live calls, no paid calls.
"""
import contextlib
import importlib.util
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FEEDBACK = SCRIPTS / "investigate_feedback.py"
DETECT = SCRIPTS / "detect_state.py"

_scripts_path = str(SCRIPTS)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


investigate_feedback = _load("investigate_feedback_u4", FEEDBACK)
detect_state = _load("detect_state_u5", DETECT)


# Env vars that change where feedback lands, whether Cartographer is contacted,
# and which providers detect_state reports. Tests clear all of them so the host
# machine's real configuration can never leak into (or satisfy) an assertion.
FEEDBACK_ENV_VARS = (
    "DEEP_RESEARCH_CARTOGRAPHER_URL",
    "DEEP_RESEARCH_NOTIFY_URL",
    "DEEP_RESEARCH_PROFILE",
    "DEEP_RESEARCH_SECRETS_DIR",
)

KEY_ENV_VARS = (
    "GEMINI_API_KEY",
    "GROK_API_KEY",
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
    "SCRAPECREATORS_KEY",
    "BRAVE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "THREADS_ACCESS_TOKEN",
)


@contextlib.contextmanager
def feedback_environment(secrets_dir=None, **overrides):
    with mock.patch.dict(os.environ):
        for name in FEEDBACK_ENV_VARS + KEY_ENV_VARS:
            os.environ.pop(name, None)
        if secrets_dir is not None:
            os.environ["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets_dir)
        os.environ.update(overrides)
        yield


class RecordAndReadTests(unittest.TestCase):
    def test_round_trip_record_then_read_recent(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp) / "nested" / "secrets"
            result = investigate_feedback.record_feedback(
                "ai memory",
                composed_queries={"github-issues": "mem0ai/mem0"},
                sources_used=["github-issues", "grok"],
                human_feedback="more reddit next time",
                coverage={"web_unreachable": 2, "total": 3},
                base_dir=base,
            )
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        self.assertTrue(result.logged)
        self.assertFalse(result.notified)
        self.assertIsNone(result.error)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["topic"], "ai memory")
        self.assertEqual(row["composed_queries"], {"github-issues": "mem0ai/mem0"})
        self.assertEqual(row["sources_used"], ["github-issues", "grok"])
        self.assertEqual(row["human_feedback"], "more reddit next time")
        self.assertEqual(row["coverage"], {"web_unreachable": 2, "total": 3})
        # ts must be parseable ISO8601
        datetime.fromisoformat(row["ts"])

    def test_topic_filter_excludes_other_topics(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp)
            investigate_feedback.record_feedback("ai memory", base_dir=base)
            investigate_feedback.record_feedback("vector dbs", base_dir=base)
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        self.assertEqual([row["topic"] for row in rows], ["ai memory"])

    def test_read_recent_returns_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp)
            for note in ("first", "second", "third"):
                investigate_feedback.record_feedback(
                    "ai memory", human_feedback=note, base_dir=base
                )
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        self.assertEqual(
            [row["human_feedback"] for row in rows], ["third", "second", "first"]
        )

    def test_read_recent_caps_at_last_n(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp)
            for index in range(5):
                investigate_feedback.record_feedback(
                    "ai memory", human_feedback=f"note-{index}", base_dir=base
                )
            rows = investigate_feedback.read_recent("ai memory", n=2, base_dir=base)

        self.assertEqual([row["human_feedback"] for row in rows], ["note-4", "note-3"])

    def test_missing_or_empty_ledger_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp)
            self.assertEqual(investigate_feedback.read_recent("ai memory", base_dir=base), [])
            (base / investigate_feedback.FEEDBACK_FILENAME).write_text("", encoding="utf-8")
            self.assertEqual(investigate_feedback.read_recent("ai memory", base_dir=base), [])

    def test_malformed_line_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp)
            investigate_feedback.record_feedback("ai memory", human_feedback="good", base_dir=base)
            ledger = base / investigate_feedback.FEEDBACK_FILENAME
            with ledger.open("a", encoding="utf-8") as handle:
                handle.write("{half-written garbage\n")
                handle.write('"a bare string, not a row"\n')
            investigate_feedback.record_feedback("ai memory", human_feedback="also good", base_dir=base)
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        self.assertEqual([row["human_feedback"] for row in rows], ["also good", "good"])

    def test_unwritable_base_dir_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            blocked = Path(tmp) / "blocked"
            blocked.write_text("", encoding="utf-8")  # a FILE where a dir must go
            with self.assertRaises(OSError) as ctx:
                investigate_feedback.record_feedback("ai memory", base_dir=blocked)

        self.assertIn("investigate feedback", str(ctx.exception))

    def test_blank_topic_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp)
            for topic in ("", "   ", None, 42):
                with self.subTest(topic=topic):
                    with self.assertRaises(ValueError):
                        investigate_feedback.record_feedback(topic, base_dir=base)
            self.assertFalse((base / investigate_feedback.FEEDBACK_FILENAME).exists())


class RelayTests(unittest.TestCase):
    def test_relay_success_claims_notified(self):
        calls = []

        def sender(url, payload):
            calls.append((url, payload))
            return 200

        with tempfile.TemporaryDirectory() as tmp, feedback_environment(
            DEEP_RESEARCH_CARTOGRAPHER_URL="https://cartographer.invalid/ingest"
        ):
            base = Path(tmp)
            result = investigate_feedback.record_feedback(
                "ai memory", human_feedback="great run", base_dir=base, sender=sender
            )
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        self.assertTrue(result.logged)
        self.assertTrue(result.notified)
        self.assertIsNone(result.error)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "https://cartographer.invalid/ingest")
        import json

        payload = json.loads(calls[0][1].decode("utf-8"))
        self.assertEqual(payload["topic"], "ai memory")
        self.assertEqual(payload["human_feedback"], "great run")

    def test_relay_failure_keeps_local_line_and_reports_not_notified(self):
        def raising_sender(url, payload):
            raise urllib.error.URLError("connection refused")

        def http_500_sender(url, payload):
            return 500

        for label, sender in (("raises", raising_sender), ("http-500", http_500_sender)):
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmp, feedback_environment(
                    DEEP_RESEARCH_CARTOGRAPHER_URL="https://cartographer.invalid/ingest"
                ):
                    base = Path(tmp)
                    result = investigate_feedback.record_feedback(
                        "ai memory", base_dir=base, sender=sender
                    )
                    rows = investigate_feedback.read_recent("ai memory", base_dir=base)

                self.assertTrue(result.logged)
                self.assertFalse(result.notified)
                self.assertTrue(result.error)
                self.assertEqual(len(rows), 1)
                # A relay URL may carry a token — the error must never echo it.
                self.assertNotIn("cartographer.invalid", result.error)

    def test_no_relay_url_never_calls_sender(self):
        sender = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp, feedback_environment():
            base = Path(tmp)
            result = investigate_feedback.record_feedback(
                "ai memory", base_dir=base, sender=sender
            )
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        sender.assert_not_called()
        self.assertTrue(result.logged)
        self.assertFalse(result.notified)
        self.assertIsNone(result.error)
        self.assertEqual(len(rows), 1)

    def test_non_https_relay_url_is_never_sent(self):
        sender = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp, feedback_environment(
            DEEP_RESEARCH_CARTOGRAPHER_URL="http://cartographer.invalid/ingest"
        ):
            base = Path(tmp)
            result = investigate_feedback.record_feedback(
                "ai memory", base_dir=base, sender=sender
            )
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        sender.assert_not_called()
        self.assertTrue(result.logged)
        self.assertFalse(result.notified)
        self.assertIn("https", result.error)
        self.assertEqual(len(rows), 1)

    def test_malformed_relay_url_degrades_without_raising(self):
        # Review regression: a bracket-malformed URL makes urllib.urlsplit raise
        # ValueError. record_feedback must save the note and degrade the relay to
        # a clean not-notified result — never propagate the exception.
        sender = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp, feedback_environment(
            DEEP_RESEARCH_CARTOGRAPHER_URL="https://["
        ):
            base = Path(tmp)
            result = investigate_feedback.record_feedback(
                "ai memory", base_dir=base, sender=sender
            )
            rows = investigate_feedback.read_recent("ai memory", base_dir=base)

        sender.assert_not_called()
        self.assertTrue(result.logged)        # rule 3: the note is never lost
        self.assertFalse(result.notified)
        self.assertIsNotNone(result.error)    # honest skip reason, not a crash
        self.assertEqual(len(rows), 1)


class FeedbackMessageTests(unittest.TestCase):
    def test_message_claims_relay_only_when_actually_relayed(self):
        relayed = investigate_feedback.feedback_message(notified=True)
        local_only = investigate_feedback.feedback_message(notified=False)

        self.assertIn("inform the next run on this topic", relayed)
        self.assertIn("relayed to Cartographer", relayed)
        self.assertIn("inform the next run on this topic", local_only)
        self.assertNotIn("relayed to Cartographer", local_only)

    def test_message_never_claims_learning(self):
        for notified in (True, False):
            with self.subTest(notified=notified):
                message = investigate_feedback.feedback_message(notified=notified)
                self.assertNotIn("learn", message.lower())


class CartographerStateTests(unittest.TestCase):
    def test_collect_state_reports_cartographer_configured(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment(
            tmp, DEEP_RESEARCH_CARTOGRAPHER_URL="https://cartographer.invalid/ingest"
        ):
            state = detect_state.collect_state()

        self.assertTrue(state["cartographer"])

    def test_collect_state_cartographer_absent_or_non_https_is_false(self):
        for overrides in (
            {},
            {"DEEP_RESEARCH_CARTOGRAPHER_URL": "http://cartographer.invalid/ingest"},
            {"DEEP_RESEARCH_CARTOGRAPHER_URL": "   "},
        ):
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as tmp:
                with feedback_environment(tmp, **overrides):
                    state = detect_state.collect_state()

                self.assertFalse(state["cartographer"])

    def test_doctor_report_soft_plug_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment(
            tmp, DEEP_RESEARCH_CARTOGRAPHER_URL="https://cartographer.invalid/ingest"
        ):
            report = detect_state.doctor_report()

        self.assertIn("cartographer", report)
        self.assertIn("relay on", report)
        self.assertIn("compounding across runs", report)
        self.assertNotIn("not connected", report)
        self.assertNotIn("learn", report.lower())

    def test_doctor_report_soft_plug_when_not_connected(self):
        with tempfile.TemporaryDirectory() as tmp, feedback_environment(tmp):
            report = detect_state.doctor_report()

        self.assertIn("cartographer", report)
        self.assertIn("not connected", report)
        self.assertIn("connect Cartographer (neighboring product)", report)
        self.assertIn("compound your research profile across runs", report)
        self.assertNotIn("relay on", report)
        self.assertNotIn("learn", report.lower())

    def test_feedback_source_avoids_posix_only_calls(self):
        source = FEEDBACK.read_text(encoding="utf-8")
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid", "pwd.", "grp."):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

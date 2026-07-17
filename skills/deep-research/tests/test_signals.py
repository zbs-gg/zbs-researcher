import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    import signals

    SPEC = importlib.util.spec_from_file_location("deep_research_signal_cli", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
finally:
    if path_added:
        sys.path.remove(scripts_path)


# Env vars that change where signals land, whether a webhook is contacted, and
# what profile gets recorded. Tests clear all of them so the host machine's real
# configuration can never leak into (or accidentally satisfy) an assertion.
SIGNAL_ENV_VARS = (
    "DEEP_RESEARCH_NOTIFY_URL",
    "DEEP_RESEARCH_PROFILE",
    "DEEP_RESEARCH_SECRETS_DIR",
)

# Provider keys stripped from subprocess runs so no real key can appear in
# output even by accident.
KEY_ENV_VARS = (
    "GEMINI_API_KEY",
    "GROK_API_KEY",
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
    "SCRAPECREATORS_KEY",
    "BRAVE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
)


@contextlib.contextmanager
def signal_environment(secrets_dir=None, **overrides):
    with mock.patch.dict(os.environ):
        for name in SIGNAL_ENV_VARS:
            os.environ.pop(name, None)
        if secrets_dir is not None:
            os.environ["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets_dir)
        os.environ.update(overrides)
        yield


def read_jsonl(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


class RecordSignalTests(unittest.TestCase):
    def test_first_signal_creates_file_with_one_json_line(self):
        with tempfile.TemporaryDirectory() as tmp, signal_environment():
            base = Path(tmp) / "nested" / "secrets"
            result = signals.record_signal(
                "want-paid", tier_context="tier-1", profile="client", base_dir=base
            )

            ledger = base / "demand-signals.jsonl"
            self.assertTrue(ledger.is_file())
            entries = read_jsonl(ledger)

        self.assertTrue(result.logged)
        self.assertFalse(result.notified)
        self.assertIsNone(result.error)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["kind"], "want-paid")
        self.assertEqual(entry["tier_context"], "tier-1")
        self.assertEqual(entry["profile"], "client")
        # ts must be parseable ISO8601
        datetime.fromisoformat(entry["ts"])

    def test_signals_append_rather_than_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, signal_environment():
            base = Path(tmp)
            signals.record_signal("want-paid", base_dir=base)
            signals.record_signal("host-for-me", base_dir=base)
            entries = read_jsonl(base / "demand-signals.jsonl")

        self.assertEqual([e["kind"] for e in entries], ["want-paid", "host-for-me"])

    def test_invalid_kind_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp, signal_environment():
            base = Path(tmp)
            with self.assertRaises(ValueError):
                signals.record_signal("gimme-money", base_dir=base)
            self.assertFalse((base / "demand-signals.jsonl").exists())

    def test_unwritable_base_dir_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp, signal_environment():
            blocked = Path(tmp) / "blocked"
            blocked.write_text("", encoding="utf-8")  # a FILE where a dir must go
            with self.assertRaises(OSError) as ctx:
                signals.record_signal("want-paid", base_dir=blocked)

        self.assertIn("demand signal", str(ctx.exception))


class NotifyTests(unittest.TestCase):
    def test_host_for_me_with_successful_sender_claims_notified(self):
        calls = []

        def sender(url, payload):
            calls.append((url, payload))
            return 200

        with tempfile.TemporaryDirectory() as tmp, signal_environment(
            DEEP_RESEARCH_NOTIFY_URL="https://relay.invalid/hook"
        ):
            base = Path(tmp)
            result = signals.record_signal("host-for-me", base_dir=base, sender=sender)
            entries = read_jsonl(base / "demand-signals.jsonl")

        self.assertTrue(result.logged)
        self.assertTrue(result.notified)
        self.assertIsNone(result.error)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "https://relay.invalid/hook")
        self.assertEqual(json.loads(calls[0][1].decode("utf-8"))["kind"], "host-for-me")

        message = signals.signal_message("host-for-me", result.notified)
        self.assertIn("Nik was notified", message)

    def test_no_notify_url_never_calls_sender(self):
        sender = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp, signal_environment():
            base = Path(tmp)
            result = signals.record_signal("host-for-me", base_dir=base, sender=sender)
            entries = read_jsonl(base / "demand-signals.jsonl")

        sender.assert_not_called()
        self.assertTrue(result.logged)
        self.assertFalse(result.notified)
        self.assertEqual(len(entries), 1)

        message = signals.signal_message("host-for-me", result.notified)
        self.assertIn("recorded locally", message)
        self.assertNotIn("Nik was notified", message)

    def test_notify_failure_keeps_local_line_and_reports_not_notified(self):
        def raising_sender(url, payload):
            raise urllib.error.URLError("connection refused")

        def http_500_sender(url, payload):
            return 500

        for label, sender in (("raises", raising_sender), ("http-500", http_500_sender)):
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmp, signal_environment(
                    DEEP_RESEARCH_NOTIFY_URL="https://relay.invalid/hook"
                ):
                    base = Path(tmp)
                    result = signals.record_signal(
                        "host-for-me", base_dir=base, sender=sender
                    )
                    entries = read_jsonl(base / "demand-signals.jsonl")

                self.assertTrue(result.logged)
                self.assertFalse(result.notified)
                self.assertTrue(result.error)
                self.assertEqual(len(entries), 1)
                message = signals.signal_message("host-for-me", result.notified)
                self.assertNotIn("Nik was notified", message)

    def test_non_https_notify_url_is_never_sent(self):
        sender = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp, signal_environment(
            DEEP_RESEARCH_NOTIFY_URL="http://relay.invalid/hook"
        ):
            base = Path(tmp)
            result = signals.record_signal("want-paid", base_dir=base, sender=sender)
            entries = read_jsonl(base / "demand-signals.jsonl")

        sender.assert_not_called()
        self.assertTrue(result.logged)
        self.assertFalse(result.notified)
        self.assertIn("https", result.error)
        self.assertEqual(len(entries), 1)


class SignalMessageTests(unittest.TestCase):
    def test_want_paid_local_only_copy_is_honest(self):
        message = signals.signal_message("want-paid", notified=False)
        self.assertIn("recorded locally", message)
        self.assertNotIn("Nik was notified", message)

    def test_host_for_me_never_claims_provisioning(self):
        for notified in (True, False):
            with self.subTest(notified=notified):
                message = signals.signal_message("host-for-me", notified=notified)
                # never auto-mint: the copy must say nothing was set up/billed
                self.assertIn("Nothing has been provisioned or billed", message)

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            signals.signal_message("gimme-money", notified=False)


class SignalCliTests(unittest.TestCase):
    def run_main(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", [str(RUNNER), *map(str, args)]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                deep_research.main()
        return stdout.getvalue(), stderr.getvalue()

    def test_cli_records_signal_and_prints_honest_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp).resolve()
            with signal_environment(secrets, DEEP_RESEARCH_PROFILE="operator"):
                stdout, _ = self.run_main("--signal", "want-paid")
            entries = read_jsonl(secrets / "demand-signals.jsonl")

        self.assertIn("recorded locally", stdout)
        self.assertNotIn("Nik was notified", stdout)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "want-paid")
        self.assertEqual(entries[0]["profile"], "operator")

    def test_cli_invalid_kind_exits_nonzero_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp).resolve()
            with signal_environment(secrets):
                with self.assertRaises(SystemExit) as ctx:
                    self.run_main("--signal", "gimme-money")
            self.assertFalse((secrets / "demand-signals.jsonl").exists())
        self.assertNotEqual(ctx.exception.code, 0)

    def test_cli_unwritable_secrets_dir_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp).resolve() / "blocked"
            blocked.write_text("", encoding="utf-8")
            with signal_environment(blocked):
                with self.assertRaises(SystemExit) as ctx:
                    self.run_main("--signal", "want-paid")
        self.assertNotEqual(ctx.exception.code, 0)

    def test_cli_signal_is_mutually_exclusive_with_other_modes(self):
        for extra in (("--diagnose",), ("--list-connectors",), ("--allocate-run",)):
            with self.subTest(extra=extra):
                with self.assertRaises(SystemExit):
                    self.run_main("--signal", "want-paid", *extra)

    def test_cli_subprocess_emits_no_key_material(self):
        env_secret = "AIzaSignalSecretDoNotPrint555"
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp).resolve()

            env = os.environ.copy()
            for name in SIGNAL_ENV_VARS + KEY_ENV_VARS:
                env.pop(name, None)
            env["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets)
            env["GEMINI_API_KEY"] = env_secret

            result = subprocess.run(
                [sys.executable, str(RUNNER), "--signal", "want-paid"],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            entries = read_jsonl(secrets / "demand-signals.jsonl")

        self.assertEqual(result.returncode, 0, result.stderr)
        combined = result.stdout + result.stderr
        self.assertNotIn(env_secret, combined)
        self.assertIn("recorded locally", result.stdout)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "want-paid")
        self.assertEqual(entries[0]["profile"], "client")

    def test_signals_source_avoids_posix_only_calls(self):
        source = (SCRIPTS / "signals.py").read_text(encoding="utf-8")
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid", "pwd.", "grp."):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

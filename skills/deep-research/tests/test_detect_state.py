import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"
DETECT = SCRIPTS / "detect_state.py"
REPO_ROOT = Path(__file__).resolve().parents[3]

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    import detect_state

    SPEC = importlib.util.spec_from_file_location("deep_research_diagnose_cli", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
finally:
    if path_added:
        sys.path.remove(scripts_path)


# Every env var the state detector may treat as a live credential or profile
# switch. Tests clear all of them so the host machine's real keys can never
# leak into (or accidentally satisfy) an assertion.
STATE_ENV_VARS = (
    "GEMINI_API_KEY",
    "GROK_API_KEY",
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
    "SCRAPECREATORS_KEY",
    "BRAVE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "THREADS_ACCESS_TOKEN",
    "DEEP_RESEARCH_PROFILE",
)


@contextlib.contextmanager
def isolated_environment(secrets_dir, **overrides):
    with mock.patch.dict(os.environ):
        for name in STATE_ENV_VARS:
            os.environ.pop(name, None)
        os.environ["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets_dir)
        os.environ.update(overrides)
        yield


class DetectStateTests(unittest.TestCase):
    def test_empty_secrets_and_env_reports_everything_absent(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_environment(tmp):
            state = detect_state.collect_state()

        self.assertEqual(
            state,
            {
                "providers": {
                    "gemini": False,
                    "grok": False,
                    "perplexity": False,
                    "openrouter": False,
                    "scrapecreators": False,
                    "groq": False,
                    "threads": False,
                },
                "telegram_session": False,
                "profile": "client",
                "wizard_done": False,
                "tier": None,
            },
        )

    def test_env_keys_mark_providers_configured_at_call_time(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_environment(
            tmp,
            GEMINI_API_KEY="AIzaFakeForTest123",
            OPENROUTER_API_KEY="sk-or-fake-test-123",
            GROQ_API_KEY="gsk_faketest123",
        ):
            state = detect_state.collect_state()

        self.assertTrue(state["providers"]["gemini"])
        self.assertTrue(state["providers"]["openrouter"])
        self.assertTrue(state["providers"]["groq"])
        self.assertFalse(state["providers"]["grok"])
        self.assertFalse(state["providers"]["perplexity"])
        self.assertFalse(state["providers"]["scrapecreators"])

    def test_secrets_dir_override_serves_key_files_session_and_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp).resolve()
            (secrets / "gemini-key.txt").write_text("AIzaFakeFromFile42\n", encoding="utf-8")
            (secrets / "collector.session").write_text("", encoding="utf-8")
            (secrets / "onboarding.json").write_text(
                json.dumps({"wizard_done": True, "tier": "0"}), encoding="utf-8"
            )

            with isolated_environment(secrets, DEEP_RESEARCH_PROFILE="operator"):
                state = detect_state.collect_state()

        self.assertTrue(state["providers"]["gemini"])
        self.assertTrue(state["telegram_session"])
        self.assertTrue(state["wizard_done"])
        self.assertEqual(state["tier"], "0")
        self.assertEqual(state["profile"], "operator")

    def test_malformed_onboarding_marker_is_treated_as_absent(self):
        cases = (
            "{not json at all",
            "[1, 2, 3]",
            json.dumps({"wizard_done": "yes", "tier": {}}),
            "",
        )
        for raw in cases:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                secrets = Path(tmp).resolve()
                (secrets / "onboarding.json").write_text(raw, encoding="utf-8")

                with isolated_environment(secrets):
                    state = detect_state.collect_state()

                self.assertFalse(state["wizard_done"])
                self.assertIsNone(state["tier"])

    def test_cli_emits_valid_json_without_key_material(self):
        env_secret = "AIzaSuperSecretDoNotPrint987"
        file_secret = "xai-FileSecretNoPrint7"  # short: under the selftest secret-scan floor
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp).resolve()
            (secrets / "grok-api-key.txt").write_text(file_secret + "\n", encoding="utf-8")

            env = os.environ.copy()
            for name in STATE_ENV_VARS:
                env.pop(name, None)
            env["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets)
            env["GEMINI_API_KEY"] = env_secret

            result = subprocess.run(
                [sys.executable, str(DETECT)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout)
        self.assertTrue(state["providers"]["gemini"])
        self.assertTrue(state["providers"]["grok"])
        combined = result.stdout + result.stderr
        self.assertNotIn(env_secret, combined)
        self.assertNotIn(file_secret, combined)

    def test_non_utf8_key_file_degrades_to_absent_state_no_crash(self):
        # The SessionStart hook must never crash the session. A non-UTF-8
        # *-key.txt (read_key does a plain read_text) would otherwise raise
        # UnicodeDecodeError; main() catches it and emits the absent shape.
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp).resolve()
            (secrets / "gemini-key.txt").write_bytes(b"\xff\xfe\x00\x80not-utf8")

            env = os.environ.copy()
            for name in STATE_ENV_VARS:
                env.pop(name, None)
            env["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets)

            result = subprocess.run(
                [sys.executable, str(DETECT)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout)
        self.assertFalse(any(state["providers"].values()))
        self.assertFalse(state["wizard_done"])
        self.assertEqual(state["profile"], "client")

    def test_detector_source_avoids_posix_only_calls(self):
        source = DETECT.read_text(encoding="utf-8")
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid", "pwd.", "grp."):
            self.assertNotIn(token, source)


class DiagnoseCliTests(unittest.TestCase):
    def run_main(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", [str(RUNNER), *map(str, args)]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                deep_research.main()
        return stdout.getvalue(), stderr.getvalue()

    def test_diagnose_prints_offline_doctor_report_without_allocating(self):
        secret_value = "AIzaDoctorSecret321"
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            secrets = launch_cwd / "secrets"
            secrets.mkdir()

            with isolated_environment(secrets, GEMINI_API_KEY=secret_value):
                with mock.patch.object(deep_research.Path, "cwd", return_value=launch_cwd):
                    stdout, _ = self.run_main("--diagnose")

            self.assertIn("gemini", stdout)
            self.assertIn("configured", stdout)
            self.assertIn("missing", stdout)
            self.assertIn(str(secrets), stdout)
            self.assertIn("client", stdout)
            self.assertNotIn(secret_value, stdout)
            self.assertFalse((launch_cwd / "research").exists())

    def test_diagnose_is_mutually_exclusive_with_other_modes(self):
        for extra in (("--list-connectors",), ("--allocate-run",)):
            with self.subTest(extra=extra):
                with self.assertRaises(SystemExit):
                    self.run_main("--diagnose", *extra)


class HookWiringTests(unittest.TestCase):
    def test_plugin_hooks_wire_session_start_to_detect_state(self):
        hooks = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        entries = hooks["hooks"]["SessionStart"]
        commands = [hook["command"] for entry in entries for hook in entry["hooks"]]

        self.assertTrue(
            any(
                "detect_state.py" in command and "${CLAUDE_PLUGIN_ROOT}" in command
                for command in commands
            ),
            commands,
        )

    def test_plugin_manifest_declares_the_hooks_file(self):
        plugin = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(plugin["hooks"], "./hooks/hooks.json")


if __name__ == "__main__":
    unittest.main()

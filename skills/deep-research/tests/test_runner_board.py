"""U2 — runner wiring: banner + live board, byte-compatible plain path (R4/R5/R11).

The keystone is the plain-tier golden characterization test: it was captured
against the runner BEFORE any term_ui wiring and must stay green unmodified
after the wiring lands — that is the R11 byte-compatibility proof.

Determinism recipe (per the plan's U2 execution note):
  * connectors are faked via registry patching (one fast OK, one ERROR, one
    SKIPPED missing-key) — no network, fixed file contents, stable sizes;
  * ``time.time`` is fixed (dt is always 0.0);
  * the run directory is substituted with a placeholder before comparison;
  * per-channel completion lines are compared as a sorted set (thread
    completion order is nondeterministic); header/footer stay positional;
  * every UI-affecting env var is stripped, and KEYS is emptied, so the host
    terminal/secrets can never leak into an assertion.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import threading
import time as real_time
import types
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
    SPEC = importlib.util.spec_from_file_location("deep_research_runner_board", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import term_ui
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "demo topic"

# Every env var the capability detector or size probe may read (mirrors
# test_term_ui) — stripped for each run so host state never leaks in.
UI_ENV_VARS = ("NO_COLOR", "FORCE_COLOR", "CI", "TERM", "WT_SESSION", "COLUMNS", "LINES")


# ---------------------------------------------------------------------------
# Fixture connectors: one fast OK, one ERROR, one SKIPPED (missing key)
# ---------------------------------------------------------------------------
def _ok_channel(query, out_path, max_items):
    out_path.write_text("alpha report\n")
    return 3


def _err_channel(query, out_path, max_items):
    raise RuntimeError("boom failed")


def _never_channel(query, out_path, max_items):
    raise AssertionError("skipped connector must never run")


def _slow_err_channel(query, out_path, max_items):
    real_time.sleep(0.3)  # long enough for several ~10fps board frames
    raise RuntimeError("boom failed")


def make_registry(err_fn=_err_channel):
    Connector = deep_research.Connector
    return {
        c.name: c
        for c in [
            Connector("alpha", "direct", _ok_channel, "fake ok", []),
            Connector("boom", "direct", err_fn, "fake error", []),
            Connector("keyless", "direct", _never_channel, "fake skip", ["nokey"]),
        ]
    }


OUTPUT_NAMES = {"alpha": "alpha.md", "boom": "boom.md", "keyless": "keyless.md"}


def fixed_time():
    """The runner module's ``time`` with a frozen clock (dt is always 0.0)."""
    return types.SimpleNamespace(
        time=lambda: 1000.0,
        strftime=real_time.strftime,
        gmtime=real_time.gmtime,
        sleep=real_time.sleep,
    )


class FakeTTY(io.StringIO):
    """A stderr stand-in that claims to be a real terminal."""

    def isatty(self):
        return True

    def fileno(self):
        return 77  # unprobeable on purpose; size comes from COLUMNS/LINES


@contextlib.contextmanager
def patched_runner(registry, env=None):
    with mock.patch.dict(os.environ):
        for name in UI_ENV_VARS:
            os.environ.pop(name, None)
        if env:
            os.environ.update(env)
        with mock.patch.object(deep_research, "CONNECTORS", registry), \
             mock.patch.object(deep_research, "OUTPUT_NAMES", dict(OUTPUT_NAMES)), \
             mock.patch.object(deep_research, "KEYS", {}), \
             mock.patch.object(deep_research, "time", fixed_time()):
            yield


def run_topic(tmp, stderr, extra_args=()):
    """Invoke main() for the fixture topic; returns the resolved run dir."""
    out_dir = Path(tmp).resolve() / "run"
    argv = [str(RUNNER), TOPIC, "--output-dir", str(out_dir), *extra_args]
    with mock.patch.object(sys, "argv", argv), \
         contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(stderr):
        deep_research.main()
    return out_dir


# ---------------------------------------------------------------------------
# Golden characterization — plain tier stays byte-compatible (R11 keystone)
# ---------------------------------------------------------------------------
# Captured from the UNMODIFIED runner (pre-term_ui wiring) under the recipe
# above. Header and footer are positional; the completion block is a sorted
# set because connector threads finish in nondeterministic order.
GOLDEN_HEADER = ["[keyless] SKIP — missing keys: ['nokey']"]
GOLDEN_COMPLETIONS = sorted(
    [
        "[alpha] OK 0.0s (3)",
        "[boom] ERROR: boom failed",
    ]
)
GOLDEN_FOOTER = [
    "",
    "All channels done. Output: OUT_DIR",
    "  _topic.txt: 11 bytes",
    "  alpha.md: 13 bytes",
    "  boom.ERROR.md: 18 bytes",
    "  manifest.json: 410 bytes",
]


def split_golden(raw, out_dir):
    """Normalize a captured stderr into (header, sorted completions, footer)."""
    text = raw.replace(str(out_dir), "OUT_DIR")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # trailing newline of the last print
    blank = lines.index("")
    header = lines[: len(GOLDEN_HEADER)]
    completions = sorted(lines[len(GOLDEN_HEADER) : blank])
    footer = lines[blank:]
    return header, completions, footer


class PlainTierGoldenTests(unittest.TestCase):
    """Non-TTY stderr => plain tier => byte-identical to today's output."""

    def test_plain_run_matches_golden(self):
        stderr = io.StringIO()  # isatty() is False -> plain tier
        with tempfile.TemporaryDirectory() as tmp:
            with patched_runner(make_registry()):
                out_dir = run_topic(tmp, stderr)
            header, completions, footer = split_golden(stderr.getvalue(), out_dir)
            self.assertEqual(header, GOLDEN_HEADER)
            self.assertEqual(completions, GOLDEN_COMPLETIONS)
            self.assertEqual(footer, GOLDEN_FOOTER)
            # No escape byte may ever reach a piped stderr.
            self.assertNotIn("\x1b", stderr.getvalue())
            # The failed channel still wrote its ERROR.md artifact.
            self.assertEqual(
                (out_dir / "boom.ERROR.md").read_text(), "ERROR: boom failed"
            )
            manifest = json.loads((out_dir / "manifest.json").read_text())
            self.assertEqual(manifest["channels"]["alpha"]["status"], "ok")
            self.assertEqual(manifest["channels"]["boom"]["status"], "error")
            self.assertEqual(
                manifest["connectors_skipped"], {"keyless": "missing keys: ['nokey']"}
            )


ERASE = "\x1b[0J"  # LiveBoard's erase-frame control (cursor-up + clear)


@contextlib.contextmanager
def clean_ui_env(**overrides):
    with mock.patch.dict(os.environ):
        for name in UI_ENV_VARS:
            os.environ.pop(name, None)
        os.environ.update(overrides)
        yield


class AnimatedTierTests(unittest.TestCase):
    """TTY stderr + 100x24 => unicode tier => banner + board + one summary."""

    ANIMATED_ENV = {"COLUMNS": "100", "LINES": "24"}

    def run_animated(self, err_fn=_err_channel, extra_args=()):
        stderr = FakeTTY()
        with tempfile.TemporaryDirectory() as tmp:
            with patched_runner(make_registry(err_fn), env=self.ANIMATED_ENV):
                out_dir = run_topic(tmp, stderr, extra_args)
            files = {
                f.name: f.read_text() for f in sorted(out_dir.iterdir()) if f.is_file()
            }
        return stderr.getvalue(), out_dir, files

    def test_board_replaces_per_event_prints_and_summary_prints_once(self):
        baseline_threads = threading.active_count()
        raw, _, files = self.run_animated()

        # Final summary lines appear EXACTLY once — the plain per-event
        # prints are suppressed (the board's own rows use a different shape).
        self.assertEqual(raw.count("[alpha] OK 0.0s (3)"), 1)
        self.assertEqual(raw.count("[boom] ERROR: boom failed"), 1)
        self.assertEqual(raw.count("[keyless] SKIP — missing keys: ['nokey']"), 1)

        # Summary is in board (registry) order, after the final erase.
        summary = raw[raw.rindex(ERASE) :]
        self.assertLess(
            summary.index("[alpha] OK"), summary.index("[boom] ERROR")
        )
        self.assertLess(
            summary.index("[boom] ERROR"), summary.index("[keyless] SKIP")
        )

        # The board actually rendered rows: the guaranteed final frame shows
        # the ERROR row and the SKIP row in board format.
        self.assertIn("ERROR boom failed", raw)
        self.assertIn("SKIP missing keys: ['nokey']", raw)

        # Cursor control was emitted (this IS the animated tier)...
        self.assertIn(ERASE, raw)
        # ...but never after teardown: footer + file listing are plain prints.
        tail = raw.split("\nAll channels done. Output: ", 1)[1]
        self.assertNotIn("\x1b", tail)
        for name in ("_topic.txt", "alpha.md", "boom.ERROR.md", "manifest.json"):
            self.assertIn(f"  {name}: ", tail)

        # ERROR.md is still written even though the row went to the board.
        self.assertEqual(files["boom.ERROR.md"], "ERROR: boom failed")

        # Board + connector threads all joined — nothing lingers.
        self.assertEqual(threading.active_count(), baseline_threads)

    def test_board_animates_multiple_frames_with_slow_connector(self):
        raw, _, files = self.run_animated(err_fn=_slow_err_channel)
        # A connector outliving several ~10fps intervals means the loop drew
        # and erased more than one frame before the final teardown erase.
        self.assertGreaterEqual(raw.count(ERASE), 2)
        # A mid-run frame showed alpha finished while boom was still running.
        self.assertIn("running", raw)
        self.assertEqual(raw.count("[boom] ERROR: boom failed"), 1)
        self.assertEqual(files["boom.ERROR.md"], "ERROR: boom failed")

    def test_banner_art_precedes_the_board(self):
        raw, _, _ = self.run_animated()
        self.assertIn("█", raw)  # block-letter art
        self.assertIn(term_ui.SUBTITLE, raw)
        self.assertLess(raw.index("█"), raw.index("All channels done."))

    def test_no_banner_suppresses_art_but_keeps_the_board(self):
        raw, _, _ = self.run_animated(extra_args=("--no-banner",))
        self.assertNotIn("█", raw)
        self.assertNotIn(term_ui.SUBTITLE, raw)
        self.assertNotIn(term_ui.PLAIN_TITLE, raw)
        self.assertIn(ERASE, raw)  # the board still animates
        self.assertEqual(raw.count("[alpha] OK 0.0s (3)"), 1)


class DiagnoseBannerTests(unittest.TestCase):
    """--diagnose: banner in ansi tiers only; piped output is untouched."""

    DOCTOR = "DOCTOR REPORT"

    def run_diagnose(self, stderr, env=None, extra_args=()):
        fake_detect = types.SimpleNamespace(doctor_report=lambda: self.DOCTOR)
        stdout = io.StringIO()
        argv = [str(RUNNER), "--diagnose", *extra_args]
        with clean_ui_env(**(env or {})), \
             mock.patch.object(deep_research, "_import_sibling", lambda name: fake_detect), \
             mock.patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(stdout), \
             contextlib.redirect_stderr(stderr):
            deep_research.main()
        return stdout.getvalue(), stderr.getvalue()

    def test_piped_diagnose_is_exactly_todays_doctor_output(self):
        stdout, stderr = self.run_diagnose(io.StringIO())
        self.assertEqual(stdout, self.DOCTOR + "\n")
        self.assertEqual(stderr, "")  # no banner, no escapes — logs stay clean

    def test_tty_diagnose_adds_banner_on_stderr_only(self):
        stdout, stderr = self.run_diagnose(
            FakeTTY(), env={"COLUMNS": "100", "LINES": "24"}
        )
        self.assertEqual(stdout, self.DOCTOR + "\n")  # stdout untouched
        self.assertIn("█", stderr)
        self.assertIn(term_ui.SUBTITLE, stderr)

    def test_tty_diagnose_respects_no_banner(self):
        stdout, stderr = self.run_diagnose(
            FakeTTY(), env={"COLUMNS": "100", "LINES": "24"},
            extra_args=("--no-banner",),
        )
        self.assertEqual(stdout, self.DOCTOR + "\n")
        self.assertEqual(stderr, "")


class SourceHygieneTests(unittest.TestCase):
    def test_runner_source_stays_windows_safe(self):
        source = RUNNER.read_text(encoding="utf-8")
        for token in (
            "SIGALRM",
            "killpg",
            "fcntl",
            "os.fork",
            "setsid",
            "termios",
            "import pty",
            "openpty",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

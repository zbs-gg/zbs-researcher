"""U2 — the --fire single-composed-query affordance (R1, R2, R5).

--fire SOURCE runs ONE composed query (the positional topic) on ONE named
source and prints EXACTLY one JSON envelope {source, path, items, status,
provenance} to stdout — the investigate loop's machine contract. These tests
pin that contract plus the degrade rules (unknown source, key-gated source,
channel error), the accumulating manifest across sequential fires, the
pass-through of repo-scoped composed queries, the U1 provenance block on the
classic single mode, and the characterization that the classic --only and
entity-fanout paths still behave as before (no envelope on stdout, same
stderr shape, manifest only gains the additive provenance block).

All network is mocked — no live calls, no paid calls.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
import time as real_time
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

_scripts_path = str(SCRIPTS)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


deep_research = _load("deep_research_fire", RUNNER)


# Env vars the terminal-capability probe may read (mirrors test_runner_board)
# — stripped per run so the host terminal never leaks into an assertion.
UI_ENV_VARS = ("NO_COLOR", "FORCE_COLOR", "CI", "TERM", "WT_SESSION", "COLUMNS", "LINES")

ENVELOPE_KEYS = {"source", "path", "items", "status", "provenance"}


# ---------------------------------------------------------------------------
# Fixture registry: names deliberately reuse REAL reachability-table entries
# (github "yes", telegram "no", grok "partial") so the envelope's provenance
# tag can be asserted against the table, plus one failing and one key-gated
# connector for the degrade rules.
# ---------------------------------------------------------------------------
FIRE_OUTPUT_NAMES = {
    "github": "github.md",
    "github-issues": "github-issues.md",
    "telegram": "telegram.md",
    "grok": "grok-x.md",
    "boom": "boom.md",
    "tiktok-ig": "tiktok-ig.md",
}


def make_registry(captured_queries=None):
    Connector = deep_research.Connector

    def gh(query, out_path, max_items):
        if captured_queries is not None:
            captured_queries.append(query)
        out_path.write_text("github result\n")
        return 3

    def tg(query, out_path, max_items):
        out_path.write_text("telegram result\n")
        return 2

    def grok(query, out_path, max_items):
        out_path.write_text("grok result\n")
        return 4

    def boom(query, out_path, max_items):
        raise RuntimeError("boom failed")

    def never(query, out_path, max_items):
        raise AssertionError("key-gated channel must never be called")

    return {
        c.name: c
        for c in [
            Connector("github", "direct", gh, "fake github", []),
            Connector("github-issues", "direct", gh, "fake gh issues", []),
            Connector("telegram", "direct", tg, "fake telegram", [], default=False),
            Connector("grok", "llm", grok, "fake grok", []),
            Connector("boom", "direct", boom, "fake failing", []),
            Connector("tiktok-ig", "direct", never, "fake key-gated",
                      ["scrapecreators"], default=False),
        ]
    }


@contextlib.contextmanager
def patched_runner(registry, output_names=FIRE_OUTPUT_NAMES):
    with mock.patch.dict(os.environ):
        for name in UI_ENV_VARS:
            os.environ.pop(name, None)
        with mock.patch.object(deep_research, "CONNECTORS", registry), \
             mock.patch.object(deep_research, "OUTPUT_NAMES", dict(output_names)), \
             mock.patch.object(deep_research, "KEYS", {}):
            yield


def run_main(argv):
    """Invoke main() with captured stdout/stderr; returns (stdout, stderr)."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", [str(RUNNER), *argv]), \
         contextlib.redirect_stdout(stdout), \
         contextlib.redirect_stderr(stderr):
        deep_research.main()
    return stdout.getvalue(), stderr.getvalue()


def fire(out_dir, source, query):
    return run_main([query, "--fire", source, "--output-dir", str(out_dir)])


def parse_envelope(test, stdout):
    """Assert stdout is exactly one JSON line and return it parsed."""
    test.assertTrue(stdout.endswith("\n"), "envelope line must end with newline")
    line = stdout[:-1]
    test.assertNotIn("\n", line, "stdout must be EXACTLY one JSON line")
    envelope = json.loads(line)
    test.assertEqual(set(envelope), ENVELOPE_KEYS)
    return envelope


# ---------------------------------------------------------------------------
# The happy path + the loop's machine contract
# ---------------------------------------------------------------------------
class FireEnvelopeTests(unittest.TestCase):
    def test_fire_writes_result_and_prints_single_json_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            with patched_runner(make_registry()):
                stdout, stderr = fire(out_dir, "github", "agent memory leaks")
            envelope = parse_envelope(self, stdout)
            self.assertEqual(envelope["source"], "github")
            self.assertEqual(envelope["status"], "ok")
            self.assertEqual(envelope["items"], 3)
            # resolve(): the runner resolves --output-dir (macOS /var symlink).
            self.assertEqual(
                Path(envelope["path"]), (out_dir / "github.md").resolve()
            )
            self.assertEqual((out_dir / "github.md").read_text(), "github result\n")
            # Progress went to stderr, never stdout.
            self.assertIn("[github] OK", stderr)
            # No banner/board bytes anywhere near the machine channel.
            self.assertNotIn("\x1b", stdout)

    def test_envelope_provenance_matches_reachability_table(self):
        # github "yes", telegram "no", grok "partial" (no ages are known to
        # --fire, so the pre-index override can never fire).
        expected = {"github": "yes", "telegram": "no", "grok": "partial"}
        for source, tag in expected.items():
            with self.subTest(source=source):
                with tempfile.TemporaryDirectory() as tmp:
                    out_dir = Path(tmp) / "run"
                    with patched_runner(make_registry()):
                        stdout, _ = fire(out_dir, source, "composed query")
                    prov = parse_envelope(self, stdout)["provenance"]
                    self.assertEqual(prov["web_index_reachable"], tag)
                    self.assertEqual(prov["source"], source)
                    self.assertEqual(prov["query"], "composed query")
                    self.assertIsNone(prov["freshness_hours"])

    def test_repo_scoped_composed_query_passes_through_unchanged(self):
        captured = []
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            with patched_runner(make_registry(captured_queries=captured)):
                stdout, _ = fire(out_dir, "github-issues", "mem0ai/mem0")
            self.assertEqual(captured, ["mem0ai/mem0"])
            envelope = parse_envelope(self, stdout)
            self.assertEqual(envelope["provenance"]["query"], "mem0ai/mem0")


# ---------------------------------------------------------------------------
# Degrade rules: unknown source, key-gated source, channel error
# ---------------------------------------------------------------------------
class FireDegradeTests(unittest.TestCase):
    def test_unknown_source_exits_2_without_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            stdout, stderr = io.StringIO(), io.StringIO()
            argv = [str(RUNNER), "q", "--fire", "nosuch", "--output-dir", str(out_dir)]
            with patched_runner(make_registry()), \
                 mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stdout(stdout), \
                 contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    deep_research.main()
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("unknown source", stderr.getvalue())
            # Valid sources are listed so the loop can self-correct.
            self.assertIn("github", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(out_dir.exists(), "no run dir for an unknown source")

    def test_key_gated_source_is_refused_before_any_channel_call(self):
        # KEYS is {} inside patched_runner, so tiktok-ig is unavailable; its
        # channel fn raises AssertionError if it were ever called.
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            stdout, stderr = io.StringIO(), io.StringIO()
            argv = [str(RUNNER), "q", "--fire", "tiktok-ig",
                    "--output-dir", str(out_dir)]
            with patched_runner(make_registry()), \
                 mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stdout(stdout), \
                 contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    deep_research.main()
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("missing keys", stderr.getvalue())
            self.assertIn("scrapecreators", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(out_dir.exists())

    def test_channel_error_writes_error_twin_and_envelope_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            with patched_runner(make_registry()):
                # main() returns normally — no SystemExit: the envelope, not
                # the exit code, is the loop's failure signal (exit-0 contract).
                stdout, stderr = fire(out_dir, "boom", "any query")
            envelope = parse_envelope(self, stdout)
            self.assertEqual(envelope["status"], "error")
            self.assertEqual(envelope["items"], 0)
            self.assertEqual(
                Path(envelope["path"]), (out_dir / "boom.ERROR.md").resolve()
            )
            self.assertEqual(
                (out_dir / "boom.ERROR.md").read_text(), "ERROR: boom failed"
            )
            self.assertFalse((out_dir / "boom.md").exists())
            # The failure is still recorded honestly in the manifest…
            manifest = json.loads((out_dir / "manifest.json").read_text())
            self.assertEqual(manifest["channels"]["boom"]["status"], "error")
            # …and its provenance record makes no evidence claim (0 items).
            self.assertEqual(manifest["provenance"][-1]["items"], 0)
            self.assertIn("[boom] ERROR", stderr)

    def test_fire_rejects_conflicting_selection_flags(self):
        for extra in (("--only", "github"), ("--skip", "boom"),
                      ("--prepared-run",), ("--mode", "entity-fanout")):
            with self.subTest(extra=extra):
                with tempfile.TemporaryDirectory() as tmp:
                    argv = [str(RUNNER), "q", "--fire", "github",
                            "--output-dir", str(Path(tmp) / "run"), *extra]
                    with patched_runner(make_registry()), \
                         mock.patch.object(sys, "argv", argv), \
                         contextlib.redirect_stdout(io.StringIO()), \
                         contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as ctx:
                            deep_research.main()
                    self.assertEqual(ctx.exception.code, 2)


# ---------------------------------------------------------------------------
# Accumulating manifest: sequential fires build ONE investigate manifest
# ---------------------------------------------------------------------------
class FireManifestAccumulationTests(unittest.TestCase):
    def test_two_fires_into_one_dir_accumulate_channels_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            with patched_runner(make_registry()):
                fire(out_dir, "github", "first composed query")
                fire(out_dir, "telegram", "second composed query")
            manifest = json.loads((out_dir / "manifest.json").read_text())
            self.assertEqual(manifest["mode"], "investigate")
            # The first fire's query names the run and sticks.
            self.assertEqual(manifest["topic"], "first composed query")
            self.assertEqual(
                (out_dir / "_topic.txt").read_text(), "first composed query\n"
            )
            self.assertEqual(
                set(manifest["channels"]), {"github", "telegram"}
            )
            self.assertEqual(
                [row["source"] for row in manifest["provenance"]],
                ["github", "telegram"],
            )
            self.assertEqual(
                [row["query"] for row in manifest["provenance"]],
                ["first composed query", "second composed query"],
            )
            # Both result files coexist in the accumulated run.
            self.assertTrue((out_dir / "github.md").exists())
            self.assertTrue((out_dir / "telegram.md").exists())

    def test_unreadable_manifest_starts_fresh_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            out_dir.mkdir(parents=True)
            (out_dir / "manifest.json").write_text("{not json")
            with patched_runner(make_registry()):
                stdout, stderr = fire(out_dir, "github", "q")
            self.assertEqual(parse_envelope(self, stdout)["status"], "ok")
            self.assertIn("unreadable", stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text())
            self.assertEqual(manifest["mode"], "investigate")
            self.assertEqual(len(manifest["provenance"]), 1)


# ---------------------------------------------------------------------------
# Characterization (keystone): the default paths are untouched by --fire
# ---------------------------------------------------------------------------
def _ok_channel(query, out_path, max_items):
    out_path.write_text("alpha report\n")
    return 3


def _err_channel(query, out_path, max_items):
    raise RuntimeError("boom failed")


def _never_channel(query, out_path, max_items):
    raise AssertionError("skipped connector must never run")


def make_classic_registry():
    Connector = deep_research.Connector
    return {
        c.name: c
        for c in [
            Connector("alpha", "direct", _ok_channel, "fake ok", []),
            Connector("boom", "direct", _err_channel, "fake error", []),
            Connector("keyless", "direct", _never_channel, "fake skip", ["nokey"]),
        ]
    }


CLASSIC_OUTPUT_NAMES = {"alpha": "alpha.md", "boom": "boom.md", "keyless": "keyless.md"}


def fixed_time():
    """The runner module's ``time`` with a frozen clock (dt is always 0.0)."""
    return types.SimpleNamespace(
        time=lambda: 1000.0,
        strftime=real_time.strftime,
        gmtime=real_time.gmtime,
        sleep=real_time.sleep,
    )


class ClassicModeCharacterizationTests(unittest.TestCase):
    """A plain --only run behaves as before the --fire work: empty stdout,
    the same stderr line-per-event shape, the same result files; the ONLY
    manifest delta is the additive U1 provenance block."""

    def test_only_run_is_unchanged_except_additive_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            with patched_runner(make_classic_registry(), CLASSIC_OUTPUT_NAMES), \
                 mock.patch.object(deep_research, "time", fixed_time()):
                stdout, stderr = run_main(
                    ["demo topic", "--only", "alpha,boom",
                     "--output-dir", str(out_dir)]
                )
            # Classic mode never speaks on stdout — no envelope leaks.
            self.assertEqual(stdout, "")
            # stderr keeps today's line-per-event shape, escape-free.
            self.assertIn("[alpha] OK 0.0s (3)", stderr)
            self.assertIn("[boom] ERROR: boom failed", stderr)
            self.assertIn("All channels done. Output: ", stderr)
            self.assertNotIn("\x1b", stderr)
            # Result artifacts are byte-identical to the pre-change runner.
            self.assertEqual((out_dir / "alpha.md").read_text(), "alpha report\n")
            self.assertEqual(
                (out_dir / "boom.ERROR.md").read_text(), "ERROR: boom failed"
            )
            manifest = json.loads((out_dir / "manifest.json").read_text())
            # Exactly the pre-change keys + the additive provenance block; a
            # classic run is NOT an investigate run (no "mode" key).
            self.assertEqual(
                set(manifest),
                {"topic", "started", "connectors_run", "connectors_skipped",
                 "channels", "provenance", "finished"},
            )
            self.assertEqual(manifest["topic"], "demo topic")
            self.assertEqual(manifest["connectors_run"], ["alpha", "boom"])
            self.assertEqual(manifest["connectors_skipped"], {})
            self.assertEqual(manifest["channels"]["alpha"]["status"], "ok")
            self.assertEqual(manifest["channels"]["boom"]["status"], "error")
            # One record per RAN channel, static classification only.
            self.assertEqual(
                [(r["source"], r["items"], r["web_index_reachable"])
                 for r in manifest["provenance"]],
                [("alpha", 3, "yes"), ("boom", 0, "yes")],
            )
            for row in manifest["provenance"]:
                self.assertIsNone(row["freshness_hours"])
                self.assertEqual(row["query"], "demo topic")

    def test_entity_fanout_dry_run_path_is_untouched(self):
        """The fanout branch still runs first and prints its own summary —
        stdout stays empty (no fire envelope machinery bleeds in)."""
        calls = {}

        class FakeFanout:
            DEFAULT_N = 50
            DEFAULT_K = 10
            HARD_N_CAP = 200
            DEFAULT_CONCURRENCY = 6

            @staticmethod
            def attach_runner(g):
                calls["attached"] = True

            @staticmethod
            def run_entity_fanout(topic, out_dir, keys, **kwargs):
                calls["kwargs"] = kwargs
                (Path(out_dir) / "research-plan.md").write_text("plan\n")
                return {
                    "manifest": {
                        "dry_run": True,
                        "entities": 5,
                        "plan": {"free_cells": 10, "paid_cells": 0},
                    }
                }

        real_import = deep_research._import_sibling
        fake_import = (
            lambda name: FakeFanout if name == "entity_fanout" else real_import(name)
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            with patched_runner(make_classic_registry(), CLASSIC_OUTPUT_NAMES), \
                 mock.patch.object(deep_research, "_import_sibling", fake_import):
                stdout, stderr = run_main(
                    ["demo topic", "--mode", "entity-fanout", "--dry-run",
                     "--output-dir", str(out_dir)]
                )
            self.assertEqual(stdout, "")
            self.assertTrue(calls["attached"])
            self.assertTrue(calls["kwargs"]["dry_run"])
            self.assertIn("[entity-fanout] dry-run: 5 entities enumerated", stderr)
            self.assertIn("Entity-fanout dry-run done.", stderr)
            # The dry run wrote a plan, never a fire manifest.
            self.assertTrue((out_dir / "research-plan.md").exists())
            self.assertFalse((out_dir / "manifest.json").exists())


# ---------------------------------------------------------------------------
# --feedback: the U4 CLI capture (honest wording, ledger round-trip)
# ---------------------------------------------------------------------------
class FeedbackCliTests(unittest.TestCase):
    def test_feedback_appends_note_and_prints_honest_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ):
                os.environ["DEEP_RESEARCH_SECRETS_DIR"] = tmp
                os.environ.pop("DEEP_RESEARCH_CARTOGRAPHER_URL", None)
                stdout, _ = run_main(
                    ["--feedback", "too many stale results",
                     "--topic", "agent memory"]
                )
            ledger = Path(tmp) / "investigate-feedback.jsonl"
            rows = [json.loads(line) for line in
                    ledger.read_text().splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["topic"], "agent memory")
            self.assertEqual(rows[0]["human_feedback"], "too many stale results")
            # Honest wording: saved to inform the next run; never "learned",
            # and no relay claim without a real 2xx.
            self.assertIn("saved locally", stdout)
            self.assertIn("inform the next run", stdout)
            self.assertNotIn("learn", stdout.lower())
            self.assertIn("not relayed anywhere", stdout)

    def test_feedback_requires_a_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ):
                os.environ["DEEP_RESEARCH_SECRETS_DIR"] = tmp
                argv = [str(RUNNER), "--feedback", "note without a topic"]
                with mock.patch.object(sys, "argv", argv), \
                     contextlib.redirect_stdout(io.StringIO()), \
                     contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as ctx:
                        deep_research.main()
            self.assertEqual(ctx.exception.code, 2)
            self.assertFalse((Path(tmp) / "investigate-feedback.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

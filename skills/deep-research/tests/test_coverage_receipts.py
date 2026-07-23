"""U6 — coverage-receipts renderer (R6).

coverage_markers / coverage_summary / render_coverage_section turn the run
manifest's real provenance records into the report's Coverage section: inline
markers for what a web-index researcher can NOT reach, one honest summary
line, and a per-source reachability table. Truthfulness gate throughout — a
"yes" record never yields a marker, a manifest with no provenance yields NO
section (never a fabricated one), and a yes-only run says "0 of M" out loud
instead of hiding it. The --coverage CLI mode prints that section from a run
directory's manifest.json.

Pure rendering + local files only — no network, no keys, no paid calls.
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PROVENANCE = SCRIPTS / "provenance.py"
RUNNER = SCRIPTS / "deep-research.py"

_scripts_path = str(SCRIPTS)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


provenance = _load("provenance_coverage", PROVENANCE)
deep_research = _load("deep_research_coverage", RUNNER)


FIXED_AT = "2026-07-22T12:00:00+00:00"


def rec(source, items=3, age=None, query="composed query"):
    """A REAL provenance record (the only thing markers may render from)."""
    return provenance.provenance_record(
        source, query, items, newest_item_age_hours=age, fetched_at=FIXED_AT
    )


def mixed_records():
    """telegram(no) + github(yes) + grok fresh 3h (partial -> no override)."""
    return [rec("telegram"), rec("github"), rec("grok", age=3)]


# ---------------------------------------------------------------------------
# coverage_markers: only no/partial records speak; "yes" is NEVER marked
# ---------------------------------------------------------------------------
class CoverageMarkersTests(unittest.TestCase):
    def test_markers_only_for_no_and_partial_records(self):
        markers = provenance.coverage_markers(mixed_records())
        self.assertEqual(len(markers), 2)
        self.assertTrue(any("telegram" in m for m in markers))
        self.assertFalse(any("github" in m for m in markers),
                         "a yes record must never yield a marker")

    def test_yes_only_records_yield_no_markers(self):
        self.assertEqual(
            provenance.coverage_markers([rec("github"), rec("hackernews")]), []
        )

    def test_no_records_yield_no_markers(self):
        self.assertEqual(provenance.coverage_markers([]), [])

    def test_marker_text_is_the_records_own_reason(self):
        # Truthfulness gate: the marker carries the record's reason verbatim,
        # never re-inferred prose.
        record = rec("telegram")
        (marker,) = provenance.coverage_markers([record])
        self.assertIn(record["reason"], marker)
        self.assertIn("no web footprint", marker)

    def test_fresh_grok_marker_carries_the_pre_index_freshness_text(self):
        (marker,) = provenance.coverage_markers([rec("grok", age=3)])
        self.assertIn("grok/X", marker)
        self.assertIn("posted 3h ago", marker)
        self.assertIn("not yet web-indexed", marker)

    def test_identical_repeated_fires_collapse_to_one_marker(self):
        markers = provenance.coverage_markers([rec("telegram"), rec("telegram")])
        self.assertEqual(len(markers), 1)


# ---------------------------------------------------------------------------
# coverage_summary: honest counts over DISTINCT sources
# ---------------------------------------------------------------------------
class CoverageSummaryTests(unittest.TestCase):
    def test_counts_unreachable_and_partial_sources(self):
        summary = provenance.coverage_summary(
            [rec("telegram"), rec("github"), rec("grok")]
        )
        self.assertIn("2 of 3 sources web-index-unreachable or partial", summary)

    def test_freshest_signal_age_is_appended_when_known(self):
        summary = provenance.coverage_summary(mixed_records())
        self.assertIn("2 of 3", summary)
        self.assertIn("freshest signal ~3h old", summary)

    def test_no_known_ages_means_no_freshness_claim(self):
        summary = provenance.coverage_summary([rec("telegram"), rec("github")])
        self.assertNotIn("freshest", summary)

    def test_yes_only_run_says_zero_out_loud(self):
        summary = provenance.coverage_summary([rec("github"), rec("hackernews")])
        self.assertIn("0 of 2", summary)
        self.assertIn("web-index-reachable", summary)

    def test_repeat_fires_of_one_source_count_it_once(self):
        summary = provenance.coverage_summary(
            [rec("telegram"), rec("telegram"), rec("github")]
        )
        self.assertIn("1 of 2", summary)

    def test_empty_list_gives_empty_summary(self):
        self.assertEqual(provenance.coverage_summary([]), "")


# ---------------------------------------------------------------------------
# render_coverage_section: full section or NOTHING — never fabricated
# ---------------------------------------------------------------------------
class RenderCoverageSectionTests(unittest.TestCase):
    def test_no_provenance_renders_no_section(self):
        for manifest in ({}, {"provenance": []}, {"provenance": "junk"},
                         {"topic": "x", "channels": {}}, None):
            with self.subTest(manifest=manifest):
                self.assertEqual(
                    provenance.render_coverage_section(manifest), ""
                )

    def test_full_section_has_heading_summary_markers_and_table(self):
        section = provenance.render_coverage_section(
            {"provenance": mixed_records()}
        )
        lines = section.split("\n")
        self.assertEqual(
            lines[0], "## Coverage — what a web-index researcher would miss"
        )
        self.assertIn("2 of 3 sources web-index-unreachable or partial", section)
        self.assertIn("| source | reachability | reason |", section)
        # Table carries EVERY fired source, markers only the unreachable ones.
        self.assertTrue(any(l.startswith("| github | yes |") for l in lines))
        self.assertTrue(any(l.startswith("| telegram | no |") for l in lines))
        self.assertTrue(any(l.startswith("- telegram") for l in lines))
        self.assertFalse(any(l.startswith("- github") for l in lines),
                         "no inline marker for a web-reachable source")

    def test_section_stays_self_contained_through_markdown_to_html(self):
        # The session pastes the section into synthesis.md; brief.html renders
        # it via the existing markdown_to_html — no external refs may appear.
        section = provenance.render_coverage_section(
            {"provenance": mixed_records()}
        )
        html = deep_research.markdown_to_html(section)
        self.assertIn("<table>", html)
        self.assertIn("<h2>", html)
        self.assertNotIn("src=", html)
        self.assertNotIn("@import", html)


# ---------------------------------------------------------------------------
# --coverage CLI: print the section from RUN_DIR/manifest.json
# ---------------------------------------------------------------------------
def run_main(argv):
    """Invoke main() with captured stdout/stderr; returns (stdout, stderr)."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", [str(RUNNER), *argv]), \
         contextlib.redirect_stdout(stdout), \
         contextlib.redirect_stderr(stderr):
        deep_research.main()
    return stdout.getvalue(), stderr.getvalue()


class CoverageCliTests(unittest.TestCase):
    def test_coverage_prints_the_section_for_a_run_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(
                json.dumps({"mode": "investigate", "topic": "t",
                            "provenance": mixed_records()})
            )
            stdout, _ = run_main(["--coverage", str(run_dir)])
        self.assertIn("## Coverage — what a web-index researcher would miss",
                      stdout)
        self.assertIn("telegram", stdout)
        self.assertIn("2 of 3", stdout)

    def test_coverage_prints_nothing_for_a_manifest_without_provenance(self):
        # Honest empty: no provenance data -> no section, normal exit 0.
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text("{}")
            stdout, _ = run_main(["--coverage", str(run_dir)])
        self.assertEqual(stdout, "")

    def test_coverage_on_a_dir_without_manifest_errors_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = [str(RUNNER), "--coverage", tmp]
            with mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    deep_research.main()
            self.assertEqual(ctx.exception.code, 2)

    def test_coverage_is_mutually_exclusive_with_fire(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = [str(RUNNER), "q", "--coverage", tmp, "--fire", "github"]
            with mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    deep_research.main()
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

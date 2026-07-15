import contextlib
import hashlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deep-research.py"
SPEC = importlib.util.spec_from_file_location("deep_research_runner", SCRIPT)
deep_research = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deep_research)


class OutputPathTests(unittest.TestCase):
    def test_nested_git_launch_resolves_git_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            subprocess.run(
                ["git", "init", "-q", str(root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            nested = root / "game" / "tools"
            nested.mkdir(parents=True)

            self.assertEqual(deep_research.resolve_project_root(nested), root)

    def test_non_git_launch_falls_back_to_captured_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            failed = subprocess.CompletedProcess([], 128, "", "not a repository")

            with mock.patch.object(deep_research.subprocess, "run", return_value=failed):
                self.assertEqual(
                    deep_research.resolve_project_root(launch_cwd), launch_cwd
                )

    def test_missing_git_falls_back_to_captured_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()

            with mock.patch.object(
                deep_research.subprocess, "run", side_effect=FileNotFoundError
            ):
                self.assertEqual(
                    deep_research.resolve_project_root(launch_cwd), launch_cwd
                )

    def test_explicit_project_root_overrides_outer_git_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp).resolve()
            subprocess.run(
                ["git", "init", "-q", str(outer)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            project = outer / "packages" / "zeus"
            launch_cwd = project / "tools"
            launch_cwd.mkdir(parents=True)

            self.assertEqual(
                deep_research.resolve_project_root(launch_cwd, project), project
            )

    def test_invalid_explicit_project_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            missing = launch_cwd / "missing"

            with self.assertRaisesRegex(ValueError, "project root"):
                deep_research.resolve_project_root(launch_cwd, missing)

    def test_explicit_output_directory_wins_and_relative_is_launch_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            absolute = launch_cwd / "elsewhere" / "absolute"

            self.assertEqual(
                deep_research.resolve_output_directory(absolute, launch_cwd), absolute
            )
            self.assertEqual(
                deep_research.resolve_output_directory("relative/run", launch_cwd),
                launch_cwd / "relative" / "run",
            )

    def test_topic_slug_normalizes_case_spacing_punctuation_and_unicode(self):
        self.assertEqual(
            deep_research.topic_slug("  Mobile RTS: Touch UI!  "),
            "mobile-rts-touch-ui",
        )
        self.assertEqual(deep_research.topic_slug("ＺＥＵＳ café"), "zeus-café")

    def test_symbol_only_topic_uses_deterministic_digest_fallback(self):
        topic = "🔥✨"
        expected = "topic-" + hashlib.sha256(topic.encode("utf-8")).hexdigest()[:8]

        self.assertEqual(deep_research.topic_slug(topic), expected)
        self.assertEqual(deep_research.topic_slug(topic), expected)

    def test_overlong_multibyte_slug_keeps_complete_component_byte_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            allocated = deep_research.allocate_run_directory(
                root,
                "é" * 500,
                run_date="2026-07-15",
                name_max=80,
            )

            self.assertLessEqual(len(allocated.name.encode("utf-8")), 80)
            self.assertEqual(allocated.name.encode("utf-8").decode("utf-8"), allocated.name)

    def test_collision_allocates_numbered_sibling_without_touching_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            first = root / "research" / "deep-research-mobile-rts-2026-07-15"
            first.mkdir(parents=True)
            sentinel = first / "sentinel.txt"
            sentinel.write_text("original", encoding="utf-8")

            allocated = deep_research.allocate_run_directory(
                root, "Mobile RTS", run_date="2026-07-15"
            )

            self.assertEqual(allocated.name, "deep-research-mobile-rts-2026-07-15-02")
            self.assertTrue(allocated.is_dir())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "original")

    def test_concurrent_allocators_claim_distinct_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            def allocate():
                return deep_research.allocate_run_directory(
                    root, "Mobile RTS", run_date="2026-07-15"
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                allocated = list(pool.map(lambda _: allocate(), range(2)))

            self.assertEqual(len(set(allocated)), 2)
            self.assertTrue(all(path.is_dir() for path in allocated))


class CliModeTests(unittest.TestCase):
    def run_main(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", [str(SCRIPT), *map(str, args)]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                deep_research.main()
        return stdout.getvalue(), stderr.getvalue()

    def test_allocate_only_prints_reserved_directory_without_starting_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()

            stdout, _ = self.run_main(
                "Mobile RTS",
                "--allocate-run",
                "--project-root",
                project,
            )

            allocated = Path(stdout.strip())
            self.assertTrue(allocated.is_dir())
            self.assertEqual(allocated.parent, project / "research")
            self.assertEqual(list(allocated.iterdir()), [])

    def test_default_run_passes_one_concrete_allocated_directory_to_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            with mock.patch.object(
                deep_research, "select_connectors", return_value=([], [])
            ):
                self.run_main("Mobile RTS", "--project-root", project)

            runs = list((project / "research").iterdir())
            self.assertEqual(len(runs), 1)
            self.assertEqual(
                (runs[0] / "_topic.txt").read_text(encoding="utf-8"),
                "Mobile RTS\n",
            )
            self.assertTrue((runs[0] / "manifest.json").is_file())

    def test_explicit_output_bypasses_project_root_resolution_and_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            requested = launch_cwd / "raw-output"
            with mock.patch.object(
                deep_research, "select_connectors", return_value=([], [])
            ), mock.patch.object(
                deep_research,
                "resolve_project_root",
                side_effect=AssertionError("project root must be bypassed"),
            ), mock.patch.object(
                deep_research.Path, "cwd", return_value=launch_cwd
            ):
                self.run_main("Mobile RTS", "--output-dir", "raw-output")

            self.assertTrue((requested / "manifest.json").is_file())
            self.assertFalse((launch_cwd / "research").exists())

    def test_list_connectors_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            with mock.patch.object(deep_research.Path, "cwd", return_value=launch_cwd):
                stdout, _ = self.run_main("--list-connectors")

            self.assertIn('"connectors"', stdout)
            self.assertFalse((launch_cwd / "research").exists())

    def test_render_only_defaults_next_to_input_and_allocates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            source = launch_cwd / "synthesis.md"
            source.write_text("# Brief\n", encoding="utf-8")
            with mock.patch.object(deep_research.Path, "cwd", return_value=launch_cwd):
                self.run_main("--render-html", source)

            self.assertTrue(source.with_suffix(".html").is_file())
            self.assertFalse((launch_cwd / "research").exists())

    def test_invalid_run_inputs_fail_before_allocating(self):
        cases = [
            ("--project-root", "{root}"),
            ("Topic", "--project-root", "{root}", "--only", "not-a-connector"),
            ("Topic", "--project-root", "{root}", "--skip", "not-a-connector"),
            ("Topic", "--project-root", "{root}", "--q", "not-a-connector:query"),
            ("Topic", "--project-root", "{root}", "--only", "github", "--skip", "reddit"),
        ]
        for raw_args in cases:
            with self.subTest(args=raw_args), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp).resolve()
                args = [str(project) if arg == "{root}" else arg for arg in raw_args]
                with self.assertRaises(SystemExit):
                    self.run_main(*args)
                self.assertFalse((project / "research").exists())

    def test_invalid_project_root_fails_before_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            missing = launch_cwd / "missing"
            with mock.patch.object(deep_research.Path, "cwd", return_value=launch_cwd):
                with self.assertRaises(SystemExit):
                    self.run_main("Topic", "--project-root", missing)
            self.assertFalse((launch_cwd / "research").exists())

    def test_incompatible_modes_fail_before_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            source = launch_cwd / "synthesis.md"
            source.write_text("# Brief\n", encoding="utf-8")
            with mock.patch.object(deep_research.Path, "cwd", return_value=launch_cwd):
                with self.assertRaises(SystemExit):
                    self.run_main("--list-connectors", "--render-html", source)
            self.assertFalse((launch_cwd / "research").exists())


if __name__ == "__main__":
    unittest.main()

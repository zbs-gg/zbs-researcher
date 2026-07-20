import contextlib
import hashlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "deep-research.py"
scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
SPEC = importlib.util.spec_from_file_location("deep_research_runner", SCRIPT)
deep_research = importlib.util.module_from_spec(SPEC)
try:
    SPEC.loader.exec_module(deep_research)
finally:
    if path_added:
        sys.path.remove(scripts_path)
output_paths = sys.modules["output_paths"]


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

            self.assertEqual(output_paths.resolve_project_root(nested), root)

    def test_non_git_launch_falls_back_to_captured_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            failed = subprocess.CompletedProcess([], 128, "", "not a repository")

            with mock.patch.object(output_paths.subprocess, "run", return_value=failed):
                self.assertEqual(
                    output_paths.resolve_project_root(launch_cwd), launch_cwd
                )

    def test_missing_git_falls_back_to_captured_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()

            with mock.patch.object(
                output_paths.subprocess, "run", side_effect=FileNotFoundError
            ):
                self.assertEqual(
                    output_paths.resolve_project_root(launch_cwd), launch_cwd
                )

    def test_timed_out_git_discovery_falls_back_to_captured_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()

            with mock.patch.object(
                output_paths.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("git", 5),
            ):
                self.assertEqual(
                    output_paths.resolve_project_root(launch_cwd), launch_cwd
                )

    def test_git_discovery_ignores_rebinding_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()

            def fake_run(*_args, **kwargs):
                for name in output_paths.GIT_REBINDING_ENV_VARS:
                    self.assertNotIn(name, kwargs["env"])
                return subprocess.CompletedProcess([], 128, "", "not a repository")

            polluted = {name: "/tmp/other" for name in output_paths.GIT_REBINDING_ENV_VARS}
            with mock.patch.dict(output_paths.os.environ, polluted), mock.patch.object(
                output_paths.subprocess, "run", side_effect=fake_run
            ):
                self.assertEqual(
                    output_paths.resolve_project_root(launch_cwd), launch_cwd
                )

    def test_git_root_outside_launch_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            launch_cwd = base / "launch"
            launch_cwd.mkdir()
            outside = base / "other"
            outside.mkdir()
            discovered = subprocess.CompletedProcess([], 0, str(outside) + "\n", "")

            with mock.patch.object(
                output_paths.subprocess, "run", return_value=discovered
            ):
                self.assertEqual(
                    output_paths.resolve_project_root(launch_cwd), launch_cwd
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
                output_paths.resolve_project_root(launch_cwd, project), project
            )

    def test_invalid_explicit_project_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            missing = launch_cwd / "missing"

            with self.assertRaisesRegex(ValueError, "project root"):
                output_paths.resolve_project_root(launch_cwd, missing)

    def test_allocator_does_not_create_a_missing_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp).resolve() / "missing"

            with self.assertRaisesRegex(ValueError, "project root"):
                output_paths.allocate_run_directory(missing, "Mobile RTS")

            self.assertFalse(missing.exists())

    def test_allocator_rejects_a_non_directory_research_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "research").write_text("occupied", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "research path"):
                output_paths.allocate_run_directory(root, "Mobile RTS")

    def test_allocator_rejects_an_impossibly_small_name_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            with self.assertRaisesRegex(ValueError, "name limit"):
                output_paths.allocate_run_directory(
                    root,
                    "Mobile RTS",
                    run_date="2026-07-15",
                    name_max=10,
                )

    def test_explicit_output_directory_wins_and_relative_is_launch_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()
            absolute = launch_cwd / "elsewhere" / "absolute"

            self.assertEqual(
                output_paths.resolve_output_directory(absolute, launch_cwd), absolute
            )
            self.assertEqual(
                output_paths.resolve_output_directory("relative/run", launch_cwd),
                launch_cwd / "relative" / "run",
            )

    def test_explicit_paths_reject_blank_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch_cwd = Path(tmp).resolve()

            for value in ("", "   "):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(ValueError, "blank"):
                        output_paths.resolve_output_directory(value, launch_cwd)
                    with self.assertRaisesRegex(ValueError, "blank"):
                        output_paths.resolve_project_root(launch_cwd, value)

    def test_explicit_launch_directory_is_resolved_from_process_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            process_cwd = Path(tmp).resolve()
            launch_cwd = process_cwd / "project"
            launch_cwd.mkdir()

            self.assertEqual(
                output_paths.resolve_launch_directory("project", process_cwd),
                launch_cwd,
            )
            with self.assertRaisesRegex(ValueError, "launch directory"):
                output_paths.resolve_launch_directory("missing", process_cwd)

    def test_topic_slug_normalizes_case_spacing_punctuation_and_unicode(self):
        self.assertEqual(
            output_paths.topic_slug("  Mobile RTS: Touch UI!  "),
            "mobile-rts-touch-ui",
        )
        self.assertEqual(output_paths.topic_slug("ＺＥＵＳ café"), "zeus-café")

    def test_symbol_only_topic_uses_deterministic_digest_fallback(self):
        topic = "🔥✨"
        expected = "topic-" + hashlib.sha256(topic.encode("utf-8")).hexdigest()[:8]

        self.assertEqual(output_paths.topic_slug(topic), expected)
        self.assertEqual(output_paths.topic_slug(topic), expected)

    def test_overlong_multibyte_slug_keeps_complete_component_byte_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            allocated = output_paths.allocate_run_directory(
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

            allocated = output_paths.allocate_run_directory(
                root, "Mobile RTS", run_date="2026-07-15"
            )

            self.assertEqual(allocated.name, "deep-research-mobile-rts-2026-07-15-02")
            self.assertTrue(allocated.is_dir())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "original")

    def test_concurrent_allocators_claim_distinct_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            def allocate():
                return output_paths.allocate_run_directory(
                    root, "Mobile RTS", run_date="2026-07-15"
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                allocated = list(pool.map(lambda _: allocate(), range(2)))

            self.assertEqual(len(set(allocated)), 2)
            self.assertTrue(all(path.is_dir() for path in allocated))

    def test_prepared_run_requires_matching_topic_plan_and_no_raw_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp).resolve()
            (run_dir / "_topic.txt").write_text("Mobile RTS\n", encoding="utf-8")
            (run_dir / "research-plan.md").write_text("# Plan\n", encoding="utf-8")

            output_paths.validate_prepared_run_directory(run_dir, "Mobile RTS")

            (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-plan artifacts"):
                output_paths.validate_prepared_run_directory(run_dir, "Mobile RTS")

    def test_prepared_run_rejects_missing_empty_or_mismatched_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp).resolve()

            with self.assertRaisesRegex(ValueError, "topic marker"):
                output_paths.validate_prepared_run_directory(run_dir, "Mobile RTS")

            (run_dir / "_topic.txt").write_text("Other Topic\n", encoding="utf-8")
            (run_dir / "research-plan.md").write_text("# Plan\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "topic mismatch"):
                output_paths.validate_prepared_run_directory(run_dir, "Mobile RTS")

            (run_dir / "_topic.txt").write_text("Mobile RTS\n", encoding="utf-8")
            (run_dir / "research-plan.md").write_text(" \n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "plan is empty"):
                output_paths.validate_prepared_run_directory(run_dir, "Mobile RTS")

    def test_prepared_run_claim_is_single_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp).resolve()
            (run_dir / "_topic.txt").write_text("Mobile RTS\n", encoding="utf-8")
            (run_dir / "research-plan.md").write_text("# Plan\n", encoding="utf-8")

            output_paths.claim_prepared_run_directory(run_dir, "Mobile RTS")

            self.assertEqual(
                (run_dir / output_paths.PREPARED_RUN_CLAIM).read_text(encoding="utf-8"),
                "Mobile RTS\n",
            )
            with self.assertRaisesRegex(ValueError, "non-plan artifacts|already claimed"):
                output_paths.claim_prepared_run_directory(run_dir, "Mobile RTS")


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
            self.assertEqual(
                (allocated / "_topic.txt").read_text(encoding="utf-8"),
                "Mobile RTS\n",
            )
            self.assertEqual(
                sorted(path.name for path in allocated.iterdir()), ["_topic.txt"]
            )

    def test_prepared_run_reuses_exact_reservation_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            stdout, _ = self.run_main(
                "Mobile RTS", "--allocate-run", "--project-root", project
            )
            run_dir = Path(stdout.strip())
            plan = run_dir / "research-plan.md"
            plan.write_text("# Plan\n", encoding="utf-8")

            with mock.patch.object(
                deep_research, "select_connectors", return_value=([], [])
            ):
                self.run_main(
                    "Mobile RTS",
                    "--output-dir",
                    run_dir,
                    "--prepared-run",
                )

            self.assertEqual(plan.read_text(encoding="utf-8"), "# Plan\n")
            self.assertTrue((run_dir / "manifest.json").is_file())
            self.assertEqual(len(list((project / "research").iterdir())), 1)

    def test_concurrent_prepared_cli_runs_accept_exactly_one_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            stdout, _ = self.run_main(
                "Mobile RTS", "--allocate-run", "--project-root", project
            )
            run_dir = Path(stdout.strip())
            (run_dir / "research-plan.md").write_text("# Plan\n", encoding="utf-8")
            secrets = project / "no-secrets"
            secrets.mkdir()
            environment = os.environ.copy()
            environment.pop("GEMINI_API_KEY", None)
            environment["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets)
            command = [
                sys.executable,
                str(SCRIPT),
                "Mobile RTS",
                "--output-dir",
                str(run_dir),
                "--prepared-run",
                "--only",
                "gemini",
            ]

            processes = [
                subprocess.Popen(
                    command,
                    cwd=project,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(2)
            ]
            results = [process.communicate(timeout=10) for process in processes]
            return_codes = sorted(process.returncode for process in processes)

            self.assertEqual(return_codes, [0, 2], results)
            self.assertTrue((run_dir / "manifest.json").is_file())

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

    def test_captured_launch_directory_owns_run_when_process_cwd_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            process_cwd = base / "agent-work"
            process_cwd.mkdir()
            project = base / "project"
            project.mkdir()
            with mock.patch.object(
                deep_research, "select_connectors", return_value=([], [])
            ), mock.patch.object(
                deep_research.Path, "cwd", return_value=process_cwd
            ), mock.patch.object(
                output_paths.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 128, "", "not a repo"),
            ):
                self.run_main("Mobile RTS", "--launch-cwd", project)

            self.assertTrue((project / "research").is_dir())
            self.assertFalse((process_cwd / "research").exists())

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

    def test_blank_explicit_paths_fail_before_allocation(self):
        cases = (
            ("Topic", "--output-dir", ""),
            ("Topic", "--output-dir", "   "),
            ("Topic", "--project-root", ""),
            ("Topic", "--project-root", "   "),
            ("Topic", "--allocate-run", "--output-dir", ""),
        )
        for args in cases:
            with self.subTest(args=args), tempfile.TemporaryDirectory() as tmp:
                launch_cwd = Path(tmp).resolve()
                with mock.patch.object(
                    deep_research.Path, "cwd", return_value=launch_cwd
                ):
                    with self.assertRaises(SystemExit):
                        self.run_main(*args)
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

    def test_allocation_rejects_raw_run_options(self):
        cases = (
            ("Topic", "--allocate-run", "--max-items", "3"),
            ("Topic", "--allocate-run", "--prepared-run"),
            ("Topic", "--prepared-run"),
        )
        for args in cases:
            with self.subTest(args=args), tempfile.TemporaryDirectory() as tmp:
                launch_cwd = Path(tmp).resolve()
                with mock.patch.object(
                    deep_research.Path, "cwd", return_value=launch_cwd
                ):
                    with self.assertRaises(SystemExit):
                        self.run_main(*args)
                self.assertFalse((launch_cwd / "research").exists())


if __name__ == "__main__":
    unittest.main()

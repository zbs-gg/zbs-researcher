"""Contract tests for the private five-question Researcher vs Parallel duel.

Every provider is injected. These tests must never perform network or paid work.
"""
import importlib.util
import json
import os
import random
import sys
import tempfile
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MODULE_PATH = SCRIPTS / "duel_benchmark.py"
SUITE_PATH = ROOT / "benchmarks" / "duel-v1.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("duel_benchmark_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


duel = _load_module()


FROZEN_QUESTIONS = [
    "As an independent AI builder aiming to build an English-language reputation in 2026, should I invest seriously in X, and which current practices produce qualified relationships rather than vanity reach? What changed since 2023?",
    "For a production coding or AI agent in 2026, when should a team choose Mem0, Letta, or a custom memory layer? What failure modes are practitioners actually seeing, and which remain unresolved?",
    "What kinds of AI decision and architecture clarity are companies demonstrably paying for in 2026, how do buyers describe the pain in their own words, and which needs remain poorly served?",
    "Using current primary documentation only, compare the pricing, latency, data handling, privacy, and operational limits of Parallel Task API, Perplexity Sonar/API, and OpenAI web-search/research APIs for an agent product.",
    "What do primary 2025–2026 studies actually establish about long-term memory in LLM agents? Where do benchmarks disagree, and which important claims remain unproven?",
]


def _utc(hour=8):
    return datetime(2026, 8, 14, hour, 0, tzinfo=timezone.utc)


def _researcher_run(parent, question, *, complete=True, topic=None):
    run = Path(parent) / ("researcher-" + str(len(list(Path(parent).glob("researcher-*")))))
    run.mkdir()
    actual_topic = topic if topic is not None else question
    (run / "_topic.txt").write_text(actual_topic, encoding="utf-8")
    (run / "research-plan.md").write_text(
        f"# Research plan\n\nQuestion: {question}\n\n## Source plan\n- X: practitioners\n",
        encoding="utf-8",
    )
    (run / "manifest.json").write_text(
        json.dumps({
            "topic": actual_topic,
            "mode": "investigate",
            "started": "2026-08-14T08:00:00+00:00",
            "finished": "2026-08-14T08:02:00+00:00",
            "channels": {"grok": {"status": "ok", "seconds": 12.0}},
            "provenance": {"grok": {"source": "grok", "freshness_hours": 2}},
        }),
        encoding="utf-8",
    )
    (run / "grok-x.md").write_text(
        '# Grok\n- https://x.com/a/status/1\n  @a: "first-hand evidence with detail"\n',
        encoding="utf-8",
    )
    if complete:
        (run / "synthesis.md").write_text(
            "# Researcher answer\n\nA useful answer with evidence.\n",
            encoding="utf-8",
        )
    return run


def _parallel_outcome(question, *, state="completed", reason=None, run_id="run_1"):
    evidence = [{
        "url": "https://example.com/primary",
        "normalized_url": "example.com/primary",
        "excerpts": ["primary evidence with enough context"],
        "has_usable_excerpt": True,
        "source_shape": "structured_citation",
        "counted_depth": True,
        "exclusion_reason": None,
        "native_social_platforms": [],
        "counted_social": False,
    }] if state == "completed" else []
    return {
        "schema_version": 1,
        "provider": "parallel",
        "processor": "ultra",
        "state": state if state == "completed" else "unavailable",
        "available": state == "completed",
        "reason": reason,
        "run_id": run_id,
        "started_at": "2026-08-14T08:03:00+00:00",
        "finished_at": "2026-08-14T08:04:00+00:00",
        "duration_seconds": 60.0,
        "cost": {
            "currency": "USD", "amount": 0.3,
            "basis": "published list price per successful Task API run for ultra",
            "source": "https://docs.parallel.ai/getting-started/pricing",
            "processor_source": "https://docs.parallel.ai/task-api/guides/choose-a-processor",
            "actual_charge": None,
        },
        "scores": ({"depth": 1, "freshness_hours": None, "social_coverage": 0}
                   if state == "completed" else None),
        "raw_response": {"question": question, "output": {"content": "Parallel answer"}},
        "answer_markdown": "# Parallel answer\n\nA different useful answer.\n",
        "evidence": evidence,
    }


def _complete_forms(bundle, qid, *, scores_a=None, scores_b=None,
                    critical_a=False, critical_b=False):
    blind = Path(bundle) / "questions" / qid / "blind"
    audit = json.loads((blind / "ai-audit.json").read_text())
    audit["complete"] = True
    for label, critical in (("A", critical_a), ("B", critical_b)):
        side = audit["answers"][label]
        side.update({
            "load_bearing_claims_checked": True,
            "citation_fit_checked": True,
            "freshness_checked": True,
            "unsupported_recommendations": [],
            "omissions": [],
            "contradictions": [],
            "critical_error": {
                "confirmed": critical,
                "decision_changing": critical,
                "evidence_note": "wrong fact changes the decision" if critical else "",
            },
        })
    duel.write_private_json(blind / "ai-audit.json", audit)

    judgment = json.loads((blind / "owner-judgment.json").read_text())
    judgment["complete"] = True
    judgment["blind_mapping_not_consulted"] = True
    default_a = {name: 4 for name in duel.RUBRIC_DIMENSIONS}
    default_b = {name: 2 for name in duel.RUBRIC_DIMENSIONS}
    judgment["answers"]["A"]["scores"] = scores_a or default_a
    judgment["answers"]["B"]["scores"] = scores_b or default_b
    judgment["answers"]["A"]["notes"] = "reviewed"
    judgment["answers"]["B"]["notes"] = "reviewed"
    duel.write_private_json(blind / "owner-judgment.json", judgment)


class DuelTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.providers = {
            "parallel": True,
            "gemini": True,
            "grok": True,
            "openrouter": False,
            "perplexity": False,
            "telegram": True,
            "scrapecreators": False,
        }

    def tearDown(self):
        self.temp.cleanup()

    def init(self, now=None):
        return duel.init_bundle(
            SUITE_PATH, self.bundle, repo_root=ROOT,
            now=(lambda: now or _utc()),
            git_sha=lambda _root: "a" * 40,
            provider_probe=lambda: dict(self.providers),
            price_checked=True,
        )

    def snapshot(self, qid="q01"):
        question = duel.load_suite(SUITE_PATH)["questions"][int(qid[1:]) - 1]["text"]
        run = _researcher_run(self.root, question)
        return duel.snapshot_researcher(self.bundle, qid, run)


class TestFrozenSuite(DuelTestCase):
    def test_exact_five_questions_and_rules_are_committed(self):
        suite = duel.load_suite(SUITE_PATH)
        self.assertEqual([q["text"] for q in suite["questions"]], FROZEN_QUESTIONS)
        self.assertEqual([q["id"] for q in suite["questions"]],
                         ["q01", "q02", "q03", "q04", "q05"])
        self.assertEqual(suite["parallel"]["processor"], "ultra")
        self.assertEqual(suite["budgets"]["parallel_max"], 1.5)
        self.assertEqual(suite["budgets"]["researcher_max"], 10.0)
        self.assertEqual(suite["rules"]["per_question_win_margin"], 3)

    def test_invalid_runtime_suite_is_rejected(self):
        suite = json.loads(SUITE_PATH.read_text())
        suite["questions"].pop()
        bad = self.root / "bad.json"
        bad.write_text(json.dumps(suite))
        with self.assertRaisesRegex(duel.BenchmarkError, "exactly five"):
            duel.load_suite(bad)


class TestInit(DuelTestCase):
    def test_offline_preflight_records_revision_versions_deadline_and_booleans(self):
        metadata = self.init()
        self.assertEqual(metadata["git_sha"], "a" * 40)
        self.assertEqual(metadata["deadline_at"], "2026-08-15T08:00:00+00:00")
        preflight = json.loads((self.bundle / "preflight.json").read_text())
        self.assertEqual(preflight["providers"], self.providers)
        self.assertEqual(
            preflight["provider_routes"]["parallel"], "configured"
        )
        self.assertFalse(preflight["paid_authorized"])
        self.assertTrue(preflight["pricing_checked_for_live_run"])
        self.assertEqual(preflight["parallel"]["amount_per_successful_run"], 0.3)
        self.assertIn("python", metadata["versions"])
        frozen = json.loads((self.bundle / "suite.json").read_text())
        self.assertEqual([q["text"] for q in frozen["suite"]["questions"]],
                         FROZEN_QUESTIONS)
        self.assertEqual(metadata["suite_digest"], frozen["digest"])
        self.assertEqual(len(list((self.bundle / "questions").glob("q*"))), 5)
        if os.name == "posix":
            self.assertEqual(self.bundle.stat().st_mode & 0o777, 0o700)
            for path in self.bundle.rglob("*"):
                if path.is_file():
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600, path)

    def test_init_never_calls_a_provider(self):
        self.providers["parallel"] = False
        self.init()
        self.assertFalse(json.loads((self.bundle / "preflight.json").read_text())
                         ["providers"]["parallel"])

    def test_price_check_is_separate_from_init_and_from_paid_consent(self):
        duel.init_bundle(
            SUITE_PATH, self.bundle, repo_root=ROOT,
            now=lambda: _utc(), git_sha=lambda _root: "a" * 40,
            provider_probe=lambda: dict(self.providers), price_checked=False,
        )
        preflight = json.loads((self.bundle / "preflight.json").read_text())
        self.assertFalse(preflight["pricing_checked_for_live_run"])
        run = _researcher_run(self.root, FROZEN_QUESTIONS[0])
        duel.snapshot_researcher(self.bundle, "q01", run)
        with self.assertRaisesRegex(duel.BenchmarkError, "pricing"):
            duel.run_parallel(
                self.bundle, "q01", confirm_paid=True,
                executor=lambda q, p: _parallel_outcome(q), now=lambda: _utc(9),
            )

    def test_bundle_refuses_suite_tampering(self):
        self.init()
        frozen = json.loads((self.bundle / "suite.json").read_text())
        frozen["suite"]["questions"][0]["text"] = "changed"
        duel.write_private_json(self.bundle / "suite.json", frozen)
        with self.assertRaisesRegex(duel.BenchmarkError, "digest"):
            duel.load_bundle(self.bundle)

    def test_bundle_refuses_tampering_even_if_local_digests_are_rewritten(self):
        self.init()
        frozen = json.loads((self.bundle / "suite.json").read_text())
        frozen["suite"]["questions"][0]["text"] = "convenient replacement"
        forged = duel._digest_json(frozen["suite"])
        frozen["digest"] = forged
        metadata = json.loads((self.bundle / "bundle.json").read_text())
        metadata["suite_digest"] = forged
        duel.write_private_json(self.bundle / "suite.json", frozen)
        duel.write_private_json(self.bundle / "bundle.json", metadata)
        with self.assertRaisesRegex(duel.BenchmarkError, "committed duel-v1"):
            duel.load_bundle(self.bundle)


class TestResearcherSnapshot(DuelTestCase):
    def test_complete_run_is_copied_scored_and_immutable(self):
        self.init()
        receipt = self.snapshot()
        self.assertEqual(receipt["question_id"], "q01")
        self.assertEqual(receipt["scores"]["depth"], 1)
        self.assertEqual(receipt["scores"]["social_coverage"], 1)
        self.assertEqual(receipt["duration_seconds"], 120.0)
        self.assertTrue((self.bundle / receipt["answer_path"]).is_file())
        self.assertTrue(all(not Path(path).is_absolute()
                            for path in receipt["files"]))
        with self.assertRaisesRegex(duel.BenchmarkError, "already frozen"):
            self.snapshot()

    def test_incomplete_or_mismatched_run_is_rejected(self):
        self.init()
        question = FROZEN_QUESTIONS[0]
        incomplete = _researcher_run(self.root, question, complete=False)
        with self.assertRaisesRegex(duel.BenchmarkError, "synthesis"):
            duel.snapshot_researcher(self.bundle, "q01", incomplete)
        mismatched = _researcher_run(self.root, question, topic="another question")
        with self.assertRaisesRegex(duel.BenchmarkError, "exact frozen question"):
            duel.snapshot_researcher(self.bundle, "q01", mismatched)

    def test_snapshot_must_be_captured_inside_the_frozen_24_hour_window(self):
        self.init()
        run = _researcher_run(self.root, FROZEN_QUESTIONS[0])
        with self.assertRaisesRegex(duel.BenchmarkError, "24-hour"):
            duel.snapshot_researcher(
                self.bundle, "q01", run,
                now=lambda: _utc() + timedelta(hours=25),
            )

    def test_copied_run_redacts_known_secret_and_personal_absolute_path(self):
        self.init()
        secret = "duel_test_secret_value_123456789"
        run = _researcher_run(self.root, FROZEN_QUESTIONS[0])
        (run / "grok-x.md").write_text(
            f"secret={secret}\npath=/Users/example/private/research.md\n",
            encoding="utf-8",
        )
        with unittest.mock.patch.dict(os.environ, {"DUEL_API_KEY": secret}):
            receipt = duel.snapshot_researcher(self.bundle, "q01", run)
        copied = "\n".join(
            (self.bundle / path).read_text(encoding="utf-8")
            for path in receipt["files"]
        )
        self.assertNotIn(secret, copied)
        self.assertNotIn("/Users/example", copied)

    def test_researcher_budget_is_cumulative_across_questions(self):
        self.init()
        for index, amount in ((1, 6.0), (2, 5.0)):
            run = _researcher_run(self.root, FROZEN_QUESTIONS[index - 1])
            manifest_path = run / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["costs"] = [{"provider": "social-vendor", "amount": amount,
                                  "currency": "USD", "basis": "reported call"}]
            manifest_path.write_text(json.dumps(manifest))
            if index == 1:
                duel.snapshot_researcher(self.bundle, "q01", run)
            else:
                with self.assertRaisesRegex(duel.BenchmarkError, "cumulative"):
                    duel.snapshot_researcher(self.bundle, "q02", run)

    def test_technical_failure_trace_is_preserved_before_one_success(self):
        self.init()
        failed_run = _researcher_run(self.root, FROZEN_QUESTIONS[0], complete=False)
        failure = duel.snapshot_researcher(
            self.bundle, "q01", failed_run,
            technical_failure_reason="session transport stopped before synthesis",
        )
        self.assertEqual(failure["state"], "technical_failure")
        self.assertTrue((self.bundle / failure["attempt_path"]).is_dir())
        completed = self.snapshot()
        self.assertEqual(completed["state"], "completed")
        self.assertTrue((self.bundle / failure["attempt_path"]).is_dir())

    def test_completed_answer_cannot_be_reclassified_as_technical_failure(self):
        self.init()
        run = _researcher_run(self.root, FROZEN_QUESTIONS[0])
        with self.assertRaisesRegex(duel.BenchmarkError, "poor answer"):
            duel.snapshot_researcher(
                self.bundle, "q01", run,
                technical_failure_reason="I dislike the answer",
            )


class TestParallelGateAndAttempts(DuelTestCase):
    def test_without_confirm_paid_executor_cannot_run(self):
        self.init()
        self.snapshot()
        calls = []
        result = duel.run_parallel(
            self.bundle, "q01", confirm_paid=False,
            executor=lambda *args, **kwargs: calls.append((args, kwargs)),
            now=lambda: _utc(9),
        )
        self.assertEqual(result["state"], "preflight_only")
        self.assertEqual(calls, [])
        self.assertEqual(list((self.bundle / "questions/q01/parallel").glob("attempt-*")), [])

    def test_success_is_preserved_and_cannot_be_retried_for_quality(self):
        self.init()
        self.snapshot()
        calls = []

        def execute(question, processor):
            calls.append((question, processor))
            return _parallel_outcome(question)

        attempt = duel.run_parallel(
            self.bundle, "q01", confirm_paid=True, executor=execute,
            now=lambda: _utc(9),
        )
        self.assertEqual(attempt["state"], "completed")
        self.assertEqual(calls, [(FROZEN_QUESTIONS[0], "ultra")])
        self.assertTrue((self.bundle / attempt["outcome_path"]).is_file())
        with self.assertRaisesRegex(duel.BenchmarkError, "successful attempt"):
            duel.run_parallel(
                self.bundle, "q01", confirm_paid=True,
                retry_technical=True, executor=execute, now=lambda: _utc(9),
            )

    def test_only_technical_failure_permits_preserved_retry(self):
        self.init()
        self.snapshot()
        failed = duel.run_parallel(
            self.bundle, "q01", confirm_paid=True,
            executor=lambda q, p: _parallel_outcome(
                q, state="failed", reason="unavailable - timeout", run_id="run_fail"
            ),
            now=lambda: _utc(9),
        )
        self.assertEqual(failed["state"], "technical_failure")
        with self.assertRaisesRegex(duel.BenchmarkError, "retry-technical"):
            duel.run_parallel(
                self.bundle, "q01", confirm_paid=True,
                executor=lambda q, p: _parallel_outcome(q), now=lambda: _utc(9),
            )
        retried = duel.run_parallel(
            self.bundle, "q01", confirm_paid=True, retry_technical=True,
            executor=lambda q, p: _parallel_outcome(q, run_id="run_retry"),
            now=lambda: _utc(9),
        )
        self.assertEqual(retried["attempt_number"], 2)
        self.assertTrue((self.bundle / failed["attempt_path"]).is_dir())
        self.assertTrue((self.bundle / retried["attempt_path"]).is_dir())

    def test_parallel_requires_snapshot_open_window_and_available_provider(self):
        self.init()
        with self.assertRaisesRegex(duel.BenchmarkError, "Researcher"):
            duel.run_parallel(self.bundle, "q01", confirm_paid=True,
                              executor=lambda q, p: _parallel_outcome(q), now=lambda: _utc(9))
        self.snapshot()
        with self.assertRaisesRegex(duel.BenchmarkError, "24-hour"):
            duel.run_parallel(
                self.bundle, "q01", confirm_paid=True,
                executor=lambda q, p: _parallel_outcome(q),
                now=lambda: _utc() + timedelta(hours=25),
            )


class TestBlindAndReport(DuelTestCase):
    def _complete_pair(self, qid="q01", rng=None):
        self.snapshot(qid)
        duel.run_parallel(
            self.bundle, qid, confirm_paid=True,
            executor=lambda q, p: _parallel_outcome(q, run_id="run_" + qid),
            now=lambda: _utc(9),
        )
        return duel.blind_question(self.bundle, qid, rng=rng or random.Random(1))

    def test_blinding_is_stable_private_and_not_regenerated(self):
        self.init()
        blind = self._complete_pair(rng=random.Random(7))
        mapping = json.loads((self.bundle / blind["mapping_path"]).read_text())
        self.assertEqual(set(mapping["labels"]), {"A", "B"})
        expected_a = "researcher" if random.Random(7).random() < 0.5 else "parallel"
        self.assertEqual(mapping["labels"]["A"], expected_a)
        for name in ("answer-a.md", "answer-b.md"):
            text = (self.bundle / "questions/q01/blind" / name).read_text()
            self.assertNotIn("# Researcher", text)
            self.assertNotIn("# Parallel", text)
        if os.name == "posix":
            self.assertEqual((self.bundle / blind["mapping_path"]).stat().st_mode & 0o777,
                             0o600)
        with self.assertRaisesRegex(duel.BenchmarkError, "already exists"):
            duel.blind_question(self.bundle, "q01", rng=random.Random(7))

    def test_report_refuses_incomplete_pairs_audits_and_judgments(self):
        self.init()
        with self.assertRaisesRegex(duel.BenchmarkError, "q01"):
            duel.build_report(self.bundle)
        self._complete_pair()
        with self.assertRaisesRegex(duel.BenchmarkError, "audit"):
            duel.build_report(self.bundle)

    def test_margin_mapping_and_critical_veto_are_derived(self):
        self.init()
        self._complete_pair()
        mapping = json.loads((self.bundle / "questions/q01/blind/mapping.json").read_text())
        _complete_forms(self.bundle, "q01", critical_a=True)
        result = duel.derive_question_result(self.bundle, "q01")
        self.assertEqual(result["quality_totals"], {"A": 20, "B": 10})
        self.assertEqual(result["margin"], 10)
        self.assertEqual(result["winner_label"], "tie")
        self.assertEqual(result["winner"], "tie")
        self.assertEqual(mapping["labels"]["A"] in ("researcher", "parallel"), True)

    def test_small_difference_is_tie(self):
        self.init()
        self._complete_pair()
        scores_a = {name: 3 for name in duel.RUBRIC_DIMENSIONS}
        scores_b = dict(scores_a)
        scores_b["usefulness"] = 2
        _complete_forms(self.bundle, "q01", scores_a=scores_a, scores_b=scores_b)
        self.assertEqual(duel.derive_question_result(self.bundle, "q01")["winner"],
                         "tie")

    def test_out_of_range_or_missing_score_refuses_result(self):
        self.init()
        self._complete_pair()
        _complete_forms(self.bundle, "q01")
        path = self.bundle / "questions/q01/blind/owner-judgment.json"
        judgment = json.loads(path.read_text())
        judgment["answers"]["A"]["scores"]["freshness"] = 5
        duel.write_private_json(path, judgment)
        with self.assertRaisesRegex(duel.BenchmarkError, "0 to 4"):
            duel.derive_question_result(self.bundle, "q01")


class TestMockedFiveQuestionEndToEnd(DuelTestCase):
    def test_complete_bundle_reports_winner_and_keeps_cost_time_separate(self):
        self.init()
        for index, question in enumerate(FROZEN_QUESTIONS, start=1):
            qid = f"q{index:02d}"
            run = _researcher_run(self.root, question)
            duel.snapshot_researcher(self.bundle, qid, run)
            duel.run_parallel(
                self.bundle, qid, confirm_paid=True,
                executor=lambda q, p, qid=qid: _parallel_outcome(q, run_id="run_" + qid),
                now=lambda: _utc(9),
            )
            duel.blind_question(self.bundle, qid, rng=random.Random(index))
            mapping = json.loads(
                (self.bundle / f"questions/{qid}/blind/mapping.json").read_text()
            )
            # Make Researcher win every fixture regardless of whether it is A or B.
            researcher_label = next(
                label for label, participant in mapping["labels"].items()
                if participant == "researcher"
            )
            high = {name: 4 for name in duel.RUBRIC_DIMENSIONS}
            low = {name: 1 for name in duel.RUBRIC_DIMENSIONS}
            _complete_forms(
                self.bundle, qid,
                scores_a=high if researcher_label == "A" else low,
                scores_b=high if researcher_label == "B" else low,
            )

        self.assertEqual(
            json.loads((self.bundle / "bundle.json").read_text())["state"],
            "ready_for_review",
        )
        report = duel.build_report(self.bundle)
        self.assertEqual(report["overall"]["winner"], "researcher")
        self.assertEqual(report["overall"]["wins"]["researcher"], 5)
        self.assertEqual(len(report["questions"]), 5)
        self.assertNotIn("cost", report["questions"][0]["quality_totals"])
        self.assertEqual(report["economics"]["parallel_list_cost"], 1.5)
        self.assertEqual(report["economics"]["parallel_duration_seconds"], 300.0)
        self.assertTrue((self.bundle / "report.json").is_file())
        self.assertTrue((self.bundle / "report.md").is_file())
        self.assertEqual(json.loads((self.bundle / "bundle.json").read_text())["state"],
                         "complete")

    def test_two_two_one_is_an_overall_tie(self):
        self.init()
        desired = ["researcher", "researcher", "parallel", "parallel", "tie"]
        for index, (question, desired_winner) in enumerate(
            zip(FROZEN_QUESTIONS, desired), start=1
        ):
            qid = f"q{index:02d}"
            duel.snapshot_researcher(
                self.bundle, qid, _researcher_run(self.root, question)
            )
            duel.run_parallel(
                self.bundle, qid, confirm_paid=True,
                executor=lambda q, p, qid=qid: _parallel_outcome(q, run_id="run_" + qid),
                now=lambda: _utc(9),
            )
            duel.blind_question(self.bundle, qid, rng=random.Random(index + 20))
            mapping = json.loads(
                (self.bundle / f"questions/{qid}/blind/mapping.json").read_text()
            )["labels"]
            high = {name: 4 for name in duel.RUBRIC_DIMENSIONS}
            low = {name: 1 for name in duel.RUBRIC_DIMENSIONS}
            tied = {name: 3 for name in duel.RUBRIC_DIMENSIONS}
            if desired_winner == "tie":
                scores = {"A": tied, "B": tied}
            else:
                winner_label = next(
                    label for label, participant in mapping.items()
                    if participant == desired_winner
                )
                scores = {
                    "A": high if winner_label == "A" else low,
                    "B": high if winner_label == "B" else low,
                }
            _complete_forms(
                self.bundle, qid, scores_a=scores["A"], scores_b=scores["B"]
            )
        report = duel.build_report(self.bundle)
        self.assertEqual(report["overall"]["winner"], "tie")
        self.assertEqual(
            report["overall"]["wins"],
            {"researcher": 2, "parallel": 2, "tie": 1},
        )


if __name__ == "__main__":
    unittest.main()

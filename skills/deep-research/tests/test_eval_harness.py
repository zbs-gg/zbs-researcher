"""U7 — eval harness (Beast vs web-index baseline).

The scoring core is pure over two result sets: depth counts DISTINCT quoted
primary-thread URLs (dedup by normalized URL), freshness is the median item
age in hours (None when unknown), social coverage counts distinct NATIVE
platforms reached (plain web pages do not count). The baseline side degrades
honestly to an "unavailable" row when no web-index key is configured.

All network is mocked — no live calls, no paid calls.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
HARNESS = SCRIPTS / "eval_harness.py"

_scripts_path = str(SCRIPTS)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eval_harness = _load("eval_harness_under_test", HARNESS)


QUOTED_MD = """# Grok — live X for: mem0
- **Thread on mem0 restarts** — 3h ago
  - https://x.com/somebody/status/123
  - @somebody: "mem0 forgets everything when the vector store restarts"
- **Same thread, other link form** — 3h ago
  - http://www.x.com/somebody/status/123/
  - @somebody: "still broken after the 0.2 upgrade, filing an issue"
- **A bare link with no voice around it**
  - https://x.com/lurker/status/999
"""


def _beast_dir(tmp, *, with_manifest=True):
    """Three native-platform result files + a manifest with fresh provenance."""
    run = Path(tmp) / "beast-run"
    run.mkdir()
    (run / "grok.md").write_text(QUOTED_MD, encoding="utf-8")
    (run / "telegram.md").write_text(
        "# Telegram — channels for: mem0\n"
        "- **@mem0_users** — 5h ago\n"
        "  - https://t.me/mem0_users/42\n"
        '  - @maria: "we rolled back to 0.1 in prod, the retriever loops"\n',
        encoding="utf-8",
    )
    (run / "reddit.md").write_text(
        "# Reddit — top posts for: mem0\n"
        "- **mem0 in production?** — 122 pts\n"
        "  - https://reddit.com/r/LocalLLaMA/abc\n"
        '  - > "the memory dedup silently drops user facts, took us a week to find"\n',
        encoding="utf-8",
    )
    # An errored neighbor must not contribute evidence.
    (run / "bluesky.ERROR.md").write_text(
        "error, but with a link https://bsky.app/broken and a \"quoted excerpt line here\"\n",
        encoding="utf-8",
    )
    if with_manifest:
        (run / "manifest.json").write_text(
            json.dumps(
                {
                    "topic": "mem0",
                    "channels": {
                        "grok": {"status": "ok"},
                        "telegram": {"status": "ok"},
                        "reddit": {"status": "ok"},
                        "bluesky": {"status": "error", "error": "HTTP 502"},
                    },
                    "provenance": {
                        # Real manifests write "freshness_hours" (provenance_record).
                        "grok": {"source": "grok", "freshness_hours": 3},
                        "telegram": {"source": "telegram", "freshness_hours": 5},
                        "reddit": {"source": "reddit", "freshness_hours": 7},
                    },
                }
            ),
            encoding="utf-8",
        )
    return run


def _stale_brave_payload():
    """One stale plain-web result — what a web-index pass hands back."""
    stale = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "web": {
            "results": [
                {
                    "url": "https://example.com/blog/mem0-review",
                    "title": "mem0 review",
                    "description": "A blog post about memory layers.",
                    "page_age": stale,
                }
            ]
        }
    }


class TestExtractEvidence(unittest.TestCase):
    def test_links_found_with_quote_flags(self):
        items = eval_harness.extract_evidence(QUOTED_MD)
        by_url = {it["url"]: it["has_quote"] for it in items}
        self.assertTrue(by_url["https://x.com/somebody/status/123"])
        self.assertFalse(by_url["https://x.com/lurker/status/999"])
        self.assertEqual(len(items), 3)

    def test_no_links_no_items(self):
        self.assertEqual(eval_harness.extract_evidence("just prose, no links"), [])


class TestScoreDepth(unittest.TestCase):
    def test_dedup_by_normalized_url(self):
        # http/https, www., and trailing-slash variants are ONE thread.
        items = [
            {"url": "https://x.com/somebody/status/123", "has_quote": True},
            {"url": "http://www.x.com/somebody/status/123/", "has_quote": True},
            {"url": "https://t.me/mem0_users/42", "has_quote": True},
        ]
        self.assertEqual(eval_harness.score_depth(items), 2)

    def test_quote_less_link_not_counted(self):
        items = [
            {"url": "https://x.com/lurker/status/999", "has_quote": False},
            {"url": "https://t.me/mem0_users/42", "has_quote": True},
        ]
        self.assertEqual(eval_harness.score_depth(items), 1)

    def test_from_fixture_markdown(self):
        # The quoted fixture: one thread quoted twice (two URL spellings) + one
        # quote-less link -> depth 1.
        items = eval_harness.extract_evidence(QUOTED_MD)
        self.assertEqual(eval_harness.score_depth(items), 1)


class TestScoreFreshness(unittest.TestCase):
    def test_median_odd(self):
        self.assertEqual(eval_harness.score_freshness([100, 2, 10]), 10)

    def test_median_even(self):
        self.assertEqual(eval_harness.score_freshness([2, 4, 8, 100]), 6.0)

    def test_unknown_ages_are_none(self):
        self.assertIsNone(eval_harness.score_freshness([]))
        self.assertIsNone(eval_harness.score_freshness(None))
        self.assertIsNone(eval_harness.score_freshness([None, None]))

    def test_unknowns_skipped_not_zeroed(self):
        self.assertEqual(eval_harness.score_freshness([None, 4, 8]), 6.0)


class TestManifestFreshnessKey(unittest.TestCase):
    """Regression: the Beast side read the wrong provenance key ("freshness" /
    "newest_item_age_hours") while provenance_record writes "freshness_hours",
    so Beast freshness was permanently "unknown". Read the real key first."""

    def _ages(self, provenance):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "manifest.json").write_text(
                json.dumps({"channels": {}, "provenance": provenance}),
                encoding="utf-8",
            )
            _sources, ages = eval_harness._manifest_sources_and_ages(d)
        return ages

    def test_reads_freshness_hours_key(self):
        ages = self._ages([
            {"source": "grok", "freshness_hours": 22.4},
            {"source": "hackernews", "freshness_hours": 3465.7},
        ])
        self.assertEqual(sorted(ages), [22.4, 3465.7])

    def test_falls_back_to_legacy_keys(self):
        ages = self._ages([
            {"source": "a", "freshness": 5},
            {"source": "b", "newest_item_age_hours": 9},
        ])
        self.assertEqual(sorted(ages), [5, 9])

    def test_none_ages_skipped(self):
        ages = self._ages([
            {"source": "grok", "freshness_hours": None},
            {"source": "hn", "freshness_hours": 10},
        ])
        self.assertEqual(ages, [10])


class TestScoreSocialCoverage(unittest.TestCase):
    def test_native_platforms_only(self):
        sources = ["grok", "telegram", "reddit", "github", "hackernews", "example.com"]
        self.assertEqual(eval_harness.score_social_coverage(sources), 3)

    def test_domains_and_urls_map_to_platforms(self):
        sources = [
            "twitter.com",
            "https://www.reddit.com/r/LocalLLaMA/abc",
            "news.ycombinator.com",  # a web page, not a native social platform
            "https://example.com/blog",
        ]
        self.assertEqual(eval_harness.score_social_coverage(sources), 2)

    def test_x_and_twitter_are_one_platform(self):
        self.assertEqual(
            eval_harness.score_social_coverage(["x.com", "twitter.com", "grok"]), 1
        )

    def test_empty(self):
        self.assertEqual(eval_harness.score_social_coverage([]), 0)


class TestBeastVsBaseline(unittest.TestCase):
    """The flagship comparison: fresh multi-platform Beast run vs one stale
    plain-web baseline result -> Beast wins on all three axes."""

    def test_beast_wins_all_three_axes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)

            def fake_fetch(url, headers=None, timeout=20):
                return _stale_brave_payload()

            with unittest.mock.patch.object(
                eval_harness, "_read_brave_key", return_value="test-key-not-real-0000"
            ):
                row = eval_harness.run_eval("mem0 problems", run, fetch=fake_fetch)

        beast, baseline = row["beast"], row["baseline"]
        self.assertIsInstance(baseline, dict)
        # depth: 3 distinct quoted native threads vs 1 snippet-backed web page
        self.assertGreater(beast["depth"], baseline["depth"])
        # freshness: fresher = LOWER median age
        self.assertLess(beast["freshness_hours"], baseline["freshness_hours"])
        self.assertAlmostEqual(beast["freshness_hours"], 5)
        # social coverage: 3 native platforms vs 0 (a blog is not native)
        self.assertGreater(beast["social_coverage"], baseline["social_coverage"])
        self.assertEqual(beast["social_coverage"], 3)
        self.assertEqual(baseline["social_coverage"], 0)

    def test_error_files_do_not_contribute(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            scores = eval_harness.score_beast_dir(run)
        # bluesky.ERROR.md carries a quoted link; it must not raise depth to 4
        # and the errored channel must not count as a reached platform.
        self.assertEqual(scores["depth"], 3)
        self.assertEqual(scores["social_coverage"], 3)


class TestNoKeyBaseline(unittest.TestCase):
    def test_honest_unavailable_row_no_crash_no_network(self):
        def boom(*args, **kwargs):
            raise AssertionError("network call attempted without a key")

        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            empty_secrets = Path(tmp) / "empty-secrets"
            empty_secrets.mkdir()
            env = {"DEEP_RESEARCH_SECRETS_DIR": str(empty_secrets), "BRAVE_API_KEY": ""}
            with unittest.mock.patch.dict(os.environ, env), \
                    unittest.mock.patch.object(eval_harness, "_get_json", boom), \
                    unittest.mock.patch("urllib.request.urlopen", boom):
                row = eval_harness.run_eval("mem0 problems", run)

        self.assertEqual(row["baseline"], "unavailable - no web-index key configured")
        # Beast still scored.
        self.assertEqual(row["beast"]["depth"], 3)
        self.assertEqual(row["beast"]["social_coverage"], 3)


PARALLEL_KEY = "prl_faketestkey_123456"


def _parallel_env(secrets_dir, **extra):
    """No host key may satisfy these tests, and no other route may leak in."""
    env = {
        "DEEP_RESEARCH_SECRETS_DIR": str(secrets_dir),
        "BRAVE_API_KEY": "",
        "PARALLEL_API_KEY": "",
    }
    env.update(extra)
    return env


class TestYouTubeCoverage(unittest.TestCase):
    """The youtube connector reads spoken content a web index cannot, so the
    coverage axis must credit it — and must agree with the provenance table,
    which already files youtube under 'partial'."""

    def test_youtube_counts_as_a_native_platform(self):
        for token in ("youtube", "youtube.com",
                      "https://www.youtube.com/watch?v=vD0E3EUb8-8",
                      "https://youtu.be/vD0E3EUb8-8"):
            with self.subTest(token=token):
                self.assertEqual(
                    eval_harness.score_social_coverage([token]), 1, token
                )

    def test_youtube_is_distinct_from_the_other_platforms(self):
        self.assertEqual(
            eval_harness.score_social_coverage(
                ["youtube", "reddit", "x.com", "t.me"]
            ),
            4,
        )

    def test_a_platforms_own_docs_are_not_that_platforms_conversation(self):
        """Caught while scoring a real opponent: help.x.com counted as
        "reached X natively". A help centre is a corporate publication a web
        index has in full — crediting it would score reading the manual as
        reading the room. (This lowers an opponent's number, which is why the
        reasoning has to stand on its own.)"""
        for host in ("https://help.x.com/en/using-x/x-timeline",
                     "https://developer.x.com/en/docs",
                     "https://blog.x.com/en_us/topics",
                     "https://support.reddit.com/hc/en-us"):
            with self.subTest(host=host):
                self.assertEqual(eval_harness.score_social_coverage([host]), 0, host)

    def test_the_real_platform_hosts_still_count(self):
        self.assertEqual(
            eval_harness.score_social_coverage(
                ["https://x.com/a/status/1", "https://old.reddit.com/r/x/comments/2"]
            ),
            2,
        )

    def test_fully_indexed_forums_still_earn_nothing(self):
        self.assertEqual(
            eval_harness.score_social_coverage(
                ["https://news.ycombinator.com/item?id=1", "https://example.com"]
            ),
            0,
        )


class TestParallelIsNeverImplicit(unittest.TestCase):
    """A configured key is not consent to spend it. The eval must stay free
    unless the caller explicitly asks for the paid opponent."""

    def test_configured_key_alone_never_triggers_a_paid_call(self):
        def boom(*args, **kwargs):
            raise AssertionError("paid Parallel call attempted without --baseline")

        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            secrets = Path(tmp) / "secrets"
            secrets.mkdir()
            (secrets / "parallel-key.txt").write_text(PARALLEL_KEY, encoding="utf-8")
            env = _parallel_env(secrets)
            with unittest.mock.patch.dict(os.environ, env), \
                    unittest.mock.patch.object(eval_harness, "_post_json", boom), \
                    unittest.mock.patch.object(eval_harness, "_get_json", boom), \
                    unittest.mock.patch("urllib.request.urlopen", boom):
                row = eval_harness.run_eval("mem0 problems", run)

        self.assertEqual(row["baseline_kind"], "web-index")
        self.assertEqual(row["baseline"], "unavailable - no web-index key configured")
        self.assertIsNone(row["baseline_processor"])
        self.assertIsNone(row["baseline_cost"]["amount"])

    def test_cli_default_stays_free_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            secrets = Path(tmp) / "secrets"
            secrets.mkdir()
            (secrets / "parallel-key.txt").write_text(PARALLEL_KEY, encoding="utf-8")
            stdout = io.StringIO()
            with unittest.mock.patch.dict(os.environ, _parallel_env(secrets)), \
                    contextlib.redirect_stdout(stdout):
                rc = eval_harness.main(["q", "--beast-dir", str(run)])
        self.assertEqual(rc, 0)
        self.assertIn("was NOT used", stdout.getvalue())


class TestParallelBaseline(unittest.TestCase):
    def _run(self, tmp, result, post=None, **kwargs):
        secrets = Path(tmp) / "secrets"
        secrets.mkdir(exist_ok=True)
        (secrets / "parallel-key.txt").write_text(PARALLEL_KEY, encoding="utf-8")
        posted = []

        def fake_post(url, payload, headers=None, timeout=60):
            posted.append((url, payload, dict(headers or {})))
            return {"run_id": "run_abc"}

        announce = kwargs.pop("announce", lambda _message: None)
        with unittest.mock.patch.dict(os.environ, _parallel_env(secrets)):
            scores = eval_harness.run_parallel_baseline(
                "how to run twitter now",
                post=post or fake_post,
                fetch=lambda url, headers=None, timeout=20: result,
                sleep=lambda _s: None,
                announce=announce,
                **kwargs,
            )
        return scores, posted

    def test_key_travels_in_the_header_never_the_url(self):
        result = {"output": {"content": 'x\n- https://x.com/a/status/1\n  "said it"'}}
        with tempfile.TemporaryDirectory() as tmp:
            _, posted = self._run(tmp, result)
        url, payload, headers = posted[0]
        self.assertEqual(url, "https://api.parallel.ai/v1/tasks/runs")
        self.assertEqual(headers["x-api-key"], PARALLEL_KEY)
        self.assertNotIn(PARALLEL_KEY, url)
        self.assertEqual(payload["processor"], "ultra")
        self.assertEqual(payload["input"], "how to run twitter now")

    def test_text_output_is_scored_on_the_same_axes_as_beast(self):
        content = (
            "Report\n"
            '- https://x.com/alice/status/1\n  "engagement fell off a cliff"\n'
            '- https://reddit.com/r/Twitter/comments/2\n  "same here"\n'
            "- https://example.com/blog\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            scores, _ = self._run(tmp, {"output": {"content": content}})
        # two quoted threads; the unquoted blog link is a pointer, not evidence
        self.assertEqual(scores["depth"], 2)
        self.assertEqual(scores["social_coverage"], 2)

    def test_structured_citations_still_count_as_evidence(self):
        """An `auto`-shaped answer keeps its links in a sibling field; scoring
        only the prose would report it as evidence-free."""
        result = {
            "output": {
                "content": {"answer": "things changed"},
                "basis": [{
                    "citations": [
                        {"url": "https://x.com/bob/status/9",
                         "excerpt": "my reach fell off a cliff in March"},
                        {"url": "https://reddit.com/r/Twitter/comments/2",
                         "excerpt": "same here, impressions down 80 percent"},
                        # Fully web-indexed: a real citation, but it earns no
                        # coverage credit for either side.
                        {"url": "https://news.ycombinator.com/item?id=1",
                         "excerpt": "the ranking model changed again"},
                    ]
                }],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            scores, _ = self._run(tmp, result)
        self.assertEqual(scores["depth"], 3)
        self.assertEqual(scores["social_coverage"], 2)

    def test_the_live_excerpts_field_is_not_dropped(self):
        """Regression, caught in a real duel: the API sends `excerpts` (a
        list). Reading only a singular `excerpt` silently threw away every
        quote the opponent supplied and scored it at zero depth — which would
        have published a rigged benchmark."""
        result = {
            "output": {
                "content": "answer",
                "basis": [{
                    "citations": [
                        {"url": "https://help.x.com/en/using-x/x-timeline",
                         "excerpts": ["For you serves posts from accounts and "
                                      "Topics you follow as well as recommended posts."]},
                        {"url": "https://help.x.com/en/rules-and-policies/x-limits",
                         "excerpts": ["Posts: 50 original posts and 200 replies per day.",
                                      "Direct Messages daily limit is 500 messages sent."]},
                    ]
                }],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            scores, _ = self._run(tmp, result)
        self.assertEqual(scores["depth"], 2)

    def test_duplicate_excerpt_shapes_do_not_inflate_depth(self):
        result = {
            "output": {
                "content": "answer",
                "basis": [{"citations": [
                    {
                        "url": "https://x.com/a/status/1",
                        "excerpt": "the same first-hand report",
                        "excerpts": ["the same first-hand report"],
                    },
                    {
                        "url": "https://x.com/a/status/1",
                        "excerpts": ["a second excerpt from the same thread"],
                    },
                ]}],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            scores, _ = self._run(tmp, result)
        self.assertEqual(scores["depth"], 1)

    def test_a_citation_with_no_excerpt_is_a_pointer_not_evidence(self):
        result = {
            "output": {
                "content": "answer",
                "basis": [{"citations": [
                    {"url": "https://help.x.com/en/using-x/x-timeline", "excerpts": []},
                ]}],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            scores, _ = self._run(tmp, result)
        self.assertEqual(scores["depth"], 0)

    def test_missing_key_is_honest_and_makes_no_call(self):
        def boom(*args, **kwargs):
            raise AssertionError("called without a key")

        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with unittest.mock.patch.dict(os.environ, _parallel_env(empty)):
                scores = eval_harness.run_parallel_baseline(
                    "q", post=boom, fetch=boom, sleep=boom,
                    announce=lambda _message: None,
                )
        self.assertIsInstance(scores, str)
        self.assertIn("no parallel key", scores)

    def test_a_failed_start_degrades_without_leaking_the_key(self):
        def failing_post(*args, **kwargs):
            raise urllib.error.HTTPError("u", 401, "Unauthorized", None, None)

        with tempfile.TemporaryDirectory() as tmp:
            scores, _ = self._run(tmp, {}, post=failing_post)
        self.assertIsInstance(scores, str)
        self.assertIn("could not start", scores)
        self.assertNotIn(PARALLEL_KEY, scores)

    def test_a_run_that_never_finishes_says_so_instead_of_scoring_zero(self):
        def never_ready(url, headers=None, timeout=20):
            raise urllib.error.HTTPError(url, 404, "not ready", None, None)

        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp) / "secrets"
            secrets.mkdir()
            (secrets / "parallel-key.txt").write_text(PARALLEL_KEY, encoding="utf-8")
            clock = iter([0.0, 0.0, 10_000.0, 10_000.0])
            with unittest.mock.patch.dict(os.environ, _parallel_env(secrets)):
                scores = eval_harness.run_parallel_baseline(
                    "q",
                    post=lambda *a, **k: {"run_id": "r"},
                    fetch=never_ready,
                    sleep=lambda _s: None,
                    now=lambda: next(clock),
                    announce=lambda _message: None,
                )
        self.assertIsInstance(scores, str)
        self.assertIn("did not finish", scores)

    def test_empty_result_is_not_reported_as_a_zero_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            scores, _ = self._run(tmp, {"output": {"content": "   "}})
        self.assertIsInstance(scores, str)
        self.assertIn("empty result", scores)

    def test_price_is_stated_immediately_before_the_call(self):
        events = []

        def announce(note):
            self.assertIn("$0.3", note)
            self.assertIn("ultra", note)
            events.append("price")

        def post(*args, **kwargs):
            events.append("post")
            return {"run_id": "r"}

        with tempfile.TemporaryDirectory() as tmp:
            self._run(
                tmp,
                {"output": {"content": "answer"}},
                post=post,
                announce=announce,
            )
        self.assertEqual(events, ["price", "post"])

    def test_direct_call_rejects_unpriced_processor_without_network(self):
        def boom(*args, **kwargs):
            raise AssertionError("paid call attempted for an unpriced processor")

        result = eval_harness.run_parallel_baseline(
            "q", processor="ultra8x", post=boom, fetch=boom, sleep=boom,
            announce=boom,
        )
        self.assertIn("not an allowed priced", result)

    def test_sub_cent_prices_are_not_rounded_up(self):
        """At two decimals a $0.005 run prints as "$0.01" — a small lie about
        money is still a lie about money."""
        note = eval_harness.parallel_price_note("lite")
        self.assertIn("$0.005", note)

    def test_unknown_processor_says_unknown_rather_than_guessing(self):
        self.assertIn("price unknown", eval_harness.parallel_price_note("zzz"))

    def test_cli_rejects_unpriced_processor_before_any_paid_call(self):
        def boom(*args, **kwargs):
            raise AssertionError("paid call attempted for an unpriced processor")

        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            with unittest.mock.patch.object(eval_harness, "_post_json", boom), \
                    contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as raised:
                eval_harness.main([
                    "q", "--beast-dir", str(run),
                    "--baseline", "parallel", "--processor", "ultra8x",
                ])
        self.assertEqual(raised.exception.code, 2)

    def test_table_names_the_opponent_that_actually_ran(self):
        row = {
            "question": "q", "baseline_kind": "parallel",
            "baseline_cost": {
                "currency": "USD", "amount": 0.3,
                "basis": "published list price per successful run",
            },
            "beast": {"depth": 5, "freshness_hours": 2.0, "social_coverage": 4},
            "baseline": {"depth": 3, "freshness_hours": None, "social_coverage": 1},
        }
        table = eval_harness.format_table(row)
        self.assertIn("Beast vs parallel baseline", table)
        self.assertNotIn("web-index", table)
        self.assertIn("parallel list price: $0.3", table)

    def test_parallel_row_records_processor_and_list_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            scores = {"depth": 1, "freshness_hours": None, "social_coverage": 1}
            with unittest.mock.patch.object(
                eval_harness, "run_parallel_baseline", return_value=scores
            ):
                row = eval_harness.run_eval(
                    "q", run, baseline="parallel", processor="pro"
                )
        self.assertEqual(row["baseline_processor"], "pro")
        self.assertEqual(row["baseline_cost"]["amount"], 0.10)
        self.assertEqual(
            row["baseline_cost"]["basis"],
            "published list price per successful run",
        )


class TestEvalLog(unittest.TestCase):
    def test_row_appended_and_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            out_dir = Path(tmp) / "eval-out"
            empty_secrets = Path(tmp) / "empty-secrets"
            empty_secrets.mkdir()
            env = {"DEEP_RESEARCH_SECRETS_DIR": str(empty_secrets), "BRAVE_API_KEY": ""}
            stdout = io.StringIO()
            with unittest.mock.patch.dict(os.environ, env), \
                    contextlib.redirect_stdout(stdout):
                rc = eval_harness.main(
                    ["mem0 problems", "--beast-dir", str(run), "--out", str(out_dir)]
                )
            self.assertEqual(rc, 0)
            ledger = out_dir / "eval-log.jsonl"
            lines = ledger.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["question"], "mem0 problems")
            self.assertIn("ts", row)
            self.assertEqual(row["beast"]["depth"], 3)
            self.assertEqual(row["baseline"], "unavailable - no web-index key configured")
            # The comparison table reached stdout.
            self.assertIn("depth", stdout.getvalue())

    def test_default_ledger_lands_in_beast_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _beast_dir(tmp)
            empty_secrets = Path(tmp) / "empty-secrets"
            empty_secrets.mkdir()
            env = {"DEEP_RESEARCH_SECRETS_DIR": str(empty_secrets), "BRAVE_API_KEY": ""}
            with unittest.mock.patch.dict(os.environ, env), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = eval_harness.main(["mem0 problems", "--beast-dir", str(run)])
            self.assertEqual(rc, 0)
            self.assertTrue((run / "eval-log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

"""U5 — GitHub issues + comments as a first-class scored source (R11).

channel_github_issues pulls top issues by reactions via the search API
(shared module-level gh_api: authed `gh` CLI preferred, unauthenticated
api.github.com fallback), ranks topic queries client-side via the U10
rank_items helper (reactions = engagement, comment count = corroboration),
and pulls comment bodies for the top few issues so the report carries real
user voice. An `owner/repo` query scopes the search to that repo and keeps
the server's reactions order (no topic to rank against).

Once this connector exists, channel_github is repos-only — its old
"Recent issues / PRs" section would be duplicate signal (review decision).

All network is mocked — no live calls in tests.
"""
import importlib.util
import io
import re
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_github_issues", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "context engineering"


def issue(number, title, reactions=0, comments=0, state="open", body="",
          updated="2026-06-01T00:00:00Z", repo="acme/widget"):
    return {
        "number": number,
        "title": title,
        "state": state,
        "comments": comments,
        "updated_at": updated,
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
        "body": body,
        "reactions": {"total_count": reactions},
    }


def comment(login, body, reactions=0):
    return {
        "user": {"login": login} if login else None,
        "body": body,
        "reactions": {"total_count": reactions},
    }


class FakeGhApi:
    """Path-routing stand-in for the module-level gh_api. Records paths."""

    _COMMENTS_RE = re.compile(r"^repos/([^/]+/[^/]+)/issues/(\d+)/comments")

    def __init__(self, search_result=None, comments=None,
                 search_error=None, comment_errors=None):
        self.search_result = search_result if search_result is not None else {"items": []}
        self.comments = comments or {}          # issue number -> [comment, ...]
        self.search_error = search_error
        self.comment_errors = comment_errors or {}  # issue number -> exception
        self.paths = []

    def __call__(self, path):
        self.paths.append(path)
        if path.startswith("search/issues"):
            if self.search_error is not None:
                raise self.search_error
            return self.search_result
        m = self._COMMENTS_RE.match(path)
        if m:
            number = int(m.group(2))
            if number in self.comment_errors:
                raise self.comment_errors[number]
            return self.comments.get(number, [])
        if path.startswith("search/repositories"):
            return self.search_result
        raise AssertionError(f"unexpected gh_api path: {path}")

    def search_paths(self):
        return [p for p in self.paths if p.startswith("search/")]

    def comment_paths(self):
        return [p for p in self.paths if self._COMMENTS_RE.match(p)]


def run_channel(fake, topic=TOPIC, max_items=5):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "github-issues.md"
        with mock.patch.object(deep_research, "gh_api", fake):
            n = deep_research.channel_github_issues(topic, out, max_items)
        return n, out.read_text(encoding="utf-8")


class TopicModeTests(unittest.TestCase):
    def test_on_topic_issue_outranks_offtopic_viral_and_comments_render(self):
        fake = FakeGhApi(
            search_result={"items": [
                issue(1, "Dark mode toggle for the settings page",
                      reactions=4200, comments=900),
                issue(2, "Context engineering breaks on long documents",
                      reactions=35, comments=12,
                      body="Repro: context engineering with 100k tokens"),
            ]},
            comments={2: [
                comment("alice", "Same here — context engineering fails past 80k.",
                        reactions=7),
                comment("bob", "Workaround: chunk the context first."),
            ]},
        )
        n, text = run_channel(fake)

        self.assertEqual(n, 2)
        # ranked: on-topic first despite the reactions gap (relevance floor)
        self.assertLess(
            text.index("Context engineering breaks"), text.index("Dark mode toggle")
        )
        # issue line: state, reactions, comments count, updated date, url
        self.assertIn("open", text)
        self.assertIn("35 reactions", text)
        self.assertIn("12 comments", text)
        self.assertIn("updated 2026-06-01", text)
        self.assertIn("https://github.com/acme/widget/issues/2", text)
        # comment excerpts carry author + reactions + body
        self.assertIn("@alice", text)
        self.assertIn("context engineering fails past 80k", text)
        self.assertIn("@bob", text)
        # comment reactions surfaced
        self.assertIn("7", text)

    def test_topic_query_carries_topic_and_reactions_sort(self):
        fake = FakeGhApi()
        run_channel(fake)
        searches = fake.search_paths()
        self.assertTrue(searches)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(searches[0]).query)
        self.assertIn(TOPIC, params["q"][0])
        self.assertIn("is:issue", params["q"][0])
        self.assertEqual(params["sort"], ["reactions"])

    def test_comment_fetch_capped_to_top_issues_and_per_issue_limit(self):
        many = [
            issue(i, f"Context engineering report {i}", reactions=100 - i,
                  comments=20)
            for i in range(1, 8)
        ]
        flood = {i: [comment(f"user{i}_{j}", f"context engineering note {j}")
                     for j in range(9)] for i in range(1, 8)}
        fake = FakeGhApi(search_result={"items": many}, comments=flood)
        n, text = run_channel(fake, max_items=7)
        self.assertEqual(n, 7)
        # only the top few issues get comment fetches (cap = 5)
        self.assertEqual(
            len(fake.comment_paths()), deep_research._GH_ISSUES_COMMENT_ISSUES
        )
        # per-issue comment cap: 9 available, at most 5 rendered
        self.assertIn("@user1_0", text)
        self.assertNotIn("@user1_5", text)

    def test_long_comment_bodies_are_truncated(self):
        long_body = "context engineering " * 60  # ~1200 chars
        fake = FakeGhApi(
            search_result={"items": [
                issue(3, "Context engineering megathread", reactions=9, comments=1),
            ]},
            comments={3: [comment("carol", long_body)]},
        )
        _, text = run_channel(fake)
        comment_line = next(line for line in text.splitlines() if "@carol" in line)
        self.assertLess(len(comment_line), 400)


class RepoModeTests(unittest.TestCase):
    def test_owner_repo_query_scopes_search_and_keeps_server_order(self):
        fake = FakeGhApi(search_result={"items": [
            issue(10, "Crash when saving", reactions=500, comments=40,
                  repo="acme/widget"),
            issue(11, "Feature request: export to CSV", reactions=90, comments=8,
                  repo="acme/widget"),
        ]})
        n, text = run_channel(fake, topic="acme/widget")
        self.assertEqual(n, 2)
        params = urllib.parse.parse_qs(
            urllib.parse.urlparse(fake.search_paths()[0]).query
        )
        self.assertIn("repo:acme/widget", params["q"][0])
        self.assertIn("is:issue", params["q"][0])
        # server order (reactions desc) preserved — no topic to rank against
        self.assertLess(text.index("Crash when saving"), text.index("export to CSV"))

    def test_plain_topic_is_not_mistaken_for_repo(self):
        fake = FakeGhApi()
        run_channel(fake, topic="context engineering")
        params = urllib.parse.parse_qs(
            urllib.parse.urlparse(fake.search_paths()[0]).query
        )
        self.assertNotIn("repo:", params["q"][0])

    def test_repo_with_zero_issues_writes_honest_empty_message(self):
        fake = FakeGhApi(search_result={"items": []})
        n, text = run_channel(fake, topic="acme/widget")
        self.assertEqual(n, 0)
        self.assertIn("No issues found", text)


class DegradeTests(unittest.TestCase):
    def test_rate_limit_403_propagates_so_wrapper_writes_error_md(self):
        err = urllib.error.HTTPError(
            "https://api.github.com/search/issues", 403, "rate limited",
            None, io.BytesIO(b"API rate limit exceeded"),
        )
        fake = FakeGhApi(search_error=err)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "github-issues.md"
            with mock.patch.object(deep_research, "gh_api", fake):
                with self.assertRaises(urllib.error.HTTPError):
                    deep_research.channel_github_issues(TOPIC, out, 5)

    def test_comment_failure_on_one_issue_leaves_siblings_intact(self):
        fake = FakeGhApi(
            search_result={"items": [
                issue(1, "Context engineering issue A", reactions=50, comments=10),
                issue(2, "Context engineering issue B", reactions=40, comments=9),
            ]},
            comments={2: [comment("dave", "context engineering works after the fix")]},
            comment_errors={1: RuntimeError("boom")},
        )
        n, text = run_channel(fake)
        self.assertEqual(n, 2)
        # both issues still render
        self.assertIn("issue A", text)
        self.assertIn("issue B", text)
        # failed issue says why its comments are missing; sibling has its comment
        self.assertIn("comments unavailable", text)
        self.assertIn("@dave", text)


class GithubChannelDedupeTests(unittest.TestCase):
    def test_channel_github_is_repos_only_no_issue_section(self):
        fake = FakeGhApi(search_result={"items": [
            {
                "full_name": "acme/widget",
                "stargazers_count": 1234,
                "pushed_at": "2026-06-15T00:00:00Z",
                "description": "A widget",
                "html_url": "https://github.com/acme/widget",
            },
        ]})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "github.md"
            with mock.patch.object(deep_research, "gh_api", fake):
                n = deep_research.channel_github(TOPIC, out, 5)
            text = out.read_text(encoding="utf-8")
        self.assertEqual(n, 1)
        self.assertIn("acme/widget", text)
        self.assertNotIn("Recent issues", text)
        # no search/issues call — the github-issues connector owns that signal
        self.assertEqual(
            [p for p in fake.paths if p.startswith("search/issues")], []
        )


class RegistryTests(unittest.TestCase):
    def test_connector_registered_keyless_direct_default(self):
        conn = deep_research.CONNECTORS["github-issues"]
        self.assertEqual(conn.kind, "direct")
        self.assertEqual(conn.requires, [])
        self.assertTrue(conn.default)
        self.assertTrue(conn.available())
        self.assertIn("comment", conn.source.lower())

    def test_output_name_present(self):
        self.assertEqual(
            deep_research.OUTPUT_NAMES["github-issues"], "github-issues.md"
        )


class WindowsSafetyTests(unittest.TestCase):
    def test_runner_source_avoids_posix_only_calls(self):
        source = RUNNER.read_text(encoding="utf-8")
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid", "pwd.", "grp."):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

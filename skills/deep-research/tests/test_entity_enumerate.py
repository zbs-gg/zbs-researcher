"""U1 — entity enumeration (merge + per-source degrade).

enumerate_entities merges free sources (GitHub top-by-stars + HN mentions) and
an optional/required LLM lens into a canonical, deduped, ranked entity list.
Each source degrades independently; the repo-shaped path runs with zero paid
keys; non-repo topics carry a coverage caveat when no lens is available.

All network is mocked — no live calls, no paid calls.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"
FANOUT = SCRIPTS / "entity_fanout.py"

_scripts_path = str(SCRIPTS)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


deep_research = _load("deep_research_enum", RUNNER)
entity_fanout = _load("entity_fanout_enum", FANOUT)


def repo(full, stars, desc):
    return {
        "full_name": full,
        "stargazers_count": stars,
        "pushed_at": "2026-07-20T00:00:00Z",
        "html_url": f"https://github.com/{full}",
        "description": desc,
    }


class FakeRunner:
    """Assembles the runner-globals dict entity_fanout resolves via _r().

    Real ranking helpers come from the loaded deep_research module; the network
    surfaces (gh_api, get_json, channel_* lenses) are fakes so nothing hits the
    wire.
    """

    def __init__(self, *, gh_items=None, gh_error=None, hn_hits=None,
                 hn_error=None, lens_lines=None):
        self.gh_items = gh_items or []
        self.gh_error = gh_error
        self.hn_hits = hn_hits or []
        self.hn_error = hn_error
        self.lens_lines = lens_lines
        self.lens_calls = 0

    def gh_api(self, path):
        if self.gh_error:
            raise self.gh_error
        return {"items": list(self.gh_items)}

    def get_json(self, url, headers=None, timeout=30):
        if "hn.algolia.com" in url:
            if self.hn_error:
                raise self.hn_error
            return {"hits": list(self.hn_hits)}
        raise AssertionError(f"unexpected get_json url: {url}")

    def _lens(self, query, out_path, max_items, usage_sink=None):
        self.lens_calls += 1
        Path(out_path).write_text(self.lens_lines or "", encoding="utf-8")
        if usage_sink is not None:
            usage_sink.append({"total_tokens": 42})
        return len(self.lens_lines or "")

    def as_globals(self):
        g = {
            "gh_api": self.gh_api,
            "get_json": self.get_json,
            "relevance_score": deep_research.relevance_score,
            "RELEVANCE_FLOOR": deep_research.RELEVANCE_FLOOR,
            "engagement_score": deep_research.engagement_score,
        }
        for lens in ("perplexity", "gemini", "grok"):
            g["channel_" + lens] = self._lens
        return g


class EnumerateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _run(self, runner, topic="LLM agent memory", n=50, keys=None):
        entity_fanout.attach_runner(runner.as_globals())
        return entity_fanout.enumerate_entities(topic, n=n, keys=keys or {}, tmpdir=self.tmp)

    def test_happy_merge_dedup_rank(self):
        gh = [
            repo("mem0ai/mem0", 61000, "Universal memory layer for AI Agents"),
            repo("getzep/zep", 4700, "Graph memory for LLM agent apps"),
            repo("letta-ai/letta", 12000, "Agent memory server (MemGPT)"),
            repo("cognee-ai/cognee", 3000, "Memory for AI agents in a few lines"),
        ]
        hn = [
            {"title": "Show HN: Mem0 – open-source memory layer for AI agents"},
            {"title": "Zep: graph memory for LLM agent apps"},
        ]
        res = self._run(FakeRunner(gh_items=gh, hn_hits=hn), keys={})
        names = [e["name"] for e in res["entities"]]
        self.assertIn("mem0", names)
        self.assertIn("zep", names)
        # mem0 (61k stars + HN Show HN + HN mention) outranks cognee (3k stars)
        self.assertLess(names.index("mem0"), names.index("cognee"))
        # ranks are 0-based, contiguous, deduped
        self.assertEqual([e["rank"] for e in res["entities"]], list(range(len(res["entities"]))))
        self.assertEqual(len(names), len(set(names)))

    def test_zero_key_repo_shaped_no_llm_call(self):
        gh = [
            repo("mem0ai/mem0", 61000, "memory layer for AI agents"),
            repo("getzep/zep", 4700, "graph memory for agents"),
            repo("letta-ai/letta", 12000, "agent memory server"),
            repo("cognee-ai/cognee", 3000, "memory for AI agents"),
        ]
        runner = FakeRunner(gh_items=gh, hn_hits=[])
        res = self._run(runner, keys={})
        self.assertEqual(runner.lens_calls, 0, "no lens key => no LLM call attempted")
        self.assertEqual(res["sources"]["llm"], "absent")
        self.assertIn("repo-shaped", res["coverage"])
        self.assertTrue(res["entities"])

    def test_github_source_degrades_hn_survives(self):
        hn = [{"title": "Show HN: Letta – agent memory server"}]
        runner = FakeRunner(gh_error=RuntimeError("HTTP 403"), hn_hits=hn)
        res = self._run(runner, keys={})
        self.assertTrue(res["sources"]["github"].startswith("error"))
        self.assertEqual(res["sources"]["hn"], "ok")
        # HN Show HN candidate still made it into the list — no abort
        self.assertIn("letta", [e["name"].lower() for e in res["entities"]])

    def test_hn_source_degrades_github_survives(self):
        gh = [repo("mem0ai/mem0", 61000, "memory layer for AI agents")]
        runner = FakeRunner(gh_items=gh, hn_error=RuntimeError("boom"))
        res = self._run(runner, keys={})
        self.assertEqual(res["sources"]["github"], "ok")
        self.assertTrue(res["sources"]["hn"].startswith("error"))
        self.assertIn("mem0", [e["name"] for e in res["entities"]])

    def test_all_sources_empty_clean_result(self):
        res = self._run(FakeRunner(gh_items=[], hn_hits=[]), keys={})
        self.assertEqual(res["entities"], [])
        self.assertEqual(res["sources"]["github"], "ok")

    def test_non_repo_topic_no_lens_carries_caveat(self):
        # GitHub yields unrelated repos (no confidently topic-matching repo),
        # so the topic is product/people-shaped and, with no lens, coverage
        # is flagged as repo-shaped-only.
        gh = [repo("torvalds/linux", 190000, "the linux kernel")]
        res = self._run(FakeRunner(gh_items=gh, hn_hits=[]),
                        topic="AI companion apps", keys={})
        self.assertIn("repo-shaped entities only", res["coverage"])
        self.assertEqual(res["sources"]["llm"], "absent")

    def test_non_repo_topic_with_lens_runs_enumeration(self):
        gh = [repo("torvalds/linux", 190000, "the linux kernel")]
        lens_lines = "1. Character.ai\n2. Replika\n3. Pi\n"
        runner = FakeRunner(gh_items=gh, hn_hits=[], lens_lines=lens_lines)
        res = self._run(runner, topic="AI companion apps",
                        keys={"perplexity": "pplx-x"})
        self.assertEqual(runner.lens_calls, 1)
        self.assertTrue(res["sources"]["llm"].startswith("ok"))
        names = [e["name"].lower() for e in res["entities"]]
        self.assertIn("character.ai", names)
        self.assertIn("replika", names)

    def test_dedup_normalized_name_without_lens(self):
        # "mem0ai/mem0" (repo full_name) and a bare "Mem0" HN mention collapse
        # to one entity via normalized-name dedup — no alias map needed.
        gh = [repo("mem0ai/mem0", 61000, "memory layer for AI agents")]
        hn = [{"title": "Show HN: Mem0 – memory for agents"}]
        res = self._run(FakeRunner(gh_items=gh, hn_hits=hn), keys={})
        mem0 = [e for e in res["entities"] if e["name"] == "mem0"]
        self.assertEqual(len(mem0), 1)
        self.assertIn("github", mem0[0]["sources"])
        self.assertIn("hn", mem0[0]["sources"])

    def test_seed_alias_collapses_memgpt_and_letta(self):
        gh = [
            repo("letta-ai/letta", 12000, "agent memory server for LLM agents"),
            repo("mem0ai/mem0", 61000, "memory layer for LLM agents"),
        ]
        # An HN Show HN names "MemGPT" — the seed alias map folds it into letta.
        hn = [{"title": "Show HN: MemGPT – LLM agents with memory"}]
        res = self._run(FakeRunner(gh_items=gh, hn_hits=hn), keys={})
        letta = [e for e in res["entities"] if e["name"] == "letta"]
        self.assertEqual(len(letta), 1, "MemGPT must fold into letta")

    def test_cap_enforced(self):
        gh = [repo(f"org{i}/proj{i}", 1000 - i, "memory for AI agents")
              for i in range(30)]
        res = self._run(FakeRunner(gh_items=gh, hn_hits=[]), n=10, keys={})
        self.assertEqual(len(res["entities"]), 10)


if __name__ == "__main__":
    unittest.main()

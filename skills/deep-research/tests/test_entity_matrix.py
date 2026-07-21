"""U5 — aggregation, fill_rate/degraded flag, honest cost/time, usage capture.

aggregate_matrix turns per-cell records into an entity x channel dossier matrix
plus a manifest with per-channel fill_rate, a `degraded` flag when a free
channel is mostly rate-limited, and token accounting split real (vendor usage)
vs est (size-based). The additive usage_sink on the three lens channels is
proven byte-compatible with the single-query path.

All network is mocked — no live calls, no paid calls.
"""
import importlib.util
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


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


deep_research = _load("deep_research_matrix", RUNNER)
entity_fanout = _load("entity_fanout_matrix", FANOUT)


def rec(entity, channel, status="ok", tier="free", **kw):
    d = {"entity": entity, "slug": entity.lower(), "channel": channel,
         "status": status, "tier": tier, "items_or_chars": 3, "seconds": 0.5,
         "output_size": 400}
    d.update(kw)
    return d


def enum_result(names):
    return {
        "topic": "LLM agent memory",
        "entities": [
            {"name": n, "rank": i, "type": "repo", "sources": ["github"],
             "aliases": [], "repo": f"org/{n}", "stars": 1000 - i}
            for i, n in enumerate(names)
        ],
        "sources": {"github": "ok", "hn": "ok", "llm": "absent"},
        "coverage": "repo-shaped topic — GitHub + HN enumeration",
    }


class AggregateTest(unittest.TestCase):
    def _agg(self, enum, records):
        return entity_fanout.aggregate_matrix(
            enum, records, topic="LLM agent memory",
            started="t0", finished="t1", wall_seconds=42.4,
            plan_report={"n": len(enum["entities"]), "paid_cells": 0},
        )

    def test_matrix_reflects_every_cell_including_errors(self):
        enum = enum_result(["mem0", "zep"])
        records = [
            rec("mem0", "hackernews", "ok"),
            rec("mem0", "bluesky", "error", error="HTTP 403"),
            rec("zep", "hackernews", "ok"),
            rec("zep", "bluesky", "ok"),
        ]
        out = self._agg(enum, records)
        matrix = {row["name"]: row for row in out["matrix"]}
        self.assertEqual(matrix["mem0"]["cells"]["bluesky"]["status"], "error")
        self.assertTrue(matrix["mem0"]["cells"]["bluesky"]["path"].endswith("bluesky.ERROR.md"))
        self.assertEqual(matrix["mem0"]["cells"]["hackernews"]["status"], "ok")
        # entity facets from enumeration are carried onto the row
        self.assertEqual(matrix["mem0"]["repo"], "org/mem0")

    def test_degraded_flag_on_rate_limited_free_channel(self):
        enum = enum_result(["a", "b", "c"])
        # bluesky: 2 of 3 error -> error_fraction .667 > .5 -> degraded
        records = [
            rec("a", "bluesky", "error"), rec("b", "bluesky", "error"),
            rec("c", "bluesky", "ok"),
            rec("a", "hackernews", "ok"), rec("b", "hackernews", "ok"),
            rec("c", "hackernews", "ok"),
        ]
        out = self._agg(enum, records)
        self.assertTrue(out["manifest"]["degraded"])
        self.assertEqual(out["manifest"]["channels"]["bluesky"]["fill_rate"], round(1 / 3, 3))

    def test_degraded_boundary_exactly_half_not_degraded(self):
        # error_fraction == 0.5 must NOT degrade (strict '>' threshold).
        enum = enum_result(["a", "b"])
        records = [rec("a", "bluesky", "error"), rec("b", "bluesky", "ok")]
        out = self._agg(enum, records)
        self.assertFalse(out["manifest"]["degraded"])
        self.assertEqual(out["manifest"]["channels"]["bluesky"]["error_fraction"], 0.5)

    def test_healthy_run_not_degraded(self):
        enum = enum_result(["a", "b"])
        records = [rec("a", "hackernews", "ok"), rec("b", "hackernews", "ok")]
        out = self._agg(enum, records)
        self.assertFalse(out["manifest"]["degraded"])

    def test_token_accounting_real_vs_est(self):
        enum = enum_result(["a", "b"])
        records = [
            rec("a", "hackernews", "ok"),  # free, no tokens
            rec("a", "perplexity", "ok", tier="paid", tokens=120, tokens_kind="real"),
            rec("b", "grok", "ok", tier="paid", tokens=50, tokens_kind="est"),
        ]
        out = self._agg(enum, records)
        m = out["manifest"]
        self.assertEqual(m["tokens_real"], 120)
        self.assertEqual(m["tokens_est"], 50)
        self.assertEqual(m["paid_calls"], 2)

    def test_free_only_run_reports_zero_paid(self):
        enum = enum_result(["a", "b"])
        records = [rec("a", "hackernews", "ok"), rec("b", "reddit", "ok")]
        out = self._agg(enum, records)
        m = out["manifest"]
        self.assertEqual(m["paid_calls"], 0)
        self.assertEqual(m["tokens_real"], 0)
        self.assertEqual(m["tokens_est"], 0)
        # honesty: wall time is real, never omitted
        self.assertEqual(m["wall_seconds"], 42.4)


class UsageTotalTest(unittest.TestCase):
    def test_openai_shape(self):
        self.assertEqual(entity_fanout._usage_total({"total_tokens": 321}), 321)

    def test_gemini_shape(self):
        self.assertEqual(entity_fanout._usage_total({"totalTokenCount": 210}), 210)

    def test_sum_prompt_completion(self):
        self.assertEqual(
            entity_fanout._usage_total({"prompt_tokens": 10, "completion_tokens": 5}), 15
        )

    def test_missing(self):
        self.assertEqual(entity_fanout._usage_total(None), 0)
        self.assertEqual(entity_fanout._usage_total({}), 0)


class LensUsageByteCompatTest(unittest.TestCase):
    """The additive usage_sink must not change the lens channels' written output
    or return value (byte-compat single-query path) — it only captures usage."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _assert_byte_compat(self, fn, keys, data, expected_usage):
        with mock.patch.object(deep_research, "KEYS", keys), \
             mock.patch.object(deep_research, "post_json", return_value=data):
            out_no = self.tmp / "no.md"
            ret_no = fn("query", out_no, 5)
            sink = []
            out_yes = self.tmp / "yes.md"
            ret_yes = fn("query", out_yes, 5, usage_sink=sink)
        self.assertEqual(out_no.read_text(), out_yes.read_text(),
                         "usage_sink changed the written output")
        self.assertEqual(ret_no, ret_yes, "usage_sink changed the return value")
        self.assertEqual(sink, [expected_usage])

    def test_perplexity_byte_compat_and_capture(self):
        data = {"choices": [{"message": {"content": "hello world"}}],
                "citations": ["https://a"], "usage": {"total_tokens": 99}}
        self._assert_byte_compat(
            deep_research.channel_perplexity, {"perplexity": "pplx-x"}, data,
            {"total_tokens": 99},
        )

    def test_grok_byte_compat_and_capture(self):
        data = {"output": [{"type": "message",
                            "content": [{"type": "output_text", "text": "grok text"}]}],
                "usage": {"total_tokens": 77}}
        self._assert_byte_compat(
            deep_research.channel_grok, {"grok": "xai-x"}, data, {"total_tokens": 77},
        )

    def test_gemini_byte_compat_and_capture(self):
        data = {"candidates": [{"content": {"parts": [{"text": "gem text"}]}}],
                "usageMetadata": {"totalTokenCount": 55}}
        self._assert_byte_compat(
            deep_research.channel_gemini, {"gemini": "AIzaX"}, data,
            {"totalTokenCount": 55},
        )


class RunCellTokenTest(unittest.TestCase):
    """_run_cell records real tokens when the lens surfaces usage, else an est."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ctx = entity_fanout.FanoutContext("topic", 5, sleep=lambda *_: None)

    def _lens_runner(self, usage):
        def lens(query, out_path, max_items, usage_sink=None):
            Path(out_path).write_text("x" * 400, encoding="utf-8")
            if usage_sink is not None and usage:
                usage_sink.append(usage)
            return 1
        return {"CONNECTORS": {"perplexity": types.SimpleNamespace(name="perplexity", fn=lens)}}

    def test_paid_cell_records_real_tokens(self):
        entity_fanout.attach_runner(self._lens_runner({"total_tokens": 250}))
        cell = {"entity": {"name": "mem0", "rank": 0}, "channel": "perplexity", "tier": "paid"}
        r = entity_fanout._run_cell(cell, self.tmp, self.ctx)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["tokens_kind"], "real")
        self.assertEqual(r["tokens"], 250)

    def test_paid_cell_estimates_when_no_usage(self):
        entity_fanout.attach_runner(self._lens_runner(None))
        cell = {"entity": {"name": "mem0", "rank": 0}, "channel": "perplexity", "tier": "paid"}
        r = entity_fanout._run_cell(cell, self.tmp, self.ctx)
        self.assertEqual(r["tokens_kind"], "est")
        self.assertEqual(r["tokens"], 100)  # 400 bytes // 4


class BriefRenderTest(unittest.TestCase):
    """U7 — entity-by-entity HTML brief, self-contained, honest footer."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        entity_fanout.attach_runner({
            "markdown_to_html": deep_research.markdown_to_html,
            "HTML_TEMPLATE": deep_research.HTML_TEMPLATE,
        })

    def _write_cell(self, slug, channel, body):
        d = self.tmp / "entities" / slug / f"{channel}.md"
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(body, encoding="utf-8")

    def _agg(self, degraded=False):
        return {
            "matrix": [
                {"name": "mem0", "rank": 0, "sources": ["github", "hn"],
                 "repo": "mem0ai/mem0", "stars": 61000, "desc": "memory layer for agents",
                 "cells": {
                     "hackernews": {"status": "ok", "path": "entities/mem0/hackernews.md"},
                     "bluesky": {"status": "error", "error": "HTTP 403",
                                 "path": "entities/mem0/bluesky.ERROR.md"}}},
                {"name": "zep", "rank": 1, "sources": ["github"], "repo": "getzep/zep",
                 "stars": 4700, "cells": {
                     "hackernews": {"status": "ok", "path": "entities/zep/hackernews.md"}}},
            ],
            "manifest": {"entities": 2, "cells_ok": 2, "cells_error": 1, "paid_calls": 0,
                         "tokens_real": 0, "tokens_est": 0, "wall_seconds": 12.3,
                         "coverage": "repo-shaped topic", "degraded": degraded},
        }

    def test_matrix_render_entity_by_entity(self):
        self._write_cell("mem0", "hackernews", "# HN — mem0\n- **Show HN: Mem0** — 201 pts\n")
        self._write_cell("zep", "hackernews", "# HN — zep\n- **Show HN: Zep** — 104 pts\n")
        brief = entity_fanout.render_entity_brief(self.tmp, "LLM agent memory", self._agg())
        html = brief.read_text()
        # entity rows present (H2 per entity)
        self.assertIn("mem0", html)
        self.assertIn("zep", html)
        self.assertIn("Show HN: Mem0", html)
        # error cell rendered as an honest marker, not blank-dropped
        self.assertIn("HTTP 403", html)
        # cost footer present
        self.assertIn("2 entities", html)
        self.assertIn("paid_calls=0", html)

    def test_brief_is_self_contained(self):
        self._write_cell("mem0", "hackernews", "# HN\n- item https://a.example\n")
        brief = entity_fanout.render_entity_brief(self.tmp, "topic", self._agg())
        html = brief.read_text()
        self.assertIsNone(re.search(r'src=|href="http[^"]*\.css|@import', html))

    def test_degraded_banner_shown(self):
        self._write_cell("mem0", "hackernews", "# HN\n- item\n")
        brief = entity_fanout.render_entity_brief(self.tmp, "topic", self._agg(degraded=True))
        self.assertIn("DEGRADED", brief.read_text())

    def test_no_degraded_banner_when_healthy(self):
        self._write_cell("mem0", "hackernews", "# HN\n- item\n")
        brief = entity_fanout.render_entity_brief(self.tmp, "topic", self._agg(degraded=False))
        self.assertNotIn("DEGRADED", brief.read_text())


if __name__ == "__main__":
    unittest.main()

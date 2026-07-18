"""U4 — OpenRouter backend, Tier 2 (R8; KTD2).

One OPENROUTER_API_KEY routes the gemini / grok / perplexity lenses through
OpenRouter's chat/completions endpoint with each provider's explicit native
grounding tool. Direct keys always take precedence (independent blast radius).
openai stays OUT of OpenRouter routing (R17: opt-in, direct key only).

All network is mocked (post_json is patched on the loaded module) — no live
OpenRouter calls in tests. The live U4 smoke needs paid-call approval and is
recorded separately.
"""
import importlib.util
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_openrouter", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "context engineering"
OPENROUTER_KEY = "sk-or-test-abc123"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# OpenAI chat/completions response shape (what OpenRouter returns).
CHAT_RESPONSE = {
    "choices": [{"message": {"content": "openrouter lens answer"}}]
}


def patched_keys(**overrides):
    """Context manager: pin EVERY llm-relevant key so the host machine's real
    keys (loaded at module import) can never satisfy an assertion."""
    values = {
        "gemini": "",
        "grok": "",
        "openai": "",
        "perplexity": "",
        "openrouter": "",
        # not an LLM lens, but pinned so a host meta-ads token can't move a
        # token-gated direct connector between live and skipped mid-test
        "meta_ads": "",
    }
    values.update(overrides)
    return mock.patch.dict(deep_research.KEYS, values)


class FakePost:
    """Stand-in for post_json. Records every call; returns a canned response
    or raises a canned exception."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, body, headers, timeout=300):
        self.calls.append(
            {"url": url, "body": body, "headers": headers, "timeout": timeout}
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class OpenRouterRoutingTests(unittest.TestCase):
    def run_channel(self, channel_name, keys, response):
        fake = FakePost(response)
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.md"
            fn = getattr(deep_research, f"channel_{channel_name}")
            with patched_keys(**keys), mock.patch.object(
                deep_research, "post_json", fake
            ):
                result = fn(TOPIC, out_path, 10)
            written = out_path.read_text() if out_path.exists() else ""
        return fake, result, written

    # -- gemini ------------------------------------------------------------
    def test_gemini_openrouter_key_only_routes_via_openrouter(self):
        fake, result, written = self.run_channel(
            "gemini", {"openrouter": OPENROUTER_KEY}, CHAT_RESPONSE
        )
        self.assertEqual(len(fake.calls), 1)
        call = fake.calls[0]
        self.assertEqual(call["url"], OPENROUTER_URL)
        self.assertEqual(
            call["headers"]["Authorization"], f"Bearer {OPENROUTER_KEY}"
        )
        self.assertEqual(call["body"]["model"], "google/gemini-2.5-pro")
        self.assertEqual(call["body"]["tools"], [{"googleSearch": {}}])
        self.assertIn(TOPIC, call["body"]["messages"][-1]["content"])
        self.assertIn("openrouter lens answer", written)
        self.assertEqual(result, len(written))

    def test_gemini_direct_key_takes_precedence_over_openrouter(self):
        direct_response = {
            "candidates": [{"content": {"parts": [{"text": "direct gemini"}]}}]
        }
        fake, _, written = self.run_channel(
            "gemini",
            {"gemini": "AIzaFakeDirect", "openrouter": OPENROUTER_KEY},
            direct_response,
        )
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("generativelanguage.googleapis.com", fake.calls[0]["url"])
        self.assertNotIn("openrouter.ai", fake.calls[0]["url"])
        self.assertIn("direct gemini", written)

    # -- grok --------------------------------------------------------------
    def test_grok_openrouter_key_only_routes_via_openrouter(self):
        fake, _, written = self.run_channel(
            "grok", {"openrouter": OPENROUTER_KEY}, CHAT_RESPONSE
        )
        call = fake.calls[0]
        self.assertEqual(call["url"], OPENROUTER_URL)
        self.assertEqual(
            call["headers"]["Authorization"], f"Bearer {OPENROUTER_KEY}"
        )
        self.assertEqual(call["body"]["model"], "x-ai/grok-4")
        self.assertEqual(call["body"]["tools"], [{"type": "x_search"}])
        self.assertIn(TOPIC, call["body"]["messages"][-1]["content"])
        self.assertIn("openrouter lens answer", written)

    def test_grok_direct_key_takes_precedence_over_openrouter(self):
        direct_response = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "direct grok"}],
                }
            ]
        }
        fake, _, written = self.run_channel(
            "grok",
            {"grok": "xai-fake-direct", "openrouter": OPENROUTER_KEY},
            direct_response,
        )
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("api.x.ai", fake.calls[0]["url"])
        self.assertNotIn("openrouter.ai", fake.calls[0]["url"])
        self.assertIn("direct grok", written)

    # -- perplexity --------------------------------------------------------
    def test_perplexity_openrouter_key_only_uses_sonar_no_tools(self):
        fake, _, written = self.run_channel(
            "perplexity", {"openrouter": OPENROUTER_KEY}, CHAT_RESPONSE
        )
        call = fake.calls[0]
        self.assertEqual(call["url"], OPENROUTER_URL)
        self.assertEqual(call["body"]["model"], "perplexity/sonar")
        # Sonar IS the grounding: no tool field at all.
        self.assertNotIn("tools", call["body"])
        self.assertIn("openrouter lens answer", written)

    def test_perplexity_direct_key_takes_precedence_over_openrouter(self):
        direct_response = {
            "choices": [{"message": {"content": "direct perplexity"}}]
        }
        fake, _, written = self.run_channel(
            "perplexity",
            {"perplexity": "pplx-fake-direct", "openrouter": OPENROUTER_KEY},
            direct_response,
        )
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("api.perplexity.ai", fake.calls[0]["url"])
        self.assertNotIn("openrouter.ai", fake.calls[0]["url"])
        self.assertIn("direct perplexity", written)

    # -- citations ---------------------------------------------------------
    def test_openrouter_citations_and_annotations_are_appended(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "grounded answer",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://example.com/annotated",
                                    "title": "Annotated source",
                                },
                            }
                        ],
                    }
                }
            ],
            "citations": ["https://example.com/cited"],
        }
        _, _, written = self.run_channel(
            "perplexity", {"openrouter": OPENROUTER_KEY}, response
        )
        self.assertIn("grounded answer", written)
        self.assertIn("https://example.com/cited", written)
        self.assertIn("https://example.com/annotated", written)

    # -- error path --------------------------------------------------------
    def test_openrouter_http_500_propagates_from_channel(self):
        err = urllib.error.HTTPError(
            OPENROUTER_URL, 500, "Internal Server Error", None, io.BytesIO(b"boom")
        )
        fake = FakePost(err)
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.md"
            with patched_keys(openrouter=OPENROUTER_KEY), mock.patch.object(
                deep_research, "post_json", fake
            ):
                with self.assertRaises(urllib.error.HTTPError):
                    deep_research.channel_gemini(TOPIC, out_path, 10)

    def test_openrouter_http_500_writes_error_md_via_run_connector(self):
        err = urllib.error.HTTPError(
            OPENROUTER_URL, 500, "Internal Server Error", None, io.BytesIO(b"boom")
        )
        fake = FakePost(err)
        manifest = {"channels": {}}
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            conn = deep_research.CONNECTORS["gemini"]
            with patched_keys(openrouter=OPENROUTER_KEY), mock.patch.object(
                deep_research, "post_json", fake
            ):
                deep_research.run_connector(
                    conn, TOPIC, out_dir, 10, manifest, threading.Lock()
                )
            error_files = list(out_dir.glob("*.ERROR.md"))
        self.assertEqual(len(error_files), 1)
        self.assertEqual(manifest["channels"]["gemini"]["status"], "error")
        self.assertIn("HTTP 500", manifest["channels"]["gemini"]["error"])

    # -- no ":online" ever -------------------------------------------------
    def test_no_online_suffix_in_any_openrouter_request(self):
        for provider in ("gemini", "grok", "perplexity"):
            body = deep_research.openrouter_request_body(provider, TOPIC)
            self.assertNotIn(":online", body["model"], provider)
            self.assertNotIn(":online", json.dumps(body), provider)
        for model in deep_research.OPENROUTER_MODELS.values():
            self.assertNotIn(":online", model)

    def test_openrouter_request_body_rejects_unrouted_provider(self):
        # openai is deliberately NOT routed through OpenRouter (R17).
        with self.assertRaises(ValueError):
            deep_research.openrouter_request_body("openai", TOPIC)


class OpenRouterAvailabilityTests(unittest.TestCase):
    def test_missing_keys_empty_with_only_openrouter_key(self):
        with patched_keys(openrouter=OPENROUTER_KEY):
            for name in ("gemini", "grok", "perplexity"):
                conn = deep_research.CONNECTORS[name]
                self.assertEqual(conn.missing_keys(), [], name)
                self.assertTrue(conn.available(), name)

    def test_missing_keys_empty_with_only_direct_key(self):
        with patched_keys(gemini="AIzaFakeDirect"):
            conn = deep_research.CONNECTORS["gemini"]
            self.assertEqual(conn.missing_keys(), [])
            self.assertTrue(conn.available())

    def test_missing_keys_reported_when_neither_key_present(self):
        with patched_keys():
            for name in ("gemini", "grok", "perplexity"):
                conn = deep_research.CONNECTORS[name]
                self.assertEqual(conn.missing_keys(), [name], name)
                self.assertFalse(conn.available(), name)

    def test_openai_stays_out_of_openrouter_routing(self):
        # R17: openai is opt-in, direct key only — an openrouter key must NOT
        # make it available.
        with patched_keys(openrouter=OPENROUTER_KEY):
            conn = deep_research.CONNECTORS["openai"]
            self.assertEqual(conn.missing_keys(), ["openai"])
            self.assertFalse(conn.available())

    def test_select_connectors_skips_llm_lenses_without_any_key(self):
        with patched_keys():
            live, skipped = deep_research.select_connectors(None, None)
            # token-gated direct connectors (meta-ads) may be skipped too;
            # this test pins the LLM-lens gating specifically
            llm_skipped = {c.name for c in skipped if c.kind == "llm"}
            self.assertEqual(llm_skipped, {"gemini", "grok", "perplexity"})
            for c in skipped:
                self.assertTrue(c.missing_keys(), c.name)

    def test_select_connectors_runs_llm_lenses_with_only_openrouter_key(self):
        with patched_keys(openrouter=OPENROUTER_KEY):
            live, skipped = deep_research.select_connectors(None, None)
        live_names = {c.name for c in live}
        self.assertIn("gemini", live_names)
        self.assertIn("grok", live_names)
        self.assertIn("perplexity", live_names)
        self.assertNotIn("openai", live_names)  # not default, and R17
        # every LLM lens runs; only token-gated direct connectors (meta-ads,
        # threads — no tokens in patched_keys) may remain skipped
        self.assertEqual([c.name for c in skipped if c.kind == "llm"], [])
        self.assertEqual([c.name for c in skipped], ["meta-ads", "threads"])

    def test_list_connectors_reflects_openrouter_availability(self):
        buf = io.StringIO()
        with patched_keys(openrouter=OPENROUTER_KEY), mock.patch.object(
            sys, "stdout", buf
        ):
            deep_research.list_connectors_json()
        rows = {r["name"]: r for r in json.loads(buf.getvalue())["connectors"]}
        for name in ("gemini", "grok", "perplexity"):
            self.assertTrue(rows[name]["available"], name)
            self.assertEqual(rows[name]["missing_keys"], [], name)
            self.assertEqual(rows[name]["fallback_key"], "openrouter", name)
        self.assertFalse(rows["openai"]["available"])
        self.assertNotIn("fallback_key", rows["openai"])


class OpenRouterKeyResolutionTests(unittest.TestCase):
    def test_keys_registry_has_openrouter_entry(self):
        self.assertIn("openrouter", deep_research.KEYS)

    def test_read_key_matches_detect_state_openrouter_contract(self):
        # Mirror of detect_state: files ["openrouter-key.txt"],
        # pattern sk-or-..., env OPENROUTER_API_KEY.
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp)
            (secrets / "openrouter-key.txt").write_text(
                "OPENROUTER = sk-or-file-key-42\n", encoding="utf-8"
            )
            with mock.patch.object(deep_research, "SECRETS", secrets):
                key = deep_research.read_key(
                    ["openrouter-key.txt"],
                    r"sk-or-[A-Za-z0-9_\-]+",
                    "OPENROUTER_API_KEY",
                )
        self.assertEqual(key, "sk-or-file-key-42")


if __name__ == "__main__":
    unittest.main()

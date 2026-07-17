"""U9 — Pluggable media backend (R16, R17; KTD5).

media_backend.py (sibling of deep-research.py, NOT a connector) exposes
get_backend(profile) -> object with transcribe(audio_bytes, mime) and
describe_image(image_bytes, mime). Two profiles:

  client — cloud-cheap raw HTTP (stdlib urllib only): Groq Whisper
           (whisper-large-v3-turbo, multipart) for audio and Gemini Flash
           (generateContent, inline_data base64) for vision. Missing key ->
           a clear guidance error, the caller degrades.
  self   — local $0: lazy mlx_whisper / mlx_vlm imports; when they are not
           installed the error is clean install guidance, never a raw
           ImportError traceback. No hard dependency.

Profile resolution: explicit arg > DEEP_RESEARCH_PROFILE env > "client";
an unknown profile warns on stderr and falls back to client.

R17 hard constraint: NO OpenAI or Anthropic endpoints anywhere in the
module — client requests go to Groq/Gemini only (asserted on the source AND
on captured request URLs). All network is mocked; no live calls in tests.
"""
import base64
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"
MEDIA = SCRIPTS / "media_backend.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    import media_backend
finally:
    if path_added:
        sys.path.remove(scripts_path)


GROQ_KEY = "gsk_FakeMediaKey123"  # short: stays under the selftest secret-scan floor
GEMINI_KEY = "AIzaFakeVisionKey123"
AUDIO = b"\xffRIFF-fake-audio-bytes"
IMAGE = b"\x89PNG-fake-image-bytes"


@contextlib.contextmanager
def isolated_env(secrets_dir, **overrides):
    """No host key (env or ~/.openclaw/secrets file) may satisfy a test."""
    with mock.patch.dict(os.environ):
        for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "DEEP_RESEARCH_PROFILE"):
            os.environ.pop(name, None)
        os.environ["DEEP_RESEARCH_SECRETS_DIR"] = str(secrets_dir)
        os.environ.update(overrides)
        yield


class Recorder:
    """Stand-in for media_backend._http_post_raw. Captures every request."""

    def __init__(self, result):
        self.result = result
        self.calls = []  # (url, data, headers, timeout)

    def __call__(self, url, data, headers, timeout=120):
        self.calls.append((url, data, headers, timeout))
        return self.result


class ProfileTests(unittest.TestCase):
    def test_default_profile_is_client(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp):
            backend = media_backend.get_backend()
        self.assertIsInstance(backend, media_backend.ClientBackend)
        self.assertTrue(callable(backend.transcribe))
        self.assertTrue(callable(backend.describe_image))

    def test_env_profile_selects_self_backend(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_env(
            tmp, DEEP_RESEARCH_PROFILE="self"
        ):
            backend = media_backend.get_backend()
        self.assertIsInstance(backend, media_backend.SelfBackend)

    def test_explicit_arg_overrides_env(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_env(
            tmp, DEEP_RESEARCH_PROFILE="client"
        ):
            backend = media_backend.get_backend("self")
        self.assertIsInstance(backend, media_backend.SelfBackend)

    def test_unknown_profile_warns_on_stderr_and_falls_back_to_client(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp), \
                contextlib.redirect_stderr(stderr):
            backend = media_backend.get_backend("mainframe")
        self.assertIsInstance(backend, media_backend.ClientBackend)
        warning = stderr.getvalue()
        self.assertIn("mainframe", warning)
        self.assertIn("client", warning)


class ClientTranscribeTests(unittest.TestCase):
    def test_transcribe_builds_groq_multipart_request(self):
        recorder = Recorder({"text": "hello from whisper"})
        with tempfile.TemporaryDirectory() as tmp, isolated_env(
            tmp, GROQ_API_KEY=GROQ_KEY
        ), mock.patch.object(media_backend, "_http_post_raw", recorder):
            text = media_backend.get_backend("client").transcribe(
                AUDIO, mime="audio/mpeg"
            )

        self.assertEqual(text, "hello from whisper")
        self.assertEqual(len(recorder.calls), 1)
        url, data, headers, _ = recorder.calls[0]
        self.assertEqual(
            url, "https://api.groq.com/openai/v1/audio/transcriptions"
        )
        self.assertEqual(headers["Authorization"], f"Bearer {GROQ_KEY}")
        content_type = headers["Content-Type"]
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        boundary = content_type.split("boundary=", 1)[1]
        self.assertIn(boundary.encode(), data)
        # model field carries the Groq Whisper model id
        self.assertIn(b'name="model"', data)
        self.assertIn(b"whisper-large-v3-turbo", data)
        # the audio bytes travel in a file part with a mime-matched name
        self.assertIn(b'name="file"', data)
        self.assertIn(b'filename="audio.mp3"', data)
        self.assertIn(AUDIO, data)

    def test_groq_key_resolves_from_secrets_file(self):
        recorder = Recorder({"text": "ok"})
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "groq-key.txt").write_text(
                GROQ_KEY + "\n", encoding="utf-8"
            )
            with isolated_env(tmp), mock.patch.object(
                media_backend, "_http_post_raw", recorder
            ):
                text = media_backend.get_backend("client").transcribe(AUDIO)
        self.assertEqual(text, "ok")
        self.assertEqual(
            recorder.calls[0][2]["Authorization"], f"Bearer {GROQ_KEY}"
        )

    def test_missing_groq_key_raises_guidance_without_network(self):
        recorder = Recorder({"text": "never"})
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp), \
                mock.patch.object(media_backend, "_http_post_raw", recorder):
            with self.assertRaises(media_backend.MediaBackendError) as ctx:
                media_backend.get_backend("client").transcribe(AUDIO)
        message = str(ctx.exception)
        self.assertIn("groq-key.txt", message)
        self.assertIn("GROQ_API_KEY", message)
        self.assertEqual(recorder.calls, [])


class ClientVisionTests(unittest.TestCase):
    GEMINI_RESPONSE = {
        "candidates": [
            {"content": {"parts": [{"text": "a red bicycle on a beach"}]}}
        ]
    }

    def test_describe_image_builds_gemini_request(self):
        recorder = Recorder(self.GEMINI_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp, isolated_env(
            tmp, GEMINI_API_KEY=GEMINI_KEY
        ), mock.patch.object(media_backend, "_http_post_raw", recorder):
            text = media_backend.get_backend("client").describe_image(
                IMAGE, mime="image/png"
            )

        self.assertEqual(text, "a red bicycle on a beach")
        self.assertEqual(len(recorder.calls), 1)
        url, data, headers, _ = recorder.calls[0]
        self.assertIn("generativelanguage.googleapis.com", url)
        self.assertIn(":generateContent", url)
        self.assertIn("gemini-2.0-flash", url)
        # key travels in a header, never in the URL
        self.assertNotIn(GEMINI_KEY, url)
        self.assertEqual(headers["x-goog-api-key"], GEMINI_KEY)
        body = json.loads(data.decode("utf-8"))
        parts = body["contents"][0]["parts"]
        inline = [p["inline_data"] for p in parts if "inline_data" in p]
        self.assertEqual(len(inline), 1)
        self.assertEqual(inline[0]["mime_type"], "image/png")
        self.assertEqual(
            inline[0]["data"], base64.b64encode(IMAGE).decode("ascii")
        )
        # a text instruction part accompanies the image
        self.assertTrue(any(p.get("text") for p in parts))

    def test_missing_gemini_key_raises_guidance_without_network(self):
        recorder = Recorder(self.GEMINI_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp), \
                mock.patch.object(media_backend, "_http_post_raw", recorder):
            with self.assertRaises(media_backend.MediaBackendError) as ctx:
                media_backend.get_backend("client").describe_image(IMAGE)
        message = str(ctx.exception)
        self.assertIn("gemini-key.txt", message)
        self.assertIn("GEMINI_API_KEY", message)
        self.assertEqual(recorder.calls, [])


class SelfBackendTests(unittest.TestCase):
    def test_transcribe_without_mlx_whisper_gives_install_guidance(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp), \
                mock.patch.dict(sys.modules, {"mlx_whisper": None}):
            with self.assertRaises(media_backend.MediaBackendError) as ctx:
                media_backend.get_backend("self").transcribe(AUDIO)
        self.assertNotIsInstance(ctx.exception, ImportError)
        self.assertIn("mlx-whisper", str(ctx.exception))

    def test_describe_image_without_mlx_vlm_gives_install_guidance(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp), \
                mock.patch.dict(sys.modules, {"mlx_vlm": None}):
            with self.assertRaises(media_backend.MediaBackendError) as ctx:
                media_backend.get_backend("self").describe_image(IMAGE)
        self.assertNotIsInstance(ctx.exception, ImportError)
        self.assertIn("mlx-vlm", str(ctx.exception))

    def test_transcribe_with_fake_mlx_whisper_runs_locally(self):
        captured = {}
        fake = types.ModuleType("mlx_whisper")

        def transcribe(path, **kwargs):
            captured["bytes"] = Path(path).read_bytes()
            return {"text": "local transcript"}

        fake.transcribe = transcribe
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp), \
                mock.patch.dict(sys.modules, {"mlx_whisper": fake}):
            text = media_backend.get_backend("self").transcribe(
                AUDIO, mime="audio/mpeg"
            )
        self.assertEqual(text, "local transcript")
        self.assertEqual(captured["bytes"], AUDIO)


class EndpointConstraintTests(unittest.TestCase):
    """R17: never OpenAI, never Anthropic — Groq/Gemini only."""

    def test_source_contains_no_openai_or_anthropic_endpoints(self):
        source = MEDIA.read_text(encoding="utf-8")
        self.assertNotIn("api.openai.com", source)
        self.assertNotIn("api.anthropic.com", source)

    def test_client_endpoints_are_groq_and_gemini(self):
        self.assertTrue(
            media_backend.GROQ_TRANSCRIBE_URL.startswith("https://api.groq.com/")
        )
        self.assertIn(
            "generativelanguage.googleapis.com", media_backend.GEMINI_BASE_URL
        )

    def test_source_avoids_posix_only_calls(self):
        source = MEDIA.read_text(encoding="utf-8")
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                      "pwd.", "grp."):
            self.assertNotIn(token, source)


class RunnerKeysTests(unittest.TestCase):
    """--diagnose visibility: the runner's KEYS must resolve groq."""

    def fresh_keys(self):
        spec = importlib.util.spec_from_file_location(
            "deep_research_media_keys", RUNNER
        )
        module = importlib.util.module_from_spec(spec)
        added = scripts_path not in sys.path
        if added:
            sys.path.insert(0, scripts_path)
        try:
            spec.loader.exec_module(module)
        finally:
            if added:
                sys.path.remove(scripts_path)
        return module.KEYS

    def test_runner_keys_resolve_groq_from_env(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_env(tmp):
            self.assertFalse(self.fresh_keys()["groq"])
            with mock.patch.dict(os.environ, {"GROQ_API_KEY": GROQ_KEY}):
                self.assertEqual(self.fresh_keys()["groq"], GROQ_KEY)


if __name__ == "__main__":
    unittest.main()
